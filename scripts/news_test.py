"""First news test: does the mood of the morning's news improve the forecast?

    python scripts/news_test.py                        # HDFC Silver ETF
    python scripts/news_test.py --etf SILVERBEES.NS    # longer price history
    python scripts/news_test.py --trusted-only         # only well-known outlets

Compares, walk-forward and out of sample, on the open-to-close return
(the one you can actually trade from a 09:15 forecast):

    overnight_rule   last night's silver x rupee move           (the baseline)
    news_only        the three news moods, nothing else
    overnight+news   both together

If overnight+news isn't clearly better than overnight_rule, the news (as measured
by GDELT's tone) adds nothing. That is a real, reportable result.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from silver_signal import baselines, config, data, evaluate, features  # noqa: E402
from silver_signal import news_features as nfeat  # noqa: E402

NEWS = ["tone_metals", "tone_us", "tone_india"]


def news_only(train, test, target):
    return baselines._ols(train, test, target, NEWS)


def overnight_plus_news(train, test, target):
    return baselines._ols(train, test, target, ["driver"] + NEWS)


MODELS = {
    "overnight_rule": baselines.overnight_rule,
    "news_only": news_only,
    "overnight+news": overnight_plus_news,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etf", default=config.ETF)
    ap.add_argument("--headlines", type=Path, default=config.DATA_DIR / "news" / "headlines.csv")
    ap.add_argument("--trusted-only", action="store_true")
    ap.add_argument("--cost-bps", type=float, default=config.DEFAULT_COST_BPS)
    ap.add_argument("--min-train", type=int, default=120)
    ap.add_argument("--step", type=int, default=20)
    a = ap.parse_args()

    raw = data.load_all(etf=a.etf)
    panel = features.build_panel(raw["etf"], raw["silver"], raw["fx"])
    heads = nfeat.load_headlines(a.headlines)
    feats = nfeat.tone_features(heads, panel.index, trusted_only=a.trusted_only)
    df = panel.join(feats)
    df = df[df.index >= heads["published_utc"].min().tz_localize(None).normalize()]
    print(f"{a.etf}: {len(df)} trading days with news, {df.index[0].date()} to {df.index[-1].date()}")
    print(f"Days with no headlines (treated as neutral): {int(df['news_missing'].sum())}")

    # 1. A first look: do the moods line up with what the overnight rule got wrong?
    pred_on = evaluate.walk_forward(df, baselines.overnight_rule, "ret_oc", a.min_train, a.step)
    resid = (df["ret_oc"] - pred_on).dropna()
    print("\nCorrelation of each news mood with the overnight rule's mistakes (open-to-close):")
    for c in NEWS:
        r = df.loc[resid.index, c].rank().corr(resid.rank())
        print(f"  {c:<12} {r:+.3f}")
    band = 1.96 / len(resid) ** 0.5
    print(f"  (with {len(resid)} days, anything inside about +/-{band:.3f} is indistinguishable from zero)")

    # 2. The proper test: forecasts and a backtest, out of sample
    acc, bt = [], []
    for name, model in MODELS.items():
        pred = evaluate.walk_forward(df, model, "ret_oc", a.min_train, a.step)
        acc.append({"model": name, **evaluate.accuracy(df["ret_oc"], pred)})
        stats, _ = evaluate.backtest(df["ret_oc"], pred, a.cost_bps)
        bt.append({"strategy": name, **stats})
    idx = pred.index
    for name, stats in evaluate.benchmarks(df, idx, a.cost_bps).items():
        bt.append({"strategy": name, **stats})

    pd.set_option("display.width", 160)
    fmt = lambda x: f"{x:.3f}"  # noqa: E731
    print("\nForecast accuracy on open-to-close (walk-forward, out of sample)")
    print(pd.DataFrame(acc).to_string(index=False, float_format=fmt))
    print(f"\nTrading: buy at open, sell at close when the forecast beats {a.cost_bps:g} bps")
    print(pd.DataFrame(bt).to_string(index=False, float_format=fmt))

    out = config.RESULTS_DIR / ("news_" + a.etf.split(".")[0].lower())
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(acc).to_csv(out / "accuracy.csv", index=False)
    pd.DataFrame(bt).to_csv(out / "backtest.csv", index=False)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
