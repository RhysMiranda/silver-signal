"""Paper-trade today's session (or backfill), without Airflow.

    python scripts/paper_trade.py --etf SILVERBEES.NS --dry-run            # print, save nothing
    python scripts/paper_trade.py --etf SILVERBEES.NS --refresh            # fetch, trade today, save to MongoDB
    python scripts/paper_trade.py --etf SILVERBEES.NS --days 60            # backfill the last 60 sessions

Saves to MONGODB_URI (default mongodb://localhost:27017).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import config, pipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etf", default=config.ETF)
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--refresh", action="store_true", help="download fresh prices first")
    ap.add_argument("--dry-run", action="store_true", help="print records, don't save")
    a = ap.parse_args()

    if a.refresh:
        pipeline.fetch(a.etf)
    recs = pipeline.trade(a.etf, a.days, save=not a.dry_run)
    if not recs:
        sys.exit("No sessions to record (not enough history, or no data for those days).")
    pipeline.show(recs)
    print("\nRunning totals" + (" (these records only)" if a.dry_run else " (everything in MongoDB)") + ":")
    pipeline.report(recs if a.dry_run else None)


if __name__ == "__main__":
    main()
