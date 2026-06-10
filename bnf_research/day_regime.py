"""Session regime taxonomy — wild trend, choppy, boring (no IB)."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# Regime labels
WILD_TREND = "WILD_TREND"
TREND = "TREND"
CHOPPY = "CHOPPY"
BORING = "BORING"
UNKNOWN = "UNKNOWN"


def session_metrics(day: pd.DataFrame) -> dict[str, Any]:
    """Core price-action metrics for one session (minute bars)."""
    if day.empty or len(day) < 30:
        return {}

    day = day.sort_values("datetime")
    o = float(day.iloc[0]["open"])
    c = float(day.iloc[-1]["close"])
    hi = float(day["high"].max())
    lo = float(day["low"].min())
    rng = hi - lo
    if rng <= 0:
        return {}

    net = c - o
    efficiency = abs(net) / rng
    open_pos = (o - lo) / rng
    close_pos = (c - lo) / rng

    # 5-min resample for direction changes
    bars = day.set_index("datetime").resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna(subset=["close"])
    bar_dir = np.sign(bars["close"].diff()).fillna(0)
    direction_changes = int((bar_dir.diff().abs() > 0).sum()) - 1
    direction_changes = max(0, direction_changes)

    # Swing count: close crosses session VWAP proxy (mid) repeatedly
    mid = (hi + lo) / 2
    above = (day["close"] > mid).astype(int)
    mid_crosses = int((above.diff().abs() > 0).sum())

    has_vol = "volume" in day.columns and day["volume"].sum() > 0
    total_vol = int(day["volume"].sum()) if has_vol else 0
    oi_delta = int(day["oi"].iloc[-1] - day["oi"].iloc[0]) if has_vol and "oi" in day.columns else 0

    return {
        "day_open": o,
        "day_close": c,
        "day_high": hi,
        "day_low": lo,
        "day_range": rng,
        "net_move": net,
        "abs_net_move": abs(net),
        "efficiency": efficiency,
        "open_pos": open_pos,
        "close_pos": close_pos,
        "direction_changes_5m": direction_changes,
        "mid_crosses": mid_crosses,
        "total_volume": total_vol,
        "oi_session_delta": oi_delta,
        "trend_up": net > 0,
    }


def classify_regime(
    metrics: dict[str, Any],
    *,
    range_p25: float,
    range_p50: float,
    range_p75: float,
    chop_changes_p75: float,
) -> str:
    """
    Four-way regime from session metrics + rolling context thresholds.

    WILD_TREND  huge range + strong one-way efficiency
    TREND       directional day, moderate+ range
    CHOPPY      wide range but low efficiency / many reversals
    BORING      tight range
    """
    if not metrics:
        return UNKNOWN

    rng = metrics["day_range"]
    eff = metrics["efficiency"]
    changes = metrics["direction_changes_5m"]
    open_pos = metrics["open_pos"]
    close_pos = metrics["close_pos"]

    if rng <= range_p25:
        return BORING

    extreme_open = open_pos <= 0.25 or open_pos >= 0.75
    extreme_close = close_pos <= 0.25 or close_pos >= 0.75
    one_way = extreme_open and extreme_close and ((open_pos <= 0.25 and close_pos >= 0.75) or (open_pos >= 0.75 and close_pos <= 0.25))

    if rng >= range_p75 and eff >= 0.55 and one_way:
        return WILD_TREND

    if rng >= range_p75 and eff >= 0.45 and (close_pos >= 0.70 or close_pos <= 0.30):
        return WILD_TREND

    if eff >= 0.40 and rng >= range_p50:
        return TREND

    if changes >= chop_changes_p75 or (eff < 0.28 and rng >= range_p50):
        return CHOPPY

    if rng >= range_p50 and eff < 0.35:
        return CHOPPY

    return TREND if eff >= 0.35 else BORING


def label_all_sessions(
    df: pd.DataFrame,
    *,
    rolling_window: int = 252,
) -> pd.DataFrame:
    """Label each session with metrics + regime (thresholds from trailing window)."""
    from bnf_research.market_profile import prepare_day_frame

    prep = prepare_day_frame(df)
    rows: list[dict[str, Any]] = []
    dates = sorted(prep["date"].unique())

    history_ranges: list[float] = []
    history_changes: list[int] = []

    for d in dates:
        day = prep[prep["date"] == d]
        m = session_metrics(day)
        if not m:
            continue

        # trailing thresholds (no look-ahead)
        if len(history_ranges) >= 20:
            r_s = pd.Series(history_ranges[-rolling_window:])
            c_s = pd.Series(history_changes[-rolling_window:])
            range_p25 = float(r_s.quantile(0.25))
            range_p50 = float(r_s.quantile(0.50))
            range_p75 = float(r_s.quantile(0.75))
            chop_p75 = float(c_s.quantile(0.75))
        else:
            range_p25 = range_p50 = range_p75 = m["day_range"]
            chop_p75 = m["direction_changes_5m"]

        regime = classify_regime(
            m,
            range_p25=range_p25,
            range_p50=range_p50,
            range_p75=range_p75,
            chop_changes_p75=chop_p75,
        )

        rows.append(
            {
                "date": d,
                "regime": regime,
                **m,
                "range_p25": range_p25,
                "range_p50": range_p50,
                "range_p75": range_p75,
            }
        )
        history_ranges.append(m["day_range"])
        history_changes.append(m["direction_changes_5m"])

    return pd.DataFrame(rows)


def latest_session_label(df: pd.DataFrame, *, rolling_window: int = 252) -> dict[str, Any]:
    """Fast path: label only the most recent session (for Telegram /regime)."""
    from bnf_research.market_profile import prepare_day_frame

    prep = prepare_day_frame(df)
    dates = sorted(prep["date"].unique())
    if not dates:
        return {}

    tail = dates[-rolling_window:]
    history: list[dict[str, Any]] = []
    for d in tail[:-1]:
        m = session_metrics(prep[prep["date"] == d])
        if m:
            history.append(m)

    last_date = tail[-1]
    m = session_metrics(prep[prep["date"] == last_date])
    if not m:
        return {}

    if len(history) >= 20:
        r_s = pd.Series([h["day_range"] for h in history])
        c_s = pd.Series([h["direction_changes_5m"] for h in history])
        range_p25 = float(r_s.quantile(0.25))
        range_p50 = float(r_s.quantile(0.50))
        range_p75 = float(r_s.quantile(0.75))
        chop_p75 = float(c_s.quantile(0.75))
    else:
        range_p25 = range_p50 = range_p75 = m["day_range"]
        chop_p75 = m["direction_changes_5m"]

    return {
        "date": last_date,
        "regime": classify_regime(
            m,
            range_p25=range_p25,
            range_p50=range_p50,
            range_p75=range_p75,
            chop_changes_p75=chop_p75,
        ),
        **m,
    }
