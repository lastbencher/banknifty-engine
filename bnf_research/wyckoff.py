from __future__ import annotations

from typing import Any

import pandas as pd

from bnf_research.config import ABSORPTION_MIN_TESTS
from bnf_research.session import SessionMeta
from bnf_research.utils import minutes_between


def _session_active_after(meta: SessionMeta, active_after: pd.Timestamp | None) -> pd.Timestamp:
    if active_after is not None:
        return active_after
    # Default: skip opening 15 minutes (no IB dependency)
    return meta.session_start + pd.Timedelta(minutes=15)


def detect_springs_at_range(
    meta: SessionMeta,
    range_high: float,
    range_low: float,
    *,
    active_after: pd.Timestamp | None = None,
) -> list[dict[str, Any]]:
    """
    Spring (potential buy):
    break below support → return inside value range → close back above support.
    """
    events: list[dict[str, Any]] = []
    start = _session_active_after(meta, active_after)
    if meta.day.empty:
        return events

    broke_below = False
    break_time = pd.NaT
    break_pos: int | None = None
    break_price = float("nan")

    for abs_pos in range(len(meta.day)):
        row = meta.day.iloc[abs_pos]
        if row["datetime"] < start:
            continue

        if not broke_below:
            if row["low"] < range_low:
                broke_below = True
                break_time = row["datetime"]
                break_pos = abs_pos
                break_price = row["low"]
            continue

        inside = range_low <= row["close"] <= range_high
        if inside and row["close"] > range_low:
            events.append(
                {
                    "event_subtype": "SPRING",
                    "event_direction": "LOW",
                    "break_time": break_time,
                    "break_pos": break_pos,
                    "break_price": break_price,
                    "confirm_time": row["datetime"],
                    "confirm_pos": abs_pos,
                    "confirm_price": row["close"],
                    "level": range_low,
                    "duration_minutes": minutes_between(break_time, row["datetime"]),
                }
            )
            broke_below = False

    return events


def detect_upthrusts_at_range(
    meta: SessionMeta,
    range_high: float,
    range_low: float,
    *,
    active_after: pd.Timestamp | None = None,
) -> list[dict[str, Any]]:
    """
    Upthrust (potential sell):
    break above resistance → return inside value range → close back below resistance.
    """
    events: list[dict[str, Any]] = []
    start = _session_active_after(meta, active_after)
    if meta.day.empty:
        return events

    broke_above = False
    break_time = pd.NaT
    break_pos: int | None = None
    break_price = float("nan")

    for abs_pos in range(len(meta.day)):
        row = meta.day.iloc[abs_pos]
        if row["datetime"] < start:
            continue

        if not broke_above:
            if row["high"] > range_high:
                broke_above = True
                break_time = row["datetime"]
                break_pos = abs_pos
                break_price = row["high"]
            continue

        inside = range_low <= row["close"] <= range_high
        if inside and row["close"] < range_high:
            events.append(
                {
                    "event_subtype": "UPTHRUST",
                    "event_direction": "HIGH",
                    "break_time": break_time,
                    "break_pos": break_pos,
                    "break_price": break_price,
                    "confirm_time": row["datetime"],
                    "confirm_pos": abs_pos,
                    "confirm_price": row["close"],
                    "level": range_high,
                    "duration_minutes": minutes_between(break_time, row["datetime"]),
                }
            )
            broke_above = False

    return events


def detect_springs(
    meta: SessionMeta,
    ib_high: float,
    ib_low: float,
) -> list[dict[str, Any]]:
    """Legacy IB-named wrapper — used by feature pipeline only."""
    if not meta.has_ib:
        return []
    return detect_springs_at_range(
        meta, ib_high, ib_low, active_after=meta.ib_end_time
    )


def detect_upthrusts(
    meta: SessionMeta,
    ib_high: float,
    ib_low: float,
) -> list[dict[str, Any]]:
    """Legacy IB-named wrapper — used by feature pipeline only."""
    if not meta.has_ib:
        return []
    return detect_upthrusts_at_range(
        meta, ib_high, ib_low, active_after=meta.ib_end_time
    )


