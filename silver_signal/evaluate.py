"""Walk-forward evaluation, accuracy metrics and a cost-aware backtest."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def walk_forward(df: pd.DataFrame, model, target: str,
                 min_train: int = 120, step: int = 20) -> pd.Series:
    """Fit on everything before a block, predict the block, move forward, repeat.

    The model never sees a row from the block it is predicting.
    """
    if len(df) <= min_train:
        raise ValueError(f"Need more than {min_train} rows, have {len(df)}")
    out = []
    for start in range(min_train, len(df), step):
        train, test = df.iloc[:start], df.iloc[start:start + step]
        out.append(model(train, test, target))
    return pd.concat(out).rename("pred")


def accuracy(y: pd.Series, pred: pd.Series) -> dict:
    """Direction hit rate (with a 95% interval), MAE and rank correlation."""
    y, pred = y.loc[pred.index], pred
    called = (np.sign(pred) != 0) & (y != 0)
    n = int(called.sum())
    if n:
        hit = float((np.sign(pred[called]) == np.sign(y[called])).mean())
        half = 1.96 * math.sqrt(hit * (1 - hit) / n)
    else:
        hit, half = float("nan"), float("nan")
    ic = float(pred.rank().corr(y.rank())) if pred.std() > 0 else float("nan")  # Spearman, no SciPy needed
    return {
        "days": len(pred),
        "direction_calls": n,
        "hit_rate": hit,
        "hit_low": hit - half if n else float("nan"),
        "hit_high": hit + half if n else float("nan"),
        "mae_bps": float((pred - y).abs().mean() * 1e4),
        "rank_corr": ic,
    }


def backtest(ret_oc: pd.Series, pred: pd.Series, cost_bps: float) -> tuple[dict, pd.Series]:
    """Buy at the open and sell at the close on days the forecast beats the cost.

    Long or flat only. Returns summary stats and the daily strategy returns.
    """
    y = ret_oc.loc[pred.index]
    cost = cost_bps / 1e4
    pos = (pred > cost).astype(float)
    daily = pos * y - pos * cost
    return _stats(daily, trades=int(pos.sum())), daily


def _stats(daily: pd.Series, trades: int) -> dict:
    equity = (1 + daily).cumprod()
    years = len(daily) / TRADING_DAYS
    total = float(equity.iloc[-1] - 1) if len(equity) else 0.0
    vol = float(daily.std() * math.sqrt(TRADING_DAYS))
    return {
        "trades": trades,
        "total_return": total,
        "annual_return": (1 + total) ** (1 / years) - 1 if years > 0 else float("nan"),
        "annual_vol": vol,
        "sharpe": float(daily.mean() / daily.std() * math.sqrt(TRADING_DAYS)) if daily.std() > 0 else float("nan"),
        "max_drawdown": float((equity / equity.cummax() - 1).min()) if len(equity) else 0.0,
    }


def benchmarks(panel: pd.DataFrame, index: pd.Index, cost_bps: float) -> dict[str, dict]:
    """What you'd get without a model, over the same days."""
    p = panel.loc[index]
    cost = cost_bps / 1e4
    every_day = p["ret_oc"] - cost
    hold = p["ret_cc"]
    return {
        "buy_every_open": _stats(every_day, trades=len(p)),
        "buy_and_hold": _stats(hold, trades=1),
    }
