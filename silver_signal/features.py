"""Turn raw prices into one row per ETF trading day, using only information
available before that day's 09:15 IST open.

Timing (IST):

    day t-1                                     day t
    ... 15:30 ETF closes ......... ~03:30 COMEX daily bar closes ... 09:15 ETF opens ... 15:30 ETF closes
                                   (Yahoo dates it t-1)

A Yahoo daily bar for silver dated D closes around 17:00 New York time on D,
which is early morning of D+1 in India. So the newest silver bar we may use for
ETF day t is the last one dated strictly before t. The same rule is applied to
USD/INR. Anything dated t or later is a look-ahead leak.

Targets
    ret_cc  close-to-close return of day t. Includes the opening gap, so the
            overnight rule should explain much of it. You cannot trade it from a
            forecast made at 09:15, because yesterday's close has passed.
    ret_oc  open-to-close return of day t. This is what you can actually capture
            by buying at the open and selling at the close.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def last_value_before(series: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """For each date, the latest observation of `series` dated strictly before it."""
    s = series.dropna().sort_index()
    pos = s.index.searchsorted(dates, side="left") - 1
    vals = np.where(pos >= 0, s.to_numpy()[np.clip(pos, 0, None)], np.nan)
    return pd.Series(vals, index=dates, name=series.name)


def build_panel(etf: pd.DataFrame, silver: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    p = pd.DataFrame(index=etf.index.copy())
    p.index.name = "date"
    p["etf_open"] = etf["open"]
    p["etf_close"] = etf["close"]

    # targets (known only after the fact)
    p["ret_cc"] = p["etf_close"] / p["etf_close"].shift(1) - 1
    p["ret_oc"] = p["etf_close"] / p["etf_open"] - 1

    # known at 09:15: overnight moves in silver and the rupee since the previous session
    s_now = last_value_before(silver["close"], p.index)
    fx_now = last_value_before(fx["close"], p.index)
    p["silver_ret"] = s_now / s_now.shift(1) - 1
    p["usdinr_ret"] = fx_now / fx_now.shift(1) - 1
    p["driver"] = (1 + p["silver_ret"]) * (1 + p["usdinr_ret"]) - 1

    # known at 09:15 (yesterday's outcome)
    p["prev_ret_cc"] = p["ret_cc"].shift(1)

    # known at the open itself: the opening gap. Fine as a feature for ret_oc if you
    # trade at or after the open; never use it to predict ret_cc.
    p["gap"] = p["etf_open"] / p["etf_close"].shift(1) - 1

    return p.dropna(subset=["ret_cc", "ret_oc", "driver", "prev_ret_cc"])
