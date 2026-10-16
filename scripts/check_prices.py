"""Compare Yahoo's prices with an official NSE download, day by day.

1. Download the ETF's historical data CSV from nseindia.com (see README).
2. Run:  python scripts/check_prices.py path\\to\\nse_file.csv --etf SILVERBEES.NS

Prints how often Yahoo's open and close match NSE's, and lists the worst days.
Opens matter most: the open-to-close results depend entirely on them.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import config, data  # noqa: E402


def read_nse(path: Path) -> pd.DataFrame:
    """Read an NSE historical-data CSV, tolerating its odd headers and number formats."""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace("﻿", "") for c in df.columns]

    def col(*names):
        for n in names:
            if n in df.columns:
                return df[n]
        sys.exit(f"Couldn't find any of {names} in columns: {list(df.columns)}")

    def num(s):
        return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")

    out = pd.DataFrame({
        "date": pd.to_datetime(col("date").astype(str).str.strip(), dayfirst=True, format="mixed"),
        "open": num(col("open", "open price")),
        "close": num(col("close", "close price")),
    })
    return out.dropna().set_index("date").sort_index()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("nse_csv", type=Path)
    ap.add_argument("--etf", default=config.ETF)
    ap.add_argument("--tolerance", type=float, default=0.002, help="0.002 = 0.2%% counts as a match")
    a = ap.parse_args()

    nse = read_nse(a.nse_csv)
    yahoo = data.load_all(etf=a.etf)["etf"][["open", "close"]]
    both = nse.join(yahoo, lsuffix="_nse", rsuffix="_yahoo", how="inner")
    if both.empty:
        sys.exit("No overlapping dates. Check the NSE file is for the same ETF and period.")

    print(f"{len(both)} days compared, {both.index[0].date()} to {both.index[-1].date()}")
    print(f"(NSE file has {len(nse)} days, Yahoo has {len(yahoo)}; "
          f"{len(nse) - len(both)} NSE days missing from Yahoo)\n")
    for field in ("open", "close"):
        diff = (both[f"{field}_yahoo"] / both[f"{field}_nse"] - 1).abs()
        ok = (diff <= a.tolerance).mean()
        print(f"{field:>5}: {ok:.0%} of days match within {a.tolerance:.1%}, "
              f"median gap {diff.median():.3%}, worst {diff.max():.2%}")
    prev = both["close_yahoo"].shift(1)
    stale = (both["open_yahoo"] == prev).mean()
    print(f"\nDays where Yahoo's open just repeats the previous close: {stale:.0%}")

    diff = (both["open_yahoo"] / both["open_nse"] - 1)
    worst = diff.abs().sort_values(ascending=False).head(10).index
    print("\nWorst opens (Yahoo vs NSE):")
    print(both.loc[worst, ["open_nse", "open_yahoo", "close_nse", "close_yahoo"]]
          .assign(open_gap=diff.loc[worst].map("{:+.2%}".format)).to_string())

    verdict = (diff.abs() <= a.tolerance).mean()
    print("\nVerdict:", "opens look reliable" if verdict >= 0.95 else
          "opens are NOT reliable enough; use NSE prices for open-to-close results")


if __name__ == "__main__":
    main()
