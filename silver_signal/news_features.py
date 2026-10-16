"""Turn scored headlines into a few numbers per trading day.

Each number answers: "what was the mood of this theme's news, published after
the previous session's open and before this session's 09:15 open?"

Two scores can be used, through the same plumbing:
    gdelt_tone  GDELT's own general-purpose tone per article (free, crude)
    fb_score    FinBERT: P(positive) - P(negative), finance-specific
                (added by scripts/spark_score_news.py)

Themes are kept apart where the sign for silver differs. Good news for the
dollar is usually bad for silver; a rate cut from the Fed is usually good:

    metals   silver, precious_metals, india_duty
    fed      fed
    dollar   dollar
    us_data  us_macro
    india    rupee, rbi
"""
from __future__ import annotations

import pandas as pd

from . import news

THEMES = {
    "silver": "metals", "precious_metals": "metals", "india_duty": "metals",
    "fed": "fed",
    "dollar": "dollar",
    "us_macro": "us_data",
    "rupee": "india", "rbi": "india",
}
THEME_NAMES = ["metals", "fed", "dollar", "us_data", "india"]
PREFIX = {"gdelt_tone": "tone", "fb_score": "fb"}


def load_headlines(path) -> pd.DataFrame:
    path = str(path)
    h = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
    h["published_utc"] = pd.to_datetime(h["published_utc"], utc=True)
    return h


def theme_features(headlines: pd.DataFrame, sessions: pd.DatetimeIndex,
                   score: str = "gdelt_tone", trusted_only: bool = False) -> pd.DataFrame:
    """One row per session: average score and headline count for each theme.

    Columns: <prefix>_<theme> for each theme (0 = neutral when a theme had no
    headlines), n_<theme>, and news_missing (no headlines at all that session).
    """
    prefix = PREFIX.get(score, score)
    h = headlines.copy()
    if trusted_only:
        h = h[h["trusted"].astype(bool)]
    h["theme"] = h["category"].map(THEMES)
    h = h.dropna(subset=["theme", score])
    h["session"] = news.assign_session(h["published_utc"], sessions)
    h = h.dropna(subset=["session"])

    g = h.groupby(["session", "theme"])[score]
    mean = g.mean().unstack()
    count = g.size().unstack()
    out = pd.DataFrame(index=pd.DatetimeIndex(sessions, name="date"))
    for t in THEME_NAMES:
        out[f"{prefix}_{t}"] = mean.get(t, pd.Series(dtype=float)).reindex(out.index).fillna(0.0)
    for t in THEME_NAMES:
        out[f"n_{t}"] = count.get(t, pd.Series(dtype=float)).reindex(out.index).fillna(0).astype(int)
    out["news_missing"] = (out[[f"n_{t}" for t in THEME_NAMES]].sum(axis=1) == 0).astype(int)
    return out


def feature_names(score: str = "gdelt_tone") -> list[str]:
    return [f"{PREFIX.get(score, score)}_{t}" for t in THEME_NAMES]


# Kept so older code and notes still work.
def tone_features(headlines, sessions, trusted_only=False):
    return theme_features(headlines, sessions, "gdelt_tone", trusted_only)
