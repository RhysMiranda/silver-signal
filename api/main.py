"""Read-only API over the paper-trading records in MongoDB.

    uvicorn api.main:app --reload            # from the repo root
    GET /health      is the database reachable
    GET /summary     running totals per strategy
    GET /trades      every record, oldest first
    GET /equity      cumulative growth of 1 rupee per strategy, plus the 20-day first-hour gap

Set MONGODB_URI (default mongodb://localhost:27017) and, for a hosted dashboard,
CORS_ORIGINS (comma-separated, default *).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import live, store  # noqa: E402

STRATEGIES = ("overnight_rule", "buy_0915", "wait_1015")

app = FastAPI(title="silver-signal", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["GET"], allow_headers=["*"])

_coll = None


def coll():
    global _coll
    if _coll is None:
        _coll = store.collection()
    return _coll


def records() -> list[dict]:
    try:
        return store.all_records(coll())
    except Exception as e:
        raise HTTPException(503, f"database unavailable: {type(e).__name__}") from e


def _jsonable(df: pd.DataFrame) -> list[dict]:
    return df.replace({np.nan: None}).to_dict(orient="records")


@app.get("/")
def index():
    return {"name": "silver-signal", "endpoints": ["/summary", "/trades", "/equity", "/health", "/docs"]}


@app.get("/health")
def health():
    try:
        coll().database.client.admin.command("ping")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(503, f"database unavailable: {type(e).__name__}") from e


@app.get("/summary")
def summary():
    return live.summary(records())


@app.get("/trades")
def trades(limit: int | None = None):
    recs = records()
    return recs[-limit:] if limit else recs


@app.get("/equity")
def equity():
    recs = records()
    if not recs:
        return []
    df = pd.DataFrame(recs).sort_values("date").set_index("date")
    out = pd.DataFrame(index=df.index)
    for s in STRATEGIES:
        out[s] = (1 + df[f"pnl_{s}"].astype(float).fillna(0.0)).cumprod()
    out["gap_bps_20d"] = df["gap_first_hour"].astype(float).rolling(20, min_periods=5).mean() * 1e4
    return _jsonable(out.reset_index())