def detect_absorption(
    meta: SessionMeta,
    ib_high: float,
    ib_low: float,
) -> list[dict[str, Any]]:
    """
    Absorption: multiple tests of a level without sustained rejection.
    HIGH side: 3+ bars touch IB high (high >= ib_high) but close <= ib_high.
    LOW side: 3+ bars touch IB low (low <= ib_low) but close >= ib_low.
    """
    events: list[dict[str, Any]] = []
    if not meta.has_ib or meta.after_ib.empty:
        return events

    high_tests: list[int] = []
    low_tests: list[int] = []

    for abs_pos in range(len(meta.day)):
        row = meta.day.iloc[abs_pos]
        if row["datetime"] < meta.ib_end_time:
            continue

        if row["high"] >= ib_high and row["close"] <= ib_high:
            high_tests.append(abs_pos)

        if row["low"] <= ib_low and row["close"] >= ib_low:
            low_tests.append(abs_pos)

        if len(high_tests) >= ABSORPTION_MIN_TESTS and high_tests[-1] == abs_pos:
            events.append(
                {
                    "event_subtype": "ABSORPTION_HIGH",
                    "event_direction": "HIGH",
                    "confirm_time": row["datetime"],
                    "confirm_pos": abs_pos,
                    "confirm_price": row["close"],
                    "level": ib_high,
                    "test_count": len(high_tests),
                }
            )
            high_tests.clear()

        if len(low_tests) >= ABSORPTION_MIN_TESTS and low_tests[-1] == abs_pos:
            events.append(
                {
                    "event_subtype": "ABSORPTION_LOW",
                    "event_direction": "LOW",
                    "confirm_time": row["datetime"],
                    "confirm_pos": abs_pos,
                    "confirm_price": row["close"],
                    "level": ib_low,
                    "test_count": len(low_tests),
                }
            )
            low_tests.clear()

    return events


def trap_summary(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    high_count = sum(1 for e in episodes if e.get("event_direction") == "HIGH" or e.get("side") == "HIGH")
    low_count = sum(1 for e in episodes if e.get("event_direction") == "LOW" or e.get("side") == "LOW")
    failed_count = len(episodes)
    both_sides = high_count > 0 and low_count > 0
    severity = failed_count + (0.5 if both_sides else 0.0)
    return {
        "failed_break_count": failed_count,
        "failed_high_break_count": high_count,
        "failed_low_break_count": low_count,
        "trap_severity_score": severity,
        "trap_count_before_move": failed_count,
    }


def failed_break_episodes_in_range(
    day: pd.DataFrame,
    high_level: float,
    low_level: float,
    start_pos: int,
    end_pos: int,
) -> list[dict[str, Any]]:
    """Failed breakouts against arbitrary range levels within a bar slice."""
    if pd.isna(high_level) or pd.isna(low_level) or start_pos >= len(day):
        return []

    episodes: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    end_pos = min(end_pos, len(day) - 1)

    for pos in range(start_pos, end_pos + 1):
        row = day.iloc[pos]

        if active is None:
            if row["high"] > high_level:
                active = {"side": "HIGH", "break_pos": pos, "level": high_level}
            elif row["low"] < low_level:
                active = {"side": "LOW", "break_pos": pos, "level": low_level}
            continue

        if active["side"] == "HIGH" and row["close"] <= high_level:
            episodes.append(active)
            active = None
        elif active["side"] == "LOW" and row["close"] >= low_level:
            episodes.append(active)
            active = None

    return episodes


def detect_failed_breaks(
    meta: SessionMeta,
    ib_high: float,
    ib_low: float,
) -> list[dict[str, Any]]:
    """Failed breakout: pierce level then close back inside on same side."""
    episodes: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None

    for abs_pos in range(len(meta.day)):
        row = meta.day.iloc[abs_pos]

        if active is None:
            if row["high"] > ib_high:
                active = {
                    "side": "HIGH",
                    "break_pos": abs_pos,
                    "break_time": row["datetime"],
                    "level": ib_high,
                    "max_extension": row["high"] - ib_high,
                }
            elif row["low"] < ib_low:
                active = {
                    "side": "LOW",
                    "break_pos": abs_pos,
                    "break_time": row["datetime"],
                    "level": ib_low,
                    "max_extension": ib_low - row["low"],
                }
            continue

        if active["side"] == "HIGH":
            active["max_extension"] = max(active["max_extension"], row["high"] - ib_high)
            if row["close"] <= ib_high:
                episodes.append(
                    {
                        "event_subtype": "FAILED_HIGH_BREAK",
                        "event_direction": "HIGH",
                        "break_time": active["break_time"],
                        "break_pos": active["break_pos"],
                        "confirm_time": row["datetime"],
                        "confirm_pos": abs_pos,
                        "confirm_price": row["close"],
                        "level": ib_high,
                        "max_extension": active["max_extension"],
                        "duration_minutes": minutes_between(active["break_time"], row["datetime"]),
                    }
                )
                active = None

        elif active["side"] == "LOW":
            active["max_extension"] = max(active["max_extension"], ib_low - row["low"])
            if row["close"] >= ib_low:
                episodes.append(
                    {
                        "event_subtype": "FAILED_LOW_BREAK",
                        "event_direction": "LOW",
                        "break_time": active["break_time"],
                        "break_pos": active["break_pos"],
                        "confirm_time": row["datetime"],
                        "confirm_pos": abs_pos,
                        "confirm_price": row["close"],
                        "level": ib_low,
                        "max_extension": active["max_extension"],
                        "duration_minutes": minutes_between(active["break_time"], row["datetime"]),
                    }
                )
                active = None

    return episodes
