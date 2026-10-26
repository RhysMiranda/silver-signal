"""Find out why FinBERT crashes inside Spark, one step at a time.

    python scripts/finbert_doctor.py

Tries FinBERT alone, then Spark in a few configurations, and prints a summary
plus any crash output the Spark workers wrote to data/logs/.
"""
from __future__ import annotations

import faulthandler
import os
import platform
import sys
import time
from pathlib import Path

faulthandler.enable()
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def step(msg):
    print(f"\n== {msg}", flush=True)


def memory_gb():
    try:
        import psutil
        vm = psutil.virtual_memory()
        return vm.total / 2**30, vm.available / 2**30
    except ImportError:
        pass
    if platform.system() == "Windows":
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                        ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong),
                        ("ae", ctypes.c_ulonglong)]
        m = MS(); m.len = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.total / 2**30, m.avail / 2**30
    return float("nan"), float("nan")


def main():
    step("Machine")
    tot, av = memory_gb()
    print(f"Python {sys.version.split()[0]} on {platform.platform()}, {os.cpu_count()} CPUs, "
          f"RAM {tot:.1f} GB total / {av:.1f} GB free")
    import numpy, pandas, pyarrow, torch, transformers, pyspark
    print(f"numpy {numpy.__version__}, pandas {pandas.__version__}, pyarrow {pyarrow.__version__}, "
          f"torch {torch.__version__}, transformers {transformers.__version__}, pyspark {pyspark.__version__}")
    print("OK")

    import pandas as pd
    from silver_signal import data, finbert, spark_news
    from silver_signal import news_features as nfeat
    heads = nfeat.load_headlines(ROOT / "data" / "news" / "headlines.csv").sort_values("published_utc")
    sessions = data.load_all(etf="SILVERBEES.NS")["etf"].index
    small = heads.head(200)
    logs = ROOT / "data" / "logs"
    results = {}

    def attempt(name, fn):
        step(name)
        t = time.time()
        try:
            fn()
            results[name] = f"OK ({time.time()-t:.0f}s)"
        except Exception as e:  # keep going so one run tells us everything
            results[name] = f"FAILED: {type(e).__name__}: {str(e).splitlines()[0][:150]}"
        print(results[name], flush=True)

    def plain():
        m = finbert.FinBert(threads=1)
        titles = heads.head(2000)["title"].astype(str).tolist()
        for i in range(0, len(titles), 500):
            m.probs(titles[i:i + 500])
            print(f"  scored {i + 500} of {len(titles)}", flush=True)

    log_env = {"SILVER_SIGNAL_WORKER_LOG": "1"}
    attempt("1. FinBERT in plain Python on the first 2,000 real headlines", plain)
    attempt("2. Spark, keyword scorer (no torch in workers)",
            lambda: spark_news.run(small, sessions, "keyword", 1, 2))
    attempt("3. Spark, FinBERT, 1 worker (as now)",
            lambda: spark_news.run(small, sessions, "finbert", 1, 2, env=log_env))
    attempt("4. Spark, FinBERT, 1 worker, fresh Python per task",
            lambda: spark_news.run(small, sessions, "finbert", 1, 2,
                                   conf={"spark.python.worker.reuse": "false"}, env=log_env))
    attempt("5. Spark, FinBERT, 1 worker, OpenMP clash workaround",
            lambda: spark_news.run(small, sessions, "finbert", 1, 2,
                                   env={**log_env, "KMP_DUPLICATE_LIB_OK": "TRUE",
                                        "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}))
    attempt("6. Spark, FinBERT, 1 worker, small Arrow batches",
            lambda: spark_news.run(small, sessions, "finbert", 1, 2, env=log_env,
                                   conf={"spark.sql.execution.arrow.maxRecordsPerBatch": "32"}))

    print("\n== Summary")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("\n== Worker logs")
    for f in sorted(logs.glob("worker_*.log")) if logs.exists() else []:
        txt = f.read_text(errors="replace").strip()
        print(f"--- {f.name}\n{txt[-3000:]}")

if __name__ == "__main__":
    main()
