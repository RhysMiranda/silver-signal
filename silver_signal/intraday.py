"""Compare the ETF with silver during Indian trading hours, using hourly prices.

The daily results showed the ETF losing money between the 09:15 open and the
15:30 close. Two explanations, two predictions:

  A. Silver itself falls during Indian hours.
     -> the ETF's daytime return roughly equals silver's (in rupees) over the
        same hours, and the gap between them averages about zero.
  B. The ETF opens at a premium to its silver and gives it back.
     -> the ETF does worse than silver during the day, and the more it jumped at
        the open compared with silver's overnight move, the more it falls back.

Hourly bars start on the hour (UTC), so silver at "09:15 IST" is measured at the
first bar starting at or after it, which is 09:30 IST; "15:30 IST" lands exactly
on a bar. India has no daylight saving, so this never shifts. Yahoo serves
roughly the last two years of hourly data.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import config

MAX_STALENESS = pd.Timedelta(minutes=90)


def download_hourly(ticker: str) -> pd.DataFrame:
    """About two years of hourly bars, indexed by bar start time in UTC."""
    import yfinance as yf

    raw = yf.download(ticker, period="730d", interval="60m", auto_adjust=False, progress=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"No hourly data for {ticker}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns=str.lower)[["open", "close"]]
    idx = pd.to_datetime(raw.index)
    raw.index = (idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC"))
    raw.index.name = "time_utc"
    return raw.dropna().sort_index()


def load_hourly(name: str, ticker: str, refresh: bool = False) -> pd.DataFrame:
    path = config.DATA_DIR / "raw" / f"{name}_60m.csv"
    if refresh or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        download_hourly(ticker).to_csv(path)
    df = pd.read_csv(path, index_col="time_utc")
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def price_at(bars: pd.DataFrame, times: pd.DatetimeIndex) -> pd.Series:
    """Price at each moment: the open of the first bar starting at or after it.

    NaN if that bar starts more than 90 minutes later (market closed, data gap).
    """
    idx = bars.index.as_unit("ns")
    t = pd.DatetimeIndex(times).as_unit("ns")
    pos = idx.searchsorted(t, side="left")
    ok = pos < len(idx)
    out = np.full(len(t), np.nan)
    p = pos[ok]
    late = (idx[p] - t[ok]) <= MAX_STALENESS
    vals = bars["open"].to_numpy()[p]
    out[np.flatnonzero(ok)[late]] = vals[late]
    return pd.Series(out, index=times)


def _ist(days: pd.DatetimeIndex, clock) -> pd.DatetimeIndex:
    tz = ZoneInfo(config.IST)
    return pd.DatetimeIndex([datetime.combine(d.date(), clock, tzinfo=tz) for d in days]).tz_convert("UTC")


def build(etf: pd.DataFrame, silver_h: pd.DataFrame, fx_h: pd.DataFrame) -> pd.DataFrame:
    """One row per ETF session that hourly data covers."""
    days = etf.index
    t_open, t_close = _ist(days, config.OPEN_IST), _ist(days, config.CLOSE_IST)
    s_open = price_at(silver_h, t_open).to_numpy() * price_at(fx_h, t_open).to_numpy()
    s_close = price_at(silver_h, t_close).to_numpy() * price_at(fx_h, t_close).to_numpy()

    d = pd.DataFrame(index=days)
    d["etf_day"] = etf["close"] / etf["open"] - 1
    d["etf_night"] = etf["open"] / etf["close"].shift(1) - 1
    d["silver_day"] = s_close / s_open - 1                      # silver in rupees, same hours
    d["silver_night"] = s_open / pd.Series(s_close, index=days).shift(1).to_numpy() - 1
    d["open_premium"] = (1 + d["etf_night"]) / (1 + d["silver_night"]) - 1
    d["day_gap"] = (1 + d["etf_day"]) / (1 + d["silver_day"]) - 1   # ETF minus silver, daytime
    suspect = (etf["open"] == etf["close"]) | (etf["open"] == etf["close"].shift(1))
    return d[~suspect].dropna()


def report(d: pd.DataFrame) -> dict:
    """The numbers that decide between explanation A and B."""
    def total(x):
        return float(np.expm1(np.log1p(x).sum()))

    x, y = d["open_premium"], d["day_gap"]
    slope = float(np.polyfit(x, y, 1)[0]) if len(d) > 2 else float("nan")
    return {
        "days": len(d),
        "etf_daytime_total": total(d["etf_day"]),
        "silver_daytime_total": total(d["silver_day"]),
        "gap_daytime_total": total(d["day_gap"]),
        "mean_gap_bps": float(d["day_gap"].mean() * 1e4),
        "gap_t_stat": float(d["day_gap"].mean() / d["day_gap"].std() * np.sqrt(len(d))),
        "corr_etf_vs_silver_daytime": float(d["etf_day"].corr(d["silver_day"])),
        "premium_slope": slope,
        "premium_corr": float(x.corr(y)),
    }


def by_premium_quintile(d: pd.DataFrame) -> pd.DataFrame:
    q = pd.qcut(d["open_premium"], 5, labels=["1 lowest", "2", "3", "4", "5 highest"])
    g = d.groupby(q, observed=True)
    return pd.DataFrame({
        "days": g.size(),
        "open_premium_bps": g["open_premium"].mean() * 1e4,
        "etf_daytime_bps": g["etf_day"].mean() * 1e4,
        "silver_daytime_bps": g["silver_day"].mean() * 1e4,
        "gap_bps": g["day_gap"].mean() * 1e4,
    }).round(1)
