"""Download daily prices from Yahoo Finance and cache them as CSV.

Every frame returned here has a tz-naive daily DatetimeIndex and lower-case
columns: open, high, low, close, volume.
"""
from __future__ import annotations

import pandas as pd

from . import config

COLUMNS = ["open", "high", "low", "close", "volume"]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):  # newer yfinance returns (field, ticker)
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    df = df[[c for c in COLUMNS if c in df.columns]].copy()
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.dropna(subset=["close"])


def download(ticker: str, start: str = config.START, end: str | None = None) -> pd.DataFrame:
    """Daily OHLCV for one Yahoo Finance ticker."""
    import yfinance as yf  # imported here so tests run without it

    raw = yf.download(ticker, start=start, end=end, interval="1d",
                      auto_adjust=False, progress=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"No data returned for {ticker}. Check the symbol and your connection.")
    return _clean(raw)


def load(name: str, ticker: str, refresh: bool = False) -> pd.DataFrame:
    """Read data/raw/<name>.csv, downloading it first if missing or refresh=True."""
    path = config.DATA_DIR / "raw" / f"{name}.csv"
    if refresh or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        download(ticker).to_csv(path)
    return pd.read_csv(path, index_col="date", parse_dates=["date"])


def load_all(refresh: bool = False) -> dict[str, pd.DataFrame]:
    return {
        "etf": load("etf", config.ETF, refresh),
        "silver": load("silver", config.SILVER, refresh),
        "fx": load("usdinr", config.USDINR, refresh),
    }
