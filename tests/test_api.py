import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
pytest.importorskip("fastapi")
mongomock = pytest.importorskip("mongomock")

from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402


def _rec(date, pnl, gap):
    return {"_id": date, "date": date, "pnl_overnight_rule": pnl, "pnl_buy_0915": pnl,
            "pnl_wait_1015": None, "gap_first_hour": gap}


def test_endpoints():
    c = mongomock.MongoClient().db.paper_trades
    c.insert_many([_rec("2026-01-02", 0.01, -0.001), _rec("2026-01-05", -0.02, None)])
    main._coll = c
    client = TestClient(main.app)
    assert client.get("/health").json() == {"ok": True}
    s = client.get("/summary").json()
    assert s["sessions"] == 2 and abs(s["buy_0915_total"] - (1.01 * 0.98 - 1)) < 1e-12
    assert [r["date"] for r in client.get("/trades").json()] == ["2026-01-02", "2026-01-05"]
    eq = client.get("/equity").json()
    assert abs(eq[-1]["buy_0915"] - 1.01 * 0.98) < 1e-12 and eq[-1]["wait_1015"] == 1.0
