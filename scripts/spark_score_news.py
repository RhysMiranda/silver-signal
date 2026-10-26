"""Score every headline with FinBERT in parallel with Spark, then build daily news moods.

    python scripts/spark_score_news.py --etf SILVERBEES.NS --limit 2000   # quick timing run
    python scripts/spark_score_news.py --etf SILVERBEES.NS                # all headlines

Steps
  1. Read data/news/headlines.csv into a Spark DataFrame.
  2. Score titles with FinBERT inside a pandas UDF. Each Spark worker loads the
     model once and scores its partitions in batches, using all CPU cores.
  3. Assign each headline to the first trading session that opens after it
     (the same tested rule as the rest of the project, so no look-ahead).
  4. Spark SQL: average FinBERT score and GDELT tone per session and theme.
  5. Write data/news/headlines_scored.parquet and data/news/daily_news.parquet.

Output is written through pandas rather than Spark's own file writers, so it
works on Windows without Hadoop's winutils.exe.

Needs Java 17 or 21 and `pip install -r requirements-nlp.txt`.
Use --scorer keyword for a fast dry run with no model download.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from silver_signal import config, data, spark_news  # noqa: E402
from silver_signal import news_features as nfeat  # noqa: E402

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headlines", type=Path, default=config.DATA_DIR / "news" / "headlines.csv")
    ap.add_argument("--etf", default=config.ETF, help="whose trading calendar to use")
    ap.add_argument("--scorer", choices=["finbert", "keyword"], default="finbert")
    ap.add_argument("--cores", type=int, default=None,
                    help="Spark workers. Each FinBERT worker holds its own ~1.5 GB copy of the "
                         "model, so the default for finbert is 4; keyword can use every core.")
    ap.add_argument("--partitions", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None, help="score only the first N headlines")
    ap.add_argument("--out-dir", type=Path, default=config.DATA_DIR / "news")
    a = ap.parse_args()

    if a.cores is None:
        cpus = os.cpu_count() or 2
        a.cores = min(4, max(1, cpus // 2)) if a.scorer == "finbert" else max(1, cpus - 1)

    heads = nfeat.load_headlines(a.headlines)
    if a.limit:
        heads = heads.sort_values("published_utc").head(a.limit)
    sessions = data.load_all(etf=a.etf)["etf"].index
    print(f"{len(heads):,} headlines, {len(sessions)} trading sessions, scorer={a.scorer}, cores={a.cores}")

    if a.scorer == "finbert":
        print("Loading FinBERT once on the driver so the download happens only once...")
        spark_news.scorer("finbert")

    t0 = time.time()
    per_headline, daily = spark_news.run(heads, sessions, a.scorer, a.cores, a.partitions or a.cores * 4)
    secs = time.time() - t0
    print(f"Took {secs/60:.1f} min ({len(heads)/secs:,.0f} headlines a second)")

    a.out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if a.scorer == "finbert" else f"_{a.scorer}"
    per_path = a.out_dir / f"headlines_scored{suffix}.parquet"
    day_path = a.out_dir / f"daily_news{suffix}.parquet"
    per_headline.to_parquet(per_path, index=False)
    daily.to_parquet(day_path)
    print(f"Saved {per_path} and {day_path}")

    if a.scorer == "finbert":
        print("\nMost positive and most negative headlines (sanity check):")
        cols = ["fb_score", "category", "title"]
        s = per_headline.sort_values("fb_score")
        with pd.option_context("display.max_colwidth", 90, "display.width", 160):
            print(s.tail(5)[cols].to_string(index=False))
            print(s.head(5)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
