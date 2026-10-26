"""Spark job: score headlines with FinBERT in parallel and build daily news moods.

Lives in the package (not the script) so Spark's Python workers can import it.
The command-line entry point is scripts/spark_score_news.py.

Output goes through pandas rather than Spark's file writers, so it runs on
Windows without Hadoop's winutils.exe.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import pandas as pd

from . import news_features as nfeat

ROOT = Path(__file__).resolve().parent.parent
WORKER_SOCKET_TIMEOUT_S = 3600


def scorer(kind: str):
    """Return a function list[str] -> (n, 3) probabilities (FinBERT loads once per process)."""
    from silver_signal import finbert
    if kind == "keyword":
        return finbert.keyword_probs
    # Each Spark worker is its own Python process with its own copy of the model,
    # so split the CPU threads between them instead of letting each grab them all.
    threads = int(os.environ.get("SILVER_SIGNAL_TORCH_THREADS", "1"))
    return finbert.get_model(threads=threads).probs


def _worker_log() -> None:
    """If SILVER_SIGNAL_WORKER_LOG is set, send this worker's crash output
    (including C-level messages from torch/OpenMP) to data/logs/worker_<pid>.log."""
    if not os.environ.get("SILVER_SIGNAL_WORKER_LOG") or getattr(_worker_log, "done", False):
        return
    import faulthandler
    d = ROOT / "data" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    f = open(d / f"worker_{os.getpid()}.log", "a", buffering=1)
    os.dup2(f.fileno(), 2)
    faulthandler.enable(file=f, all_threads=True)
    f.write(f"worker {os.getpid()} started, python {sys.executable}\n")
    _worker_log.done = True


def spark_session(cores: int, conf: dict | None = None, env: dict | None = None):
    from pyspark.sql import SparkSession

    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    os.environ["SILVER_SIGNAL_TORCH_THREADS"] = str(max(1, (os.cpu_count() or 2) // cores))
    # On Windows, PySpark's Python workers keep the 15-second socket timeout they use
    # while connecting, so any batch that takes longer than 15 s (FinBERT does) kills
    # the worker silently. Linux and macOS use a different code path and aren't affected.
    os.environ["SPARK_AUTH_SOCKET_TIMEOUT"] = str(WORKER_SOCKET_TIMEOUT_S)
    # let Spark's Python workers import the silver_signal package
    os.environ["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(ROOT), os.environ.get("PYTHONPATH", "")) if p)
    b = (SparkSession.builder.master(f"local[{cores}]").appName("silver-signal-news")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.execution.arrow.pyspark.enabled", "true")
            .config("spark.sql.execution.arrow.maxRecordsPerBatch", "512")
            .config("spark.driver.memory", "4g")
            .config("spark.ui.showConsoleProgress", "true")
            .config("spark.executorEnv.PYTHONPATH", str(ROOT))
            .config("spark.python.authenticate.socketTimeout", f"{WORKER_SOCKET_TIMEOUT_S}s")
            .config("spark.executorEnv.SPARK_AUTH_SOCKET_TIMEOUT", str(WORKER_SOCKET_TIMEOUT_S))
            .config("spark.executorEnv.SILVER_SIGNAL_TORCH_THREADS",
                    os.environ["SILVER_SIGNAL_TORCH_THREADS"])
            # print the real Python error if a worker dies, not just "crashed"
            .config("spark.python.worker.faulthandler.enabled", "true")
            .config("spark.sql.execution.pyspark.udf.faulthandler.enabled", "true"))
    for k, v in (conf or {}).items():
        b = b.config(k, v)
    for k, v in (env or {}).items():
        b = b.config(f"spark.executorEnv.{k}", v)
    return b.getOrCreate()


def run(headlines: pd.DataFrame, sessions: pd.DatetimeIndex, scorer_kind: str, cores: int,
        partitions: int, conf: dict | None = None,
        env: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    spark = spark_session(cores, conf, env)
    spark.sparkContext.setLogLevel("ERROR")
    try:
        return _run(spark, headlines, sessions, scorer_kind, partitions)
    finally:
        spark.stop()


def _run(spark, headlines, sessions, scorer_kind, partitions):
    from pyspark.sql import functions as F
    from pyspark.sql.functions import pandas_udf

    h = headlines[["published_utc", "title", "source", "category", "gdelt_tone", "trusted"]].copy()
    h["published_utc"] = (pd.to_datetime(h["published_utc"], utc=True)
                          .dt.tz_localize(None).dt.floor("us").astype("datetime64[us]"))
    h["title"] = h["title"].astype(str)
    h["trusted"] = h["trusted"].astype(bool)
    sdf = spark.createDataFrame(h).repartition(partitions)

    scorer_fn = scorer

    @pandas_udf("p_pos double, p_neg double, p_neu double")
    def score_udf(batches: Iterator[pd.Series]) -> Iterator[pd.DataFrame]:
        _worker_log()
        score = scorer_fn(scorer_kind)
        for titles in batches:
            p = score(titles.tolist())
            yield pd.DataFrame(p, columns=["p_pos", "p_neg", "p_neu"])

    session_list = [str(d.date()) for d in sessions]

    @pandas_udf("date")
    def session_udf(ts: pd.Series) -> pd.Series:
        from silver_signal import news
        s = news.assign_session(pd.to_datetime(ts).dt.tz_localize("UTC"),
                                pd.DatetimeIndex(pd.to_datetime(session_list)))
        return pd.to_datetime(s).dt.date

    scored = (sdf.withColumn("fb", score_udf("title"))
                 .select("*", "fb.*").drop("fb")
                 .withColumn("fb_score", F.col("p_pos") - F.col("p_neg"))
                 .withColumn("session", session_udf("published_utc"))
                 .cache())
    n = scored.count()   # forces the scoring to run once

    themes = spark.createDataFrame(list(nfeat.THEMES.items()), ["category", "theme"])
    scored.createOrReplaceTempView("headlines")
    themes.createOrReplaceTempView("themes")
    daily_long = spark.sql("""
        SELECT h.session,
               t.theme,
               AVG(h.fb_score)   AS fb,
               AVG(h.gdelt_tone) AS tone,
               COUNT(*)          AS n,
               AVG(CAST(h.trusted AS DOUBLE)) AS trusted_share
        FROM headlines h
        JOIN themes t ON h.category = t.category
        WHERE h.session IS NOT NULL
        GROUP BY h.session, t.theme
    """)
    daily = (daily_long.groupBy("session").pivot("theme", nfeat.THEME_NAMES)
             .agg(F.first("fb").alias("fb"), F.first("tone").alias("tone"), F.first("n").alias("n"))
             .orderBy("session"))

    per_headline = scored.toPandas()
    daily_pd = daily.toPandas()

    # pivot names come out as "<theme>_<agg>"; rename to "<agg>_<theme>"
    daily_pd = daily_pd.rename(columns={f"{t}_{a}": f"{a}_{t}" for t in nfeat.THEME_NAMES
                                        for a in ("fb", "tone", "n")})
    daily_pd["session"] = pd.to_datetime(daily_pd["session"])
    daily_pd = daily_pd.set_index("session").reindex(pd.DatetimeIndex(sessions, name="date"))
    for t in nfeat.THEME_NAMES:
        daily_pd[f"fb_{t}"] = daily_pd[f"fb_{t}"].fillna(0.0)
        daily_pd[f"tone_{t}"] = daily_pd[f"tone_{t}"].fillna(0.0)
        daily_pd[f"n_{t}"] = daily_pd[f"n_{t}"].fillna(0).astype(int)
    daily_pd["news_missing"] = (daily_pd[[f"n_{t}" for t in nfeat.THEME_NAMES]].sum(axis=1) == 0).astype(int)
    first_news = per_headline["published_utc"].min().normalize()
    daily_pd = daily_pd[daily_pd.index >= first_news]
    per_headline["published_utc"] = pd.to_datetime(per_headline["published_utc"]).dt.tz_localize("UTC")
    print(f"Scored {n:,} headlines")
    return per_headline, daily_pd
