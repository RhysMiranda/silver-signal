"""Turn cleaned headlines into a few numbers per trading day.

The question each number answers: "what was the mood of the news that came out
after the previous session's open and before this session's 09:15 open?"

Mood here is GDELT's own `gdelt_tone` score for each article (negative = gloomy,
positive = upbeat). It is a crude, free starting point. Your FinBERT or LLM
scores later replace it, using the same plumbing.

Categories are grouped into three themes so a model with a few hundred days of
data has only a handful of numbers to learn from:

    metals  silver, precious_metals, india_duty
    us      fed, dollar, us_macro
    india   rupee, rbi
"""
from __future__ import annotations

import pandas as pd

from . import news

THEMES = {
    "silver": "metals", "precious_metals": "metals", "india_duty": "metals",
    "fed": "us", "dollar": "us", "us_macro": "us",
    "rupee": "india", "rbi": "india",
}


def load_headlines(path) -> pd.DataFrame:
    h = pd.read_csv(path)
    h["published_utc"] = pd.to_datetime(h["published_utc"], utc=True)
    return h


def tone_features(headlines: pd.DataFrame, sessions: pd.DatetimeIndex,
                  trusted_only: bool = False) -> pd.DataFrame:
    """One row per session: average tone and headline count for each theme.

    Columns: tone_metals, tone_us, tone_india, n_metals, n_us, n_india, news_missing.
    Tone is 0 (neutral) on days a theme had no headlines.
    """
    h = headlines.copy()
    if trusted_only:
        h = h[h["trusted"].astype(bool)]
    h["theme"] = h["category"].map(THEMES)
    h = h.dropna(subset=["theme", "gdelt_tone"])
    h["session"] = news.assign_session(h["published_utc"], sessions)
    h = h.dropna(subset=["session"])

    g = h.groupby(["session", "theme"])["gdelt_tone"]
    tone = g.mean().unstack().add_prefix("tone_")
    count = g.size().unstack().add_prefix("n_")
    out = pd.concat([tone, count], axis=1).reindex(sessions)
    for theme in sorted(set(THEMES.values())):
        out[f"tone_{theme}"] = out.get(f"tone_{theme}", pd.Series(index=sessions, dtype=float)).fillna(0.0)
        out[f"n_{theme}"] = out.get(f"n_{theme}", pd.Series(index=sessions, dtype=float)).fillna(0).astype(int)
    out["news_missing"] = (out[[c for c in out if c.startswith("n_")]].sum(axis=1) == 0).astype(int)
    out.index.name = "date"
    return out[[f"tone_{t}" for t in ("metals", "us", "india")]
               + [f"n_{t}" for t in ("metals", "us", "india")] + ["news_missing"]]
