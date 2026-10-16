"""Combine BigQuery exports into one clean headlines file and print a quality report.

1. Save each BigQuery result as CSV into  data/news/raw/  (any file names).
2. Run:  python scripts/clean_news.py
3. Read the report. Fix the keywords in silver_signal/news_filter.py if it
   shows junk, then re-run. Output: data/news/headlines.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import config  # noqa: E402
from silver_signal import news_filter as nf  # noqa: E402

RAW = config.DATA_DIR / "news" / "raw"
OUT = config.DATA_DIR / "news" / "headlines.csv"


def load_raw(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.csv"))
    if not files:
        sys.exit(f"No CSV files in {folder}. Export your BigQuery results there first.")
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    print(f"Read {len(df):,} rows from {len(files)} file(s)")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["published_utc"] = pd.to_datetime(df["published_utc"], utc=True, errors="coerce")
    df["title"] = df["title"].astype(str).map(nf.clean_title)
    before = len(df)
    df = df.dropna(subset=["published_utc"])
    df = df[df["title"].map(nf.is_english)]
    df["category"] = df["title"].map(nf.categorize)
    df = df.dropna(subset=["category"])
    df["source"] = df["source"].astype(str).str.lower()
    df["trusted"] = df["source"].map(nf.is_trusted)
    key = df["title"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    df = (df.assign(_k=key).sort_values("published_utc")
            .drop_duplicates("_k", keep="first").drop(columns="_k"))
    print(f"Kept {len(df):,} of {before:,} after language, relevance and duplicate checks")
    cols = ["published_utc", "title", "source", "url", "category", "gdelt_tone", "trusted"]
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)


def report(df: pd.DataFrame, samples: int) -> None:
    pd.set_option("display.width", 160)
    pd.set_option("display.max_colwidth", 110)
    print("\nBy category")
    print(df["category"].value_counts().to_string())
    print(f"\nFrom trusted outlets: {df['trusted'].mean():.0%}")
    print("\nTop sources")
    print(df["source"].value_counts().head(15).to_string())

    per_day = df.set_index("published_utc").resample("D").size()
    print(f"\nPer day: median {per_day.median():.0f}, min {per_day.min()}, max {per_day.max()}")
    empty = per_day[per_day == 0]
    if len(empty):
        print(f"Days with no headlines: {len(empty)} (first few: "
              f"{', '.join(str(d.date()) for d in empty.index[:5])})")
    print("\nPer month")
    print(df.set_index("published_utc").resample("MS").size().to_string())

    print(f"\nRandom samples ({samples} per category). Read these: is each one useful?")
    for cat, g in df.groupby("category"):
        print(f"\n[{cat}]")
        for _, r in g.sample(min(samples, len(g)), random_state=1).iterrows():
            print(f"  {r['published_utc']:%Y-%m-%d %H:%M}  {r['source'][:24]:<24}  {r['title'][:100]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--trusted-only", action="store_true", help="drop headlines from other outlets")
    a = ap.parse_args()

    df = clean(load_raw(a.raw))
    if a.trusted_only:
        df = df[df["trusted"]]
        print(f"Trusted outlets only: {len(df):,} headlines")
    if df.empty:
        sys.exit("Nothing left after cleaning. Check the export columns and keywords.")
    report(df, a.samples)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"\nSaved {len(df):,} headlines to {a.out}")


if __name__ == "__main__":
    main()
