"""Where paper-trading records live: MongoDB (Atlas or the local container).

Set MONGODB_URI, e.g. mongodb+srv://user:pass@cluster.xxxxx.mongodb.net/
Default: mongodb://localhost:27017 (the `mongo` service in docker-compose.yml).
Records are upserted by date, so re-running a day overwrites it instead of
duplicating it.
"""
from __future__ import annotations

import os

DB = os.environ.get("MONGODB_DB", "silver_signal")
COLLECTION = "paper_trades"


def collection(uri: str | None = None):
    from pymongo import MongoClient

    uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    return client[DB][COLLECTION]


def upsert(records: list[dict], coll=None) -> int:
    coll = coll if coll is not None else collection()
    for r in records:
        coll.replace_one({"_id": r["_id"]}, r, upsert=True)
    return len(records)


def all_records(coll=None) -> list[dict]:
    coll = coll if coll is not None else collection()
    return list(coll.find({}, sort=[("date", 1)]))
