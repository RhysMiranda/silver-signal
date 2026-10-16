"""News plumbing. Collecting headlines and scoring them is your part (see PLAN.md).

What is here is the part that is easy to get subtly wrong: deciding which
trading day a headline is allowed to inform. A headline may only feed the
forecast for the first session whose 09:15 IST open comes *after* it was
published. Get this wrong and the backtest quietly trains on the future.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from . import config


def session_opens_utc(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """09:15 IST on each session date, expressed in UTC."""
    ist = ZoneInfo(config.IST)
    opens = [datetime.combine(d.date(), config.OPEN_IST, tzinfo=ist) for d in sessions]
    return pd.DatetimeIndex(opens).tz_convert("UTC")


def assign_session(published: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    """Map each publication time to the session it may inform.

    `published` must be timezone-aware, or naive UTC. A headline published exactly
    at 09:15 IST counts for the next session, because you can't act on it before the open.
    Headlines after the last known session get NaT.
    """
    ts = pd.to_datetime(published)
    ts = ts.dt.tz_localize("UTC") if ts.dt.tz is None else ts.dt.tz_convert("UTC")
    sessions = pd.DatetimeIndex(sessions).sort_values()
    opens = session_opens_utc(sessions).as_unit("ns")
    pos = opens.searchsorted(ts.dt.as_unit("ns"), side="right")
    out = [sessions[i] if i < len(sessions) else pd.NaT for i in pos]
    return pd.Series(out, index=published.index, name="session")


def daily_features(headlines: pd.DataFrame, sessions: pd.DatetimeIndex, scorer) -> pd.DataFrame:
    """Aggregate scored headlines into one row per session.

    headlines: columns `published_utc` and `title`
    scorer:    function(title) -> float, positive = bullish for silver in rupees
    """
    h = headlines.copy()
    h["session"] = assign_session(h["published_utc"], sessions)
    h = h.dropna(subset=["session"])
    h["score"] = h["title"].map(scorer)
    g = h.groupby("session")["score"]
    feats = pd.DataFrame({"news_count": g.size(), "news_mean": g.mean(),
                          "news_sum": g.sum()})
    feats = feats.reindex(sessions).fillna({"news_count": 0, "news_sum": 0.0})
    # Zero headlines almost always means a data outage (e.g. GDELT in June 2025),
    # not a quiet market. Flag it so a model can tell "no data" from "no news".
    feats["news_missing"] = (feats["news_count"] == 0).astype(int)
    return feats


# A deliberately crude placeholder. Your FinBERT or LLM scorer should beat it.
_UP = ("rate cut", "dovish", "weaker dollar", "dollar falls", "rupee falls",
       "safe haven", "solar demand", "rally", "surge", "record high", "stimulus")
_DOWN = ("rate hike", "hawkish", "stronger dollar", "dollar rises", "rupee gains",
         "slump", "plunge", "sell-off", "selloff", "demand slows")


def keyword_score(title: str) -> float:
    t = title.lower()
    return float(sum(k in t for k in _UP) - sum(k in t for k in _DOWN))
