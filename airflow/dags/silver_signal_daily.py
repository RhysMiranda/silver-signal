"""Airflow DAG: fetch prices, paper-trade the session, report running totals.

Runs at 16:15 IST on weekdays, 45 minutes after NSE closes. NSE holidays just
produce no new record (there's no session to trade).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, os.environ.get("SILVER_SIGNAL_HOME", "/opt/silver-signal"))

ETF = os.environ.get("SILVER_SIGNAL_ETF", "SILVERBEES.NS")


def _fetch():
    from silver_signal import pipeline
    pipeline.fetch(ETF)


def _trade():
    from silver_signal import pipeline
    recs = pipeline.trade(ETF, days=3)   # last 3 sessions: fills a missed day, upserts are idempotent
    pipeline.show(recs)


def _report():
    from silver_signal import pipeline
    pipeline.report()


with DAG(
    dag_id="silver_signal_daily",
    start_date=datetime(2026, 10, 1),
    schedule="45 10 * * 1-5",          # 10:45 UTC = 16:15 IST
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["silver-signal"],
) as dag:
    fetch = PythonOperator(task_id="fetch_prices", python_callable=_fetch)
    trade = PythonOperator(task_id="paper_trade", python_callable=_trade)
    report = PythonOperator(task_id="report", python_callable=_report)
    fetch >> trade >> report
