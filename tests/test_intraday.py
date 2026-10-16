import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import intraday  # noqa: E402


def _world(premium_sd: float, seed: int = 0):
    """Hourly silver and FX, and an ETF priced off them at 09:30 and 15:30 IST."""
    rng = np.random.default_rng(seed)
    hours = pd.date_range("2025-01-01", "2026-06-30", freq="h", tz="UTC")
    s = pd.Series(30 * np.exp(np.cumsum(rng.normal(0, 0.004, len(hours)))), index=hours)
    fx = pd.Series(85 * np.exp(np.cumsum(rng.normal(0, 0.0005, len(hours)))), index=hours)
    days = pd.bdate_range("2025-01-02", "2026-06-29")
    t_open = (days + pd.Timedelta(hours=4)).tz_localize("UTC")    # 09:30 IST
    t_close = (days + pd.Timedelta(hours=10)).tz_localize("UTC")  # 15:30 IST
    fair_open = (s[t_open] * fx[t_open]).to_numpy() / 1000
    fair_close = (s[t_close] * fx[t_close]).to_numpy() / 1000
    prem = rng.normal(0, premium_sd, len(days))
    etf = pd.DataFrame({"open": fair_open * (1 + prem), "close": fair_close}, index=days)
    bars = lambda x: pd.DataFrame({"open": x, "close": x})  # noqa: E731
    return etf, bars(s), bars(fx)


def test_price_at_uses_next_bar_and_rejects_stale():
    bars = pd.DataFrame({"open": [1.0, 2.0]},
                        index=pd.to_datetime(["2025-01-01 04:00", "2025-01-01 10:00"], utc=True))
    got = intraday.price_at(bars, pd.to_datetime(["2025-01-01 03:45", "2025-01-01 06:00",
                                                  "2025-01-01 10:00"], utc=True))
    assert got.iloc[0] == 1.0          # 15 minutes later: fine
    assert np.isnan(got.iloc[1])       # 4 hours later: too stale
    assert got.iloc[2] == 2.0


def test_no_premium_means_etf_tracks_silver():
    etf, s, fx = _world(premium_sd=0.0)
    r = intraday.report(intraday.build(etf, s, fx))
    assert r["corr_etf_vs_silver_daytime"] > 0.99
    assert abs(r["mean_gap_bps"]) < 1


def test_opening_premium_that_unwinds_is_detected():
    etf, s, fx = _world(premium_sd=0.01)
    r = intraday.report(intraday.build(etf, s, fx))
    assert -1.1 < r["premium_slope"] < -0.9
    q = intraday.by_premium_quintile(intraday.build(etf, s, fx))
    assert q["gap_bps"].iloc[0] > 0 > q["gap_bps"].iloc[-1]
