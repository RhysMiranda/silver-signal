"""Score the baselines on HDFC Silver ETF with walk-forward evaluation.

    python scripts/run_baselines.py              # real data from Yahoo Finance
    python scripts/run_baselines.py --refresh    # re-download first
    python scripts/run_baselines.py --synthetic  # fake data, no network needed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import baselines, config, data, evaluate, features, synthetic  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true", help="use fake data (no network)")
    ap.add_argument("--refresh", action="store_true", help="re-download prices")
    ap.add_argument("--etf", default=config.ETF,
                    help="Yahoo symbol of the silver ETF, e.g. SILVERBEES.NS for a longer history")
    ap.add_argument("--cost-bps", type=float, default=config.DEFAULT_COST_BPS,
                    help="round-trip cost in basis points")
    ap.add_argument("--min-train", type=int, default=120, help="days before the first forecast")
    ap.add_argument("--step", type=int, default=20, help="days predicted per refit")
    args = ap.parse_args()

    raw = synthetic.make() if args.synthetic else data.load_all(refresh=args.refresh, etf=args.etf)
    panel = features.build_panel(raw["etf"], raw["silver"], raw["fx"])
    print(f"{len(panel)} trading days, {panel.index[0].date()} to {panel.index[-1].date()}"
          + ("  [SYNTHETIC]" if args.synthetic else ""))

    acc_rows, bt_rows, preds = [], [], {}
    for target in ("ret_cc", "ret_oc"):
        models = dict(baselines.BASELINES)
        if target == "ret_oc":
            models["gap_rule"] = baselines.gap_rule
        for name, model in models.items():
            pred = evaluate.walk_forward(panel, model, target, args.min_train, args.step)
            preds[f"{target}:{name}"] = pred
            acc_rows.append({"target": target, "model": name,
                             **evaluate.accuracy(panel[target], pred)})
            if target == "ret_oc" and name != "zero":
                stats, _ = evaluate.backtest(panel["ret_oc"], pred, args.cost_bps)
                bt_rows.append({"strategy": name, **stats})

    idx = next(iter(preds.values())).index
    for name, stats in evaluate.benchmarks(panel, idx, args.cost_bps).items():
        bt_rows.append({"strategy": name, **stats})

    acc = pd.DataFrame(acc_rows)
    bt = pd.DataFrame(bt_rows)
    pd.set_option("display.width", 160)
    print("\nForecast accuracy (walk-forward, out of sample)")
    print(acc.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(f"\nTrading ret_oc: buy at open, sell at close, {args.cost_bps:g} bps round trip")
    print(bt.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    out = config.RESULTS_DIR / ("synthetic" if args.synthetic else "real_" + args.etf.split(".")[0].lower())
    out.mkdir(parents=True, exist_ok=True)
    acc.to_csv(out / "accuracy.csv", index=False)
    bt.to_csv(out / "backtest.csv", index=False)
    pd.DataFrame(preds).join(panel[["ret_cc", "ret_oc"]]).to_csv(out / "predictions.csv")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
