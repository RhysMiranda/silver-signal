import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import live, store, synthetic  # noqa: E402


def _raw():
    return synthetic.make(end="2023-12-31")


def test_record_ignores_the_future():
    raw = _raw()
    day = raw["etf"].index[300]
    base = live.record_for(day, raw, None)
    later = {k: v.copy() for k, v in raw.items()}
    for k in later:
        later[k].loc[later[k].index > day + pd.Timedelta(days=1), "close"] *= 2
    after = live.record_for(day, later, None)
    assert base["pred_ret_oc"] == after["pred_ret_oc"]
    assert base["trained_through"] < base["date"]


def test_pnl_follows_the_signal():
    raw = _raw()
    recs = [live.record_for(d, raw, None) for d in raw["etf"].index[200:260]]
    recs = [r for r in recs if r]
    for r in recs:
        c = r["cost_bps"] / 1e4
        assert abs(r["pnl_buy_0915"] - (r["ret_oc"] - c)) < 1e-12
        assert r["pnl_overnight_rule"] == (r["pnl_buy_0915"] if r["overnight_rule_buys"] else 0.0)
    s = live.summary(recs)
    assert s["sessions"] == len(recs) and s["wait_1015_total"] is None


def test_too_little_history_gives_none():
    raw = _raw()
    assert live.record_for(raw["etf"].index[10], raw, None) is None


class FakeColl:
    def __init__(self):
        self.docs = {}

    def replace_one(self, flt, doc, upsert):
        self.docs[flt["_id"]] = doc

    def find(self, flt, sort):
        return sorted(self.docs.values(), key=lambda d: d["date"])


def test_upsert_is_idempotent():
    c = FakeColl()
    r = {"_id": "2024-01-02", "date": "2024-01-02", "x": 1}
    store.upsert([r], c)
    store.upsert([{**r, "x": 2}], c)
    assert store.all_records(c) == [{**r, "x": 2}]
