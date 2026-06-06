from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from bnf_research.config import CHECKPOINTS
from bnf_research.session import SessionMeta, slice_to_minute
from bnf_research.utils import (
    classify_era,
    direction_from_points,
    era_flags,
    minutes_between,
    safe_divide,
    to_hour,
)
from bnf_research.wyckoff import failed_break_episodes_in_range, trap_summary


def count_level_tests(window: pd.DataFrame, level: float, side: str) -> int:
    if pd.isna(level) or window.empty:
        return 0

    count = 0
    for _, row in window.iterrows():
        if side == "HIGH" and row["high"] >= level and row["close"] <= level:
            count += 1
        if side == "LOW" and row["low"] <= level and row["close"] >= level:
            count += 1
    return count


def build_checkpoint_rows(meta: SessionMeta, daily_row: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    day = meta.day
    session_open = float(day.iloc[0]["open"])
    prev_high = daily_row.get("prev_high")
    prev_low = daily_row.get("prev_low")
    prev_close = daily_row.get("prev_close")
    gap_points = daily_row.get("gap_points")
    era = daily_row.get("era") or classify_era(meta.date)
    flags = era_flags(era)

    for cp in CHECKPOINTS:
        window = slice_to_minute(day, meta.session_start, cp.minutes_from_open)
        is_valid = not window.empty and len(window) >= cp.minutes_from_open * 0.75

        base = {
            "date": meta.date,
            "checkpoint_minute": cp.minutes_from_open,
            "checkpoint_clock": cp.clock_label,
            "checkpoint_cadence": cp.cadence,
            "view_layer": cp.view_layer,
            "is_valid_checkpoint": is_valid,
            "ib_formed_at_checkpoint": meta.session_start + pd.Timedelta(minutes=cp.minutes_from_open)
            >= meta.ib_end_time,
            "era": era,
            **flags,
        }

        if not is_valid:
            rows.append(base)
            continue

        high_so_far = window["high"].max()
        low_so_far = window["low"].min()
        range_so_far = high_so_far - low_so_far
        close = float(window.iloc[-1]["close"])
        checkpoint_time = window.iloc[-1]["datetime"]
        minute = cp.minutes_from_open
        end_pos = len(window) - 1

        new_high_count = int(
            (window["high"] > window["high"].cummax().shift(1)).fillna(False).sum()
        )
        new_low_count = int(
            (window["low"] < window["low"].cummin().shift(1)).fillna(False).sum()
        )

        if pd.isna(gap_points) or gap_points == 0:
            gap_fill_progress = np.nan
            gap_filled = False
            gap_sustaining = False
        elif gap_points > 0:
            gap_fill_progress = max(0.0, min(1.0, safe_divide(session_open - low_so_far, gap_points)))
            gap_filled = bool(low_so_far <= prev_close)
            gap_sustaining = bool(not gap_filled and close > prev_close)
        else:
            gap_fill_progress = max(0.0, min(1.0, safe_divide(high_so_far - session_open, abs(gap_points))))
            gap_filled = bool(high_so_far >= prev_close)
            gap_sustaining = bool(not gap_filled and close < prev_close)

        opening_dir = direction_from_points(close - session_open)
        pressure = _pressure_bucket(safe_divide(close - low_so_far, range_so_far))

        if prev_high is not None and prev_low is not None and not pd.isna(prev_high):
            prior_traps = failed_break_episodes_in_range(day, prev_high, prev_low, 0, end_pos)
            trap_stats = trap_summary(prior_traps)
            trap_basis = "PREV_RANGE"
        else:
            trap_stats = trap_summary([])
            trap_basis = "NONE"

        rows.append(
            {
                **base,
                "checkpoint_time": checkpoint_time,
                "checkpoint_hour": to_hour(checkpoint_time),
                "bars_seen": len(window),
                "session_open": session_open,
                "checkpoint_close": close,
                "high_so_far": high_so_far,
                "low_so_far": low_so_far,
                "range_so_far": range_so_far,
                "body_so_far": close - session_open,
                "return_from_open_points": close - session_open,
                "return_from_open_pct": safe_divide(close - session_open, session_open) * 100,
                "opening_direction": opening_dir,
                "opening_pressure": pressure,
                "close_position_in_range_so_far": safe_divide(close - low_so_far, range_so_far),
                "signed_speed_points_per_min": safe_divide(close - session_open, minute),
                "abs_speed_points_per_min": safe_divide(abs(close - session_open), minute),
                "range_speed_points_per_min": safe_divide(range_so_far, minute),
                "directional_efficiency": safe_divide(abs(close - session_open), range_so_far),
                "up_move_from_open": high_so_far - session_open,
                "down_move_from_open": session_open - low_so_far,
                "new_high_count": new_high_count,
                "new_low_count": new_low_count,
                "opening_range_high": high_so_far,
                "opening_range_low": low_so_far,
                "opening_range_size": range_so_far,
                "opening_range_pct": safe_divide(range_so_far, session_open) * 100,
                "gap_points": gap_points,
                "gap_pct": daily_row.get("gap_pct"),
                "gap_direction": daily_row.get("gap_direction"),
                "gap_fill_progress_pct": gap_fill_progress * 100 if not pd.isna(gap_fill_progress) else np.nan,
                "gap_filled_by_checkpoint": gap_filled,
                "gap_sustaining_by_checkpoint": gap_sustaining,
                "distance_to_prev_close": close - prev_close if not pd.isna(prev_close) else np.nan,
                "distance_to_prev_high": close - prev_high if not pd.isna(prev_high) else np.nan,
                "distance_to_prev_low": close - prev_low if not pd.isna(prev_low) else np.nan,
                "position_vs_prev_range": safe_divide(close - prev_low, prev_high - prev_low)
                if not pd.isna(prev_low) and not pd.isna(prev_high)
                else np.nan,
                "tests_of_prev_high": count_level_tests(window, prev_high, "HIGH"),
                "tests_of_prev_low": count_level_tests(window, prev_low, "LOW"),
                "tests_of_or_high": count_level_tests(window, high_so_far, "HIGH"),
                "tests_of_or_low": count_level_tests(window, low_so_far, "LOW"),
                "minutes_elapsed": minutes_between(meta.session_start, checkpoint_time),
                "trap_basis": trap_basis,
                **trap_stats,
            }
        )

    return rows


def _pressure_bucket(value: float) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    if value >= 0.67:
        return "UPPER_THIRD"
    if value <= 0.33:
        return "LOWER_THIRD"
    return "MIDDLE_THIRD"
