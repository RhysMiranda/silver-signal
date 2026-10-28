"""The daily job's three steps, shared by scripts/paper_trade.py and the Airflow DAG."""
from __future__ import annotations

import pandas as pd

from . import config, data, intraday, live, store


def fetch(etf: str = config.ETF) -> None:
    """Re-download daily and hourly prices into data/raw/."""
    data.load_all(refresh=True, etf=etf)
    name = "etf" if etf == config.ETF else "etf_" + etf.split(".")[0].lower()
    for n, t in ((name, etf), ("silver", config.SILVER), ("usdinr", config.USDINR)):
        intraday.load_hourly(n, t, refresh=True)


def _load(etf: str):
    raw = data.load_all(etf=etf)
    name = "etf" if etf == config.ETF else "etf_" + etf.split(".")[0].lower()
    try:
        hourly = {"etf": intraday.load_hourly(name, etf), "silver": intraday.load_hourly("silver", config.SILVER),
                  "fx": intraday.load_hourly("usdinr", config.USDINR)}
    except Exception as e:  # hourly data is a bonus, not a requirement
        print(f"No hourly data ({e}); 10:15 fields will be empty")
        hourly = None
    return raw, hourly


def trade(etf: str = config.ETF, days: int = 1, save: bool = True) -> list[dict]:
    """Build records for the last `days` sessions and upsert them."""
    raw, hourly = _load(etf)
    sessions = raw["etf"].index[-days:]
    recs = [r for d in sessions if (r := live.record_for(d, raw, hourly)) is not None]
    for r in recs:
        r["etf"] = etf
    if save and recs:
        store.upsert(recs)
    return recs


def report(records: list[dict] | None = None) -> dict:
    s = live.summary(records if records is not None else store.all_records())
    for k, v in s.items():
        print(f"  {k:<28} {v:+.4f}" if isinstance(v, float) else f"  {k:<28} {v}")
    return s


def show(recs: list[dict]) -> None:
    cols = ["date", "pred_ret_oc", "overnight_rule_buys", "ret_oc", "pnl_overnight_rule",
            "pnl_buy_0915", "pnl_wait_1015", "gap_first_hour"]
    with pd.option_context("display.width", 160, "display.float_format", "{:+.4f}".format):
        print(pd.DataFrame(recs)[cols].to_string(index=False))
