"""Does the mood of the morning's news improve the forecast?

    python scripts/news_test.py --etf SILVERBEES.NS                    # GDELT tone
    python scripts/news_test.py --etf SILVERBEES.NS --scorer finbert   # FinBERT (run spark_score_news.py first)
    python scripts/news_test.py --etf SILVERBEES.NS --scorer both      # side by side
    python scripts/news_test.py --etf SILVERBEES.NS --trusted-only     # GDELT tone, well-known outlets only

Compares, walk-forward and out of sample, on the open-to-close return
(the one you can actually trade from a 09:15 forecast):

    overnight_rule          last night's silver x rupee move   (the baseline)
    <scorer>_only           the five news moods, nothing else
    overnight+<scorer>      both together

Five themes, so signs that differ for silver are kept apart: metals, fed,
dollar, us_data, india. If overnight+news isn't clearly better than the
overnight rule, that news measure adds nothing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import baselines, config, data, evaluate, features  # noqa: E402
from silver_signal import news_features as nfeat  # noqa: E402

SCORE_COL = {"gdelt": "gdelt_tone", "finbert": "fb_score"}


def news_features_for(scorer: str, panel: pd.DataFrame, a) -> pd.DataFrame:
    if scorer == "finbert":
        path = config.DATA_DIR / "news" / "daily_news.parquet"
        if not path.exists():
            sys.exit(f"{path} not found. Run scripts/spark_score_news.py first.")
        daily = pd.read_parquet(path)
        daily.index = pd.DatetimeIndex(daily.index, name="date")
        return daily[nfeat.feature_names("fb_score") + ["news_missing"]]
    heads = nfeat.load_headlines(a.headlines)
    return nfeat.theme_features(heads, panel.index, "gdelt_tone", trusted_only=a.trusted_only)


def models_for(scorer: str) -> dict:
    cols = nfeat.feature_names(SCORE_COL[scorer])
    return {
        f"{scorer}_only": lambda tr, te, tg: baselines._ols(tr, te, tg, cols),
        f"overnight+{scorer}": lambda tr, te, tg: baselines._ols(tr, te, tg, ["driver"] + cols),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etf", default=config.ETF)
    ap.add_argument("--scorer", choices=["gdelt", "finbert", "both"], default="gdelt")
    ap.add_argument("--headlines", type=Path, default=config.DATA_DIR / "news" / "headlines.csv")
    ap.add_argument("--trusted-only", action="store_true", help="GDELT tone from well-known outlets only")
    ap.add_argument("--cost-bps", type=float, default=config.DEFAULT_COST_BPS)
    ap.add_argument("--min-train", type=int, default=120)
    ap.add_argument("--step", type=int, default=20)
    a = ap.parse_args()

    raw = data.load_all(etf=a.etf)
    panel = features.build_panel(raw["etf"], raw["silver"], raw["fx"])
    scorers = ["gdelt", "finbert"] if a.scorer == "both" else [a.scorer]

    df = panel
    for s in scorers:
        f = news_features_for(s, panel, a)
        df = df.join(f.drop(columns=[c for c in f if c in df.columns]), how="inner")
    df = df.dropna(subset=[c for s in scorers for c in nfeat.feature_names(SCORE_COL[s])])
    first = df.index[df["news_missing"] == 0].min()
    df = df[df.index >= first]
    print(f"{a.etf}: {len(df)} trading days with news, {df.index[0].date()} to {df.index[-1].date()}")
    print(f"Days with no headlines (treated as neutral): {int(df['news_missing'].sum())}")

    # 1. A first look: do the moods line up with what the overnight rule got wrong?
    pred_on = evaluate.walk_forward(df, baselines.overnight_rule, "ret_oc", a.min_train, a.step)
    resid = (df["ret_oc"] - pred_on).dropna()
    band = 1.96 / len(resid) ** 0.5
    print("\nCorrelation of each news mood with the overnight rule's mistakes (open-to-close):")
    for s in scorers:
        for c in nfeat.feature_names(SCORE_COL[s]):
            r = df.loc[resid.index, c].rank().corr(resid.rank())
            flag = "  <- outside noise band" if abs(r) > band else ""
            print(f"  {c:<14} {r:+.3f}{flag}")
    print(f"  (with {len(resid)} days, anything inside about +/-{band:.3f} is indistinguishable from zero)")

    # 2. The proper test: forecasts and a backtest, out of sample
    models = {"overnight_rule": baselines.overnight_rule}
    for s in scorers:
        models.update(models_for(s))
    acc, bt = [], []
    for name, model in models.items():
        pred = evaluate.walk_forward(df, model, "ret_oc", a.min_train, a.step)
        acc.append({"model": name, **evaluate.accuracy(df["ret_oc"], pred)})
        stats, _ = evaluate.backtest(df["ret_oc"], pred, a.cost_bps)
        bt.append({"strategy": name, **stats})
    for name, stats in evaluate.benchmarks(df, pred.index, a.cost_bps).items():
        bt.append({"strategy": name, **stats})

    pd.set_option("display.width", 160)
    fmt = lambda x: f"{x:.3f}"  # noqa: E731
    print("\nForecast accuracy on open-to-close (walk-forward, out of sample)")
    print(pd.DataFrame(acc).to_string(index=False, float_format=fmt))
    print(f"\nTrading: buy at open, sell at close when the forecast beats {a.cost_bps:g} bps")
    print(pd.DataFrame(bt).to_string(index=False, float_format=fmt))

    out = config.RESULTS_DIR / f"news_{a.scorer}_{a.etf.split('.')[0].lower()}"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(acc).to_csv(out / "accuracy.csv", index=False)
    pd.DataFrame(bt).to_csv(out / "backtest.csv", index=False)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
