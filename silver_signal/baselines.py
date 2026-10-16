"""Boring models that anything fancier has to beat.

Each model has the signature  model(train, test, target) -> pd.Series
of predicted returns for the rows of `test`, fitted only on `train`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def zero(train, test, target):
    """Predict no change. The bar for error metrics; has no direction."""
    return pd.Series(0.0, index=test.index)


def historical_mean(train, test, target):
    """Predict the average return seen so far (roughly 'always up' in a rising market)."""
    return pd.Series(train[target].mean(), index=test.index)


def yesterday(train, test, target):
    """Momentum: predict that today repeats yesterday's close-to-close return."""
    return test["prev_ret_cc"].copy()


def _ols(train: pd.DataFrame, test: pd.DataFrame, target: str, cols: list[str]) -> pd.Series:
    X = np.column_stack([np.ones(len(train))] + [train[c].to_numpy() for c in cols])
    beta, *_ = np.linalg.lstsq(X, train[target].to_numpy(), rcond=None)
    Xt = np.column_stack([np.ones(len(test))] + [test[c].to_numpy() for c in cols])
    return pd.Series(Xt @ beta, index=test.index)


def overnight_rule(train, test, target):
    """Today's move ~ last night's silver move x the rupee move (fitted slope + intercept)."""
    return _ols(train, test, target, ["driver"])


def gap_rule(train, test, target):
    """For ret_oc only: does the day continue or reverse its opening gap?"""
    return _ols(train, test, target, ["gap"])


BASELINES = {
    "zero": zero,
    "historical_mean": historical_mean,
    "yesterday": yesterday,
    "overnight_rule": overnight_rule,
}
