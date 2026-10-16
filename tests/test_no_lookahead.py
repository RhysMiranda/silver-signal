import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import baselines, evaluate, features, news, synthetic  # noqa: E402


def test_last_value_before_is_strict():
    s = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))
    got = features.last_value_before(s, pd.to_datetime(["2024-01-02", "2024-01-04"]))
    assert got.iloc[0] == 1.0      # value dated the same day is not allowed
    assert got.iloc[1] == 3.0


def test_driver_ignores_same_day_and_future_silver():
    raw = synthetic.make(end="2023-06-30")
    base = features.build_panel(raw["etf"], raw["silver"], raw["fx"])
    day = base.index[100]
    bumped = raw["silver"].copy()
    bumped.loc[bumped.index >= day, "close"] *= 1.5   # change silver from `day` onwards
    after = features.build_panel(raw["etf"], bumped, raw["fx"])
    cols = ["driver", "silver_ret", "prev_ret_cc"]
    pd.testing.assert_frame_equal(base.loc[:day, cols], after.loc[:day, cols])


def test_walk_forward_never_trains_on_test_rows():
    raw = synthetic.make(end="2024-06-30")
    panel = features.build_panel(raw["etf"], raw["silver"], raw["fx"])
    seen = []

    def spy(train, test, target):
        seen.append((train.index.max(), test.index.min()))
        return baselines.zero(train, test, target)

    evaluate.walk_forward(panel, spy, "ret_cc", min_train=60, step=15)
    assert seen and all(tr < te for tr, te in seen)


def test_news_assigned_to_next_open_only():
    sessions = pd.to_datetime(["2024-03-08", "2024-03-11", "2024-03-12"])   # Fri, Mon, Tue
    published = pd.Series(pd.to_datetime([
        "2024-03-08 03:44:00",   # 09:14 IST Fri -> Fri
        "2024-03-08 03:45:00",   # 09:15 IST Fri exactly -> Mon
        "2024-03-09 12:00:00",   # Saturday -> Mon
        "2024-03-12 04:00:00",   # 09:30 IST Tue -> after last session
    ]).tz_localize("UTC"))
    got = news.assign_session(published, sessions)
    assert list(got.iloc[:3]) == list(pd.to_datetime(["2024-03-08", "2024-03-11", "2024-03-11"]))
    assert pd.isna(got.iloc[3])


def test_news_handles_other_timezones():
    sessions = pd.to_datetime(["2024-03-11", "2024-03-12"])
    ny = pd.Series(pd.to_datetime(["2024-03-11 08:00"]).tz_localize("America/New_York"))
    # 08:00 New York = 17:30 IST Monday, after Monday's open -> Tuesday
    assert news.assign_session(ny, sessions).iloc[0] == pd.Timestamp("2024-03-12")


def test_overnight_rule_finds_signal_in_synthetic_data():
    raw = synthetic.make()
    panel = features.build_panel(raw["etf"], raw["silver"], raw["fx"])
    pred = evaluate.walk_forward(panel, baselines.overnight_rule, "ret_cc")
    acc = evaluate.accuracy(panel["ret_cc"], pred)
    assert acc["hit_rate"] > 0.6     # silver drives the ETF by construction
    assert np.isfinite(acc["mae_bps"])
