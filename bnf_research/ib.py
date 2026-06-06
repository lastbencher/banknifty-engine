from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from bnf_research.session import SessionMeta
from bnf_research.utils import minutes_between, safe_divide


def ib_levels(meta: SessionMeta) -> dict[str, float]:
    if not meta.has_ib or meta.ib_bars.empty:
        return {
            "ib_high": np.nan,
            "ib_low": np.nan,
            "ib_mid": np.nan,
            "ib_range": np.nan,
        }

    ib_high = float(meta.ib_bars["high"].max())
    ib_low = float(meta.ib_bars["low"].min())
    ib_mid = (ib_high + ib_low) / 2
    return {
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_mid": ib_mid,
        "ib_range": ib_high - ib_low,
    }


def find_first_break(meta: SessionMeta, ib_high: float, ib_low: float) -> dict[str, Any]:
    if meta.after_ib.empty:
        return _empty_break()

    for pos in range(len(meta.after_ib)):
        row = meta.after_ib.iloc[pos]
        abs_pos = int(meta.after_ib.index[pos])

        if row["high"] > ib_high:
            return {
                "direction": "HIGH",
                "pos": abs_pos,
                "time": row["datetime"],
                "price": row["high"],
                "level": ib_high,
            }

        if row["low"] < ib_low:
            return {
                "direction": "LOW",
                "pos": abs_pos,
                "time": row["datetime"],
                "price": row["low"],
                "level": ib_low,
            }

    return _empty_break()


def find_opposite_break(
    meta: SessionMeta,
    first_break: dict[str, Any],
    ib_high: float,
    ib_low: float,
) -> dict[str, Any]:
    if first_break["pos"] is None:
        return _empty_opposite()

    start_idx = meta.day.index.get_loc(first_break["pos"])
    for abs_pos in range(start_idx, len(meta.day)):
        row = meta.day.iloc[abs_pos]

        if first_break["direction"] == "HIGH" and row["low"] < ib_low:
            return {
                "occurred": True,
                "pos": abs_pos,
                "time": row["datetime"],
                "price": row["low"],
                "level": ib_low,
            }

        if first_break["direction"] == "LOW" and row["high"] > ib_high:
            return {
                "occurred": True,
                "pos": abs_pos,
                "time": row["datetime"],
                "price": row["high"],
                "level": ib_high,
            }

    return _empty_opposite()


def threshold_hit(
    day: pd.DataFrame,
    start_pos: int | None,
    anchor_price: float,
    direction: str | None,
    threshold: float,
) -> dict[str, Any]:
    if start_pos is None or direction is None or pd.isna(anchor_price):
        return _empty_hit()

    max_adverse = 0.0
    start_idx = day.index.get_loc(start_pos) if start_pos in day.index else start_pos

    for abs_pos in range(start_idx, len(day)):
        row = day.iloc[abs_pos]

        if direction == "HIGH":
            max_adverse = max(max_adverse, anchor_price - row["low"])
            if row["high"] >= anchor_price + threshold:
                return {
                    "hit": True,
                    "pos": abs_pos,
                    "time": row["datetime"],
                    "price": row["high"],
                    "move_points": row["high"] - anchor_price,
                    "max_adverse_before_event": max_adverse,
                }

        if direction == "LOW":
            max_adverse = max(max_adverse, row["high"] - anchor_price)
            if row["low"] <= anchor_price - threshold:
                return {
                    "hit": True,
                    "pos": abs_pos,
                    "time": row["datetime"],
                    "price": row["low"],
                    "move_points": anchor_price - row["low"],
                    "max_adverse_before_event": max_adverse,
                }

    return {**_empty_hit(), "max_adverse_before_event": max_adverse}


def favorable_excursion(
    day: pd.DataFrame,
    first_break: dict[str, Any],
    ib_high: float,
    ib_low: float,
) -> dict[str, Any]:
    if first_break["pos"] is None:
        return {
            "mfe_points": np.nan,
            "mfe_pos": None,
            "mfe_time": pd.NaT,
            "mae_points": np.nan,
            "time_to_mfe": np.nan,
        }

    start_idx = day.index.get_loc(first_break["pos"])
    trade = day.iloc[start_idx:]

    if first_break["direction"] == "HIGH":
        high_pos = trade["high"].idxmax()
        low_value = trade["low"].min()
        return {
            "mfe_points": day.loc[high_pos, "high"] - ib_high,
            "mfe_pos": int(day.index.get_loc(high_pos)),
            "mfe_time": day.loc[high_pos, "datetime"],
            "mae_points": max(0.0, ib_high - low_value),
            "time_to_mfe": minutes_between(first_break["time"], day.loc[high_pos, "datetime"]),
        }

    low_pos = trade["low"].idxmin()
    high_value = trade["high"].max()
    return {
        "mfe_points": ib_low - day.loc[low_pos, "low"],
        "mfe_pos": int(day.index.get_loc(low_pos)),
        "mfe_time": day.loc[low_pos, "datetime"],
        "mae_points": max(0.0, high_value - ib_low),
        "time_to_mfe": minutes_between(first_break["time"], day.loc[low_pos, "datetime"]),
    }


def post_break_acceptance(
    day: pd.DataFrame,
    first_break: dict[str, Any],
    ib_high: float,
    ib_low: float,
    ib_mid: float,
) -> dict[str, Any]:
    if first_break["pos"] is None:
        return {
            "returned_inside_ib": False,
            "crossed_ib_mid_after_break": False,
            "minutes_outside_after_break": 0,
        }

    returned_inside = False
    crossed_mid = False
    minutes_outside = 0
    start_idx = day.index.get_loc(first_break["pos"])

    for abs_pos in range(start_idx, len(day)):
        row = day.iloc[abs_pos]

        if first_break["direction"] == "HIGH":
            if row["low"] <= ib_mid:
                crossed_mid = True
            if row["close"] <= ib_high:
                returned_inside = True
                break
            minutes_outside += 1
        else:
            if row["high"] >= ib_mid:
                crossed_mid = True
            if row["close"] >= ib_low:
                returned_inside = True
                break
            minutes_outside += 1

    return {
        "returned_inside_ib": returned_inside,
        "crossed_ib_mid_after_break": crossed_mid,
        "minutes_outside_after_break": minutes_outside,
    }


def _empty_break() -> dict[str, Any]:
    return {
        "direction": None,
        "pos": None,
        "time": pd.NaT,
        "price": np.nan,
        "level": np.nan,
    }


def _empty_opposite() -> dict[str, Any]:
    return {
        "occurred": False,
        "pos": None,
        "time": pd.NaT,
        "price": np.nan,
        "level": np.nan,
    }


def _empty_hit() -> dict[str, Any]:
    return {
        "hit": False,
        "pos": None,
        "time": pd.NaT,
        "price": np.nan,
        "move_points": np.nan,
        "max_adverse_before_event": np.nan,
    }
