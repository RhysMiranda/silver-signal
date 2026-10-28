"""Is the ETF's opening premium really unwinding, or is the slope an artefact?

    python scripts/intraday_1015.py --etf SILVERBEES.NS
    python scripts/intraday_1015.py --etf SILVERBEES.NS --refresh

Splits the trading day at 10:15 IST using the ETF's own hourly bars (about two
years from Yahoo, cached in data/raw/etf_<name>_60m.csv). The giveback measured
from 10:15 shares no price with the 09:15 open premium, so a negative slope
there can't come from noise in the opening print.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import config, data, intraday  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etf", default="SILVERBEES.NS")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    name = "etf_" + a.etf.split(".")[0].lower()
    etf = data.load_all(etf=a.etf)["etf"]
    etf_h = intraday.load_hourly(name, a.etf, a.refresh)
    silver_h = intraday.load_hourly("silver", config.SILVER, a.refresh)
    fx_h = intraday.load_hourly("usdinr", config.USDINR, a.refresh)
    d = intraday.build_1015(intraday.build(etf, silver_h, fx_h), etf, etf_h, silver_h, fx_h)
    if len(d) < 30:
        sys.exit(f"Only {len(d)} usable days. Try --refresh.")
    r = intraday.report_1015(d)

    print(f"{a.etf}: {r['days']} sessions, {d.index[0].date()} to {d.index[-1].date()}\n")
    print("ETF minus silver, average per day:")
    print(f"  09:15-10:15  {r['gap_first_hour_bps']:+6.1f} bps  (t = {r['gap_first_hour_t']:+.1f})")
    print(f"  10:15-15:30  {r['gap_rest_bps']:+6.1f} bps  (t = {r['gap_rest_t']:+.1f})")
    print("\nSlope of the gap on the 09:15 opening premium:")
    print(f"  09:15-10:15  {r['slope_first_hour']:+.2f}   (shares the open price, partly mechanical)")
    print(f"  10:15-15:30  {r['slope_rest']:+.2f}   (no shared price; correlation {r['corr_rest']:+.2f})")
    print("\nTotal ETF return over these days:")
    print(f"  buy 09:15, sell 15:30  {r['etf_0915_close_total']:+.1%}")
    print(f"  buy 10:15, sell 15:30  {r['etf_1015_close_total']:+.1%}   (silver over the same hours {r['silver_1015_close_total']:+.1%})")
    print("\nHow to read this: a clearly negative 10:15-15:30 slope means the premium is real and")
    print("keeps unwinding after the first hour. A slope near zero means the earlier -0.62 was")
    print("mostly noise in the opening print, and the giveback happens in the first hour.")

    out = config.RESULTS_DIR / ("intraday_1015_" + a.etf.split(".")[0].lower())
    out.mkdir(parents=True, exist_ok=True)
    d.to_csv(out / "daily.csv")
    pd.Series(r).to_csv(out / "summary.csv", header=["value"])
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
