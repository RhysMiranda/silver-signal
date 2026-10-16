"""Tickers, market hours and default assumptions in one place."""
from datetime import time
from pathlib import Path

# Yahoo Finance symbols
ETF = "HDFCSILVER.NS"   # HDFC Silver ETF on NSE (listed Sep 2022)
SILVER = "SI=F"         # COMEX silver futures, continuous front month (USD/oz)
USDINR = "INR=X"        # US dollar to Indian rupee

START = "2022-09-01"

# Indian market hours (NSE cash segment)
IST = "Asia/Kolkata"
OPEN_IST = time(9, 15)
CLOSE_IST = time(15, 30)

# Round-trip trading cost in basis points (1 bp = 0.01%).
# Set this to what your broker actually charges plus a realistic bid-ask spread.
DEFAULT_COST_BPS = 10.0

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
