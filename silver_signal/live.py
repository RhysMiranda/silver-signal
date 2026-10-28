"""Daily paper trading: one record per trading session, built only from what was
knowable when each decision was made.

Three paper strategies, all long-or-flat, costs included:
  overnight_rule  at 09:15, buy if last night's silver x rupee forecast beats the cost
  buy_0915        buy every day at 09:15 (the benchmark the research says loses)
  wait_1015       buy every day at 10:15 instead (the research says this was better,
                  but the edge faded in 2026; this tracks whether it comes back)
Each sells at the 15:30 close. The record also keeps the first-hour gap
(ETF minus silver, 09:15-10:15), the number to watch.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import baselines, config, features, intraday

MIN_TRAIN = 120


def _clean(x):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return float(x)


def record_for(day: pd.Timestamp, raw: dict, hourly: dict | None,
               cost_bps: float = config.DEFAULT_COST_BPS) -> dict | None:
    """Paper-trading record for one session, or None if there's no data for it.

    `raw` is data.load_all()'s output; `hourly` has etf/silver/fx hourly bars
    (optional: without it the 10:15 fields are None). The forecast model is
    fitted only on sessions before `day`.
    """
    panel = features.build_panel(raw["etf"], raw["silver"], raw["fx"])
    day = pd.Timestamp(day).normalize()
    if day not in panel.index:
        return None
    train = panel[panel.index < day].dropna(subset=["driver", "ret_oc"])
    if len(train) < MIN_TRAIN:
        return None
    row = panel.loc[[day]]
    pred = float(baselines.overnight_rule(train, row, "ret_oc").iloc[0])
    cost = cost_bps / 1e4
    ret_oc = float(row["ret_oc"].iloc[0])
    buy = pred > cost

    rec = {
        "_id": day.strftime("%Y-%m-%d"),
        "date": day.strftime("%Y-%m-%d"),
        "etf": config.ETF,
        "pred_ret_oc": pred,
        "overnight_rule_buys": bool(buy),
        "ret_oc": ret_oc,
        "pnl_overnight_rule": (ret_oc - cost) if buy else 0.0,
        "pnl_buy_0915": ret_oc - cost,
        "trained_on_sessions": len(train),
        "trained_through": train.index.max().strftime("%Y-%m-%d"),
        "cost_bps": cost_bps,
        "etf_first_hour": None, "etf_rest": None, "gap_first_hour": None,
        "open_premium": None, "pnl_wait_1015": None,
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if hourly:
        etf = raw["etf"].loc[[day]]
        d = intraday.build(raw["etf"], hourly["silver"], hourly["fx"])
        d = d.loc[d.index == day]
        if len(d):
            d = intraday.build_1015(d, etf, hourly["etf"], hourly["silver"], hourly["fx"])
        if len(d):
            r = d.iloc[0]
            rec.update(etf_first_hour=_clean(r["etf_first_hour"]), etf_rest=_clean(r["etf_rest"]),
                       gap_first_hour=_clean(r["gap_first_hour"]), open_premium=_clean(r["open_premium"]),
                       pnl_wait_1015=_clean(r["etf_rest"] - cost))
    return {k: (_clean(v) if isinstance(v, (float, np.floating)) else v) for k, v in rec.items()}


def summary(records: list[dict]) -> dict:
    """Running totals across all paper-trading records."""
    if not records:
        return {"sessions": 0}
    df = pd.DataFrame(records).sort_values("date")
    out = {"sessions": len(df), "from": df["date"].iloc[0], "to": df["date"].iloc[-1]}
    for s in ("overnight_rule", "buy_0915", "wait_1015"):
        p = df[f"pnl_{s}"].dropna().astype(float)
        out[f"{s}_total"] = float(np.expm1(np.log1p(p).sum())) if len(p) else None
        out[f"{s}_days"] = int(len(p))
    g = df["gap_first_hour"].dropna().astype(float)
    out["first_hour_gap_bps_last20"] = float(g.tail(20).mean() * 1e4) if len(g) else None
    out["first_hour_gap_bps_all"] = float(g.mean() * 1e4) if len(g) else None
    return out
