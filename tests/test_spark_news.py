"""The Spark job must give exactly what the tested pandas code gives."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyspark")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from silver_signal import finbert, news_features  # noqa: E402


def _headlines(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    t = pd.Timestamp("2024-01-01", tz="UTC") + pd.to_timedelta(rng.uniform(0, 120 * 86400, n), unit="s")
    words = np.array(["Silver prices surge on rate cut hopes", "Fed signals rate hike, dollar rises",
                      "Rupee slips to record low against US dollar", "Gold prices slump as dollar firms",
                      "US inflation cools; markets rally"])
    cats = np.array(["silver", "fed", "rupee", "precious_metals", "us_macro", "dollar", "rbi"])
    return pd.DataFrame({"published_utc": t, "title": rng.choice(words, n),
                         "source": "x.com", "category": rng.choice(cats, n),
                         "gdelt_tone": rng.normal(0, 3, n), "trusted": rng.random(n) < 0.3})


def test_spark_matches_pandas():
    from silver_signal import spark_news as job
    heads = _headlines()
    sessions = pd.bdate_range("2024-01-02", "2024-05-01")
    per, daily = job.run(heads, sessions, "keyword", cores=2, partitions=4)

    assert len(per) == len(heads)
    expected = finbert.keyword_probs(heads["title"].tolist())
    got = per.set_index(["title"])[["p_pos", "p_neg", "p_neu"]].groupby(level=0).first()
    exp = pd.DataFrame(expected, index=heads["title"], columns=["p_pos", "p_neg", "p_neu"]).groupby(level=0).first()
    pd.testing.assert_frame_equal(got.sort_index(), exp.sort_index(), check_exact=False, atol=1e-12)

    scored = heads.assign(fb_score=expected[:, 0] - expected[:, 1])
    ref_fb = news_features.theme_features(scored, sessions, "fb_score")
    ref_tone = news_features.theme_features(scored, sessions, "gdelt_tone")
    common = daily.index.intersection(ref_fb.index)
    assert len(common) > 50
    for c in news_features.feature_names("fb_score"):
        np.testing.assert_allclose(daily.loc[common, c], ref_fb.loc[common, c], atol=1e-9)
    for c in news_features.feature_names("gdelt_tone"):
        np.testing.assert_allclose(daily.loc[common, c], ref_tone.loc[common, c], atol=1e-9)
    for t in news_features.THEME_NAMES:
        assert (daily.loc[common, f"n_{t}"] == ref_fb.loc[common, f"n_{t}"]).all()
