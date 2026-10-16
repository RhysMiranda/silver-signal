"""Fake data with the same timing structure as the real thing.

Used by the tests and by `run_baselines.py --synthetic`, so the pipeline can be
checked without a network connection. Silver and USD/INR move hour by hour;
the ETF tracks silver in rupees, opening at 03:45 UTC (09:15 IST) and closing
at 10:00 UTC (15:30 IST). Results on this data say nothing about real markets.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def make(start: str = "2022-09-01", end: str = "2026-10-15", seed: int = 0) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    hours = pd.date_range(start, end, freq="h", tz="UTC")
    n = len(hours)
    silver = 20 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))   # ~2% daily vol
    usdinr = 82 * np.exp(np.cumsum(rng.normal(0, 0.0006, n)))
    s = pd.Series(silver, index=hours)
    fx = pd.Series(usdinr, index=hours)

    def daily_bar(series: pd.Series, close_hour_utc: int, days: pd.DatetimeIndex) -> pd.DataFrame:
        # Yahoo-style: bar dated D (New York date) closes at close_hour_utc on D,
        # which is early morning of D+1 in India
        t = (days + pd.Timedelta(hours=close_hour_utc)).tz_localize("UTC")
        close = series.reindex(t, method="ffill").to_numpy()
        return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                             "volume": 0}, index=days.rename("date"))

    us_days = pd.bdate_range(start, end)
    silver_d = daily_bar(s, 22, us_days)          # ~03:30 IST next morning
    fx_d = daily_bar(fx, 23, us_days)

    in_days = pd.bdate_range(start, end)
    holidays = rng.choice(len(in_days), size=len(in_days) // 25, replace=False)
    in_days = in_days.delete(np.sort(holidays))   # Indian holidays US doesn't share

    def inr_price(ts):
        return (s.reindex(ts, method="ffill") * fx.reindex(ts, method="ffill")).to_numpy() / 1000

    open_t = (in_days + pd.Timedelta(hours=3, minutes=45)).tz_localize("UTC")
    close_t = (in_days + pd.Timedelta(hours=10)).tz_localize("UTC")
    prem = rng.normal(0, 0.002, (2, len(in_days)))  # premium/discount noise
    etf = pd.DataFrame({
        "open": inr_price(open_t) * (1 + prem[0]),
        "close": inr_price(close_t) * (1 + prem[1]),
    }, index=in_days.rename("date"))
    etf["high"] = etf[["open", "close"]].max(axis=1)
    etf["low"] = etf[["open", "close"]].min(axis=1)
    etf["volume"] = 1000
    return {"etf": etf[["open", "high", "low", "close", "volume"]],
            "silver": silver_d, "fx": fx_d}
