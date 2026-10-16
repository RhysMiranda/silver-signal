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


def scorer(kind: str):
    """Return a function list[str] -> (n, 3) probabilities (FinBERT loads once per process)."""
    from silver_signal import finbert
    if kind == "keyword":
        return finbert.keyword_probs
    return finbert.get_model().probs


def spark_session(cores: int):
    from pyspark.sql import SparkSession

    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    # let Spark's Python workers import the silver_signal package
    os.environ["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(ROOT), os.environ.get("PYTHONPATH", "")) if p)
    return (SparkSession.builder.master(f"local[{cores}]").appName("silver-signal-news")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.execution.arrow.pyspark.enabled", "true")
            .config("spark.sql.execution.arrow.maxRecordsPerBatch", "2000")
            .config("spark.driver.memory", "4g")
            .config("spark.ui.showConsoleProgress", "true")
            .config("spark.executorEnv.PYTHONPATH", str(ROOT))
            .getOrCreate())


def run(headlines: pd.DataFrame, sessions: pd.DatetimeIndex, scorer_kind: str, cores: int,
        partitions: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    from pyspark.sql import functions as F
    from pyspark.sql.functions import pandas_udf

    spark = spark_session(cores)
    spark.sparkContext.setLogLevel("ERROR")

    h = headlines[["published_utc", "title", "source", "category", "gdelt_tone", "trusted"]].copy()
    h["published_utc"] = (pd.to_datetime(h["published_utc"], utc=True)
                          .dt.tz_localize(None).dt.floor("us").astype("datetime64[us]"))
    h["title"] = h["title"].astype(str)
    h["trusted"] = h["trusted"].astype(bool)
    sdf = spark.createDataFrame(h).repartition(partitions)

    scorer_fn = scorer

    @pandas_udf("p_pos double, p_neg double, p_neu double")
    def score_udf(batches: Iterator[pd.Series]) -> Iterator[pd.DataFrame]:
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
    spark.stop()

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
