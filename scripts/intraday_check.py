"""Is the ETF's daytime drop silver itself, or the ETF's opening premium unwinding?

    python scripts/intraday_check.py --etf SILVERBEES.NS
    python scripts/intraday_check.py --etf SILVERBEES.NS --refresh   # re-download hourly data

Downloads about two years of hourly COMEX silver and USD/INR from Yahoo
(cached in data/raw/*_60m.csv) and compares them with the ETF hour for hour.
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
    ap.add_argument("--etf", default=config.ETF)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    etf = data.load_all(etf=a.etf, refresh=a.refresh)["etf"]
    silver_h = intraday.load_hourly("silver", config.SILVER, a.refresh)
    fx_h = intraday.load_hourly("usdinr", config.USDINR, a.refresh)
    d = intraday.build(etf, silver_h, fx_h)
    if len(d) < 30:
        sys.exit(f"Only {len(d)} usable days. Try --refresh, or check the hourly files.")

    r = intraday.report(d)
    print(f"{a.etf}: {r['days']} sessions with hourly silver, {d.index[0].date()} to {d.index[-1].date()}")
    print("(daytime = 09:15 to 15:30 IST; silver is COMEX silver converted to rupees)\n")
    print(f"Total daytime return, ETF:            {r['etf_daytime_total']:+.1%}")
    print(f"Total daytime return, silver in INR:  {r['silver_daytime_total']:+.1%}")
    print(f"Total daytime gap, ETF minus silver:  {r['gap_daytime_total']:+.1%}")
    print(f"Average daily gap: {r['mean_gap_bps']:+.1f} bps  (t = {r['gap_t_stat']:+.1f}; beyond +/-2 is unlikely to be chance)")
    print(f"Daytime correlation, ETF vs silver:   {r['corr_etf_vs_silver_daytime']:.2f}")
    print(f"\nDoes a bigger opening premium mean a bigger daytime giveback?")
    print(f"  slope {r['premium_slope']:+.2f}, correlation {r['premium_corr']:+.2f}  "
          "(a slope near -1 means the opening premium fully unwinds by the close)\n")
    pd.set_option("display.width", 140)
    print("Grouped by how far the ETF's open ran ahead of silver's overnight move:")
    print(intraday.by_premium_quintile(d).to_string())

    print("\nHow to read this:")
    print("  - ETF and silver daytime totals similar, gap near zero: silver itself falls in Indian hours.")
    print("  - Gap clearly negative, slope clearly negative: the ETF opens rich and gives it back.")
    print("  - Both can be partly true. Report the split.")

    out = config.RESULTS_DIR / ("intraday_" + a.etf.split(".")[0].lower())
    out.mkdir(parents=True, exist_ok=True)
    d.to_csv(out / "daily.csv")
    pd.Series(r).to_csv(out / "summary.csv", header=["value"])
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
