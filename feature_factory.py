from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_SOURCE = "banknifty_master.csv"
DEFAULT_OUTPUT_DIR = "features"
CHECKPOINT_MINUTES = [3, 5, 10, 15, 30]
POINT_THRESHOLDS = [50, 100]
IB_MINUTES = 60
COMPLETE_SESSION_MIN_BARS = 300


@dataclass(frozen=True)
class DayContext:
    date: Any
    day: pd.DataFrame
    prev: dict[str, Any] | None
    era: str
    era_flags: dict[str, bool]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build canonical Bank Nifty research feature datasets."
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def classify_era(date_value: Any) -> str:
    d = pd.Timestamp(date_value)

    if d < pd.Timestamp("2020-03-01"):
        return "pre_covid"

    if d <= pd.Timestamp("2021-12-31"):
        return "covid"

    if d <= pd.Timestamp("2023-12-31"):
        return "post_covid"

    return "recent"


def era_flags(era: str) -> dict[str, bool]:
    return {
        "pre_covid": era == "pre_covid",
        "covid": era == "covid",
        "post_covid": era == "post_covid",
        "recent": era == "recent",
    }


def to_hour(ts: Any) -> float:
    if pd.isna(ts):
        return np.nan

    value = pd.Timestamp(ts)
    return value.hour


def minutes_between(start: Any, end: Any) -> float:
    if pd.isna(start) or pd.isna(end):
        return np.nan

    return (pd.Timestamp(end) - pd.Timestamp(start)).total_seconds() / 60.0


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return np.nan

    return numerator / denominator


def load_master(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = ["datetime", "open", "high", "low", "close"]
    missing = set(required).difference(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df[required].copy()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    df["date"] = df["datetime"].dt.date

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def opening_window_features(day: pd.DataFrame, minutes: int) -> dict[str, float]:
    prefix = f"or_{minutes}"

    if len(day) < minutes:
        return {
            f"{prefix}_high": np.nan,
            f"{prefix}_low": np.nan,
            f"{prefix}_range": np.nan,
            f"{prefix}_return": np.nan,
        }

    window = day.iloc[:minutes]
    high = window["high"].max()
    low = window["low"].min()
    session_open = day.iloc[0]["open"]
    close = window.iloc[-1]["close"]

    return {
        f"{prefix}_high": high,
        f"{prefix}_low": low,
        f"{prefix}_range": high - low,
        f"{prefix}_return": close - session_open,
    }


def gap_features(day: pd.DataFrame, prev: dict[str, Any] | None) -> dict[str, Any]:
    day_open = day.iloc[0]["open"]

    if prev is None:
        return {
            "prev_date": None,
            "prev_high": np.nan,
            "prev_low": np.nan,
            "prev_close": np.nan,
            "prev_day_range": np.nan,
            "gap_points": np.nan,
            "gap_pct": np.nan,
            "gap_direction": None,
            "gap_type": None,
            "opened_above_prev_high": None,
            "opened_below_prev_low": None,
            "opened_inside_prev_range": None,
            "gap_filled": None,
            "gap_fill_time": pd.NaT,
            "minutes_to_gap_fill": np.nan,
            "gap_sustain_until_close": None,
        }

    prev_close = prev["day_close"]
    gap_points = day_open - prev_close

    if gap_points > 0:
        gap_direction = "UP"
        gap_type = "GAP_UP"
        fill_mask = day["low"] <= prev_close
        sustain = (not fill_mask.any()) and day.iloc[-1]["close"] > prev_close
    elif gap_points < 0:
        gap_direction = "DOWN"
        gap_type = "GAP_DOWN"
        fill_mask = day["high"] >= prev_close
        sustain = (not fill_mask.any()) and day.iloc[-1]["close"] < prev_close
    else:
        gap_direction = "FLAT"
        gap_type = "FLAT"
        fill_mask = pd.Series(False, index=day.index)
        sustain = False

    if fill_mask.any():
        fill_pos = fill_mask[fill_mask].index[0]
        fill_time = day.loc[fill_pos, "datetime"]
        minutes_to_fill = minutes_between(day.iloc[0]["datetime"], fill_time)
        gap_filled = True
    else:
        fill_time = pd.NaT
        minutes_to_fill = np.nan
        gap_filled = False

    return {
        "prev_date": prev["date"],
        "prev_high": prev["day_high"],
        "prev_low": prev["day_low"],
        "prev_close": prev_close,
        "prev_day_range": prev["day_range"],
        "gap_points": gap_points,
        "gap_pct": safe_divide(gap_points, prev_close) * 100,
        "gap_direction": gap_direction,
        "gap_type": gap_type,
        "opened_above_prev_high": bool(day_open > prev["day_high"]),
        "opened_below_prev_low": bool(day_open < prev["day_low"]),
        "opened_inside_prev_range": bool(prev["day_low"] <= day_open <= prev["day_high"]),
        "gap_filled": gap_filled,
        "gap_fill_time": fill_time,
        "minutes_to_gap_fill": minutes_to_fill,
        "gap_sustain_until_close": bool(sustain),
    }


def find_first_break(
    day: pd.DataFrame,
    ib_high: float,
    ib_low: float,
) -> dict[str, Any]:
    if len(day) <= IB_MINUTES:
        return {
            "direction": None,
            "pos": None,
            "time": pd.NaT,
            "price": np.nan,
            "level": np.nan,
        }

    for pos in range(IB_MINUTES, len(day)):
        row = day.iloc[pos]

        if row["high"] > ib_high:
            return {
                "direction": "HIGH",
                "pos": pos,
                "time": row["datetime"],
                "price": row["high"],
                "level": ib_high,
            }

        if row["low"] < ib_low:
            return {
                "direction": "LOW",
                "pos": pos,
                "time": row["datetime"],
                "price": row["low"],
                "level": ib_low,
            }

    return {
        "direction": None,
        "pos": None,
        "time": pd.NaT,
        "price": np.nan,
        "level": np.nan,
    }


def find_opposite_break(
    day: pd.DataFrame,
    first_break: dict[str, Any],
    ib_high: float,
    ib_low: float,
) -> dict[str, Any]:
    if first_break["pos"] is None:
        return {
            "occurred": False,
            "pos": None,
            "time": pd.NaT,
            "price": np.nan,
            "level": np.nan,
        }

    for pos in range(first_break["pos"], len(day)):
        row = day.iloc[pos]

        if first_break["direction"] == "HIGH" and row["low"] < ib_low:
            return {
                "occurred": True,
                "pos": pos,
                "time": row["datetime"],
                "price": row["low"],
                "level": ib_low,
            }

        if first_break["direction"] == "LOW" and row["high"] > ib_high:
            return {
                "occurred": True,
                "pos": pos,
                "time": row["datetime"],
                "price": row["high"],
                "level": ib_high,
            }

    return {
        "occurred": False,
        "pos": None,
        "time": pd.NaT,
        "price": np.nan,
        "level": np.nan,
    }


def failed_break_episodes(
    day: pd.DataFrame,
    high_level: float,
    low_level: float,
    start_pos: int,
    end_pos: int | None = None,
) -> list[dict[str, Any]]:
    if pd.isna(high_level) or pd.isna(low_level) or start_pos >= len(day):
        return []

    if end_pos is None:
        end_pos = len(day) - 1

    episodes: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None

    for pos in range(start_pos, min(end_pos, len(day) - 1) + 1):
        row = day.iloc[pos]

        if active is None:
            if row["high"] > high_level:
                active = {
                    "side": "HIGH",
                    "break_pos": pos,
                    "break_time": row["datetime"],
                    "break_price": row["high"],
                    "level": high_level,
                    "max_extension": row["high"] - high_level,
                }
            elif row["low"] < low_level:
                active = {
                    "side": "LOW",
                    "break_pos": pos,
                    "break_time": row["datetime"],
                    "break_price": row["low"],
                    "level": low_level,
                    "max_extension": low_level - row["low"],
                }

        if active is None:
            continue

        if active["side"] == "HIGH":
            active["max_extension"] = max(
                active["max_extension"],
                row["high"] - high_level,
            )

            if row["close"] <= high_level:
                active = {
                    **active,
                    "failure_pos": pos,
                    "failure_time": row["datetime"],
                    "failure_price": row["close"],
                    "duration_minutes": minutes_between(
                        active["break_time"],
                        row["datetime"],
                    ),
                }
                episodes.append(active)
                active = None

        elif active["side"] == "LOW":
            active["max_extension"] = max(
                active["max_extension"],
                low_level - row["low"],
            )

            if row["close"] >= low_level:
                active = {
                    **active,
                    "failure_pos": pos,
                    "failure_time": row["datetime"],
                    "failure_price": row["close"],
                    "duration_minutes": minutes_between(
                        active["break_time"],
                        row["datetime"],
                    ),
                }
                episodes.append(active)
                active = None

    return episodes


def trap_summary(
    episodes: list[dict[str, Any]],
    returned_inside: bool,
    crossed_mid: bool,
    opposite_break: bool,
) -> dict[str, Any]:
    high_count = sum(1 for episode in episodes if episode["side"] == "HIGH")
    low_count = sum(1 for episode in episodes if episode["side"] == "LOW")
    failed_count = high_count + low_count
    both_sides = high_count > 0 and low_count > 0

    severity = (
        failed_count
        + (0.5 if both_sides else 0.0)
        + (1.0 if returned_inside else 0.0)
        + (1.0 if crossed_mid else 0.0)
        + (2.0 if opposite_break else 0.0)
    )

    return {
        "failed_break_count": failed_count,
        "failed_high_break_count": high_count,
        "failed_low_break_count": low_count,
        "trap_severity_score": severity,
    }


def count_failed_before(
    episodes: list[dict[str, Any]],
    pos: int | None,
) -> dict[str, Any]:
    if pos is None:
        selected = episodes
    else:
        selected = [
            episode
            for episode in episodes
            if episode["failure_pos"] <= pos
        ]

    high_count = sum(1 for episode in selected if episode["side"] == "HIGH")
    low_count = sum(1 for episode in selected if episode["side"] == "LOW")

    return {
        "trap_count_before_move": high_count + low_count,
        "failed_break_count": high_count + low_count,
        "failed_high_break_count": high_count,
        "failed_low_break_count": low_count,
        "trap_severity_score": high_count + low_count + (0.5 if high_count and low_count else 0.0),
    }


def threshold_hit(
    day: pd.DataFrame,
    start_pos: int | None,
    anchor_price: float,
    direction: str | None,
    threshold: float,
) -> dict[str, Any]:
    if start_pos is None or direction is None or pd.isna(anchor_price):
        return {
            "hit": False,
            "pos": None,
            "time": pd.NaT,
            "price": np.nan,
            "move_points": np.nan,
            "max_adverse_before_event": np.nan,
        }

    max_adverse = 0.0

    for pos in range(start_pos, len(day)):
        row = day.iloc[pos]

        if direction == "HIGH":
            max_adverse = max(max_adverse, anchor_price - row["low"])

            if row["high"] >= anchor_price + threshold:
                return {
                    "hit": True,
                    "pos": pos,
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
                    "pos": pos,
                    "time": row["datetime"],
                    "price": row["low"],
                    "move_points": anchor_price - row["low"],
                    "max_adverse_before_event": max_adverse,
                }

    return {
        "hit": False,
        "pos": None,
        "time": pd.NaT,
        "price": np.nan,
        "move_points": np.nan,
        "max_adverse_before_event": max_adverse,
    }


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

    trade = day.iloc[first_break["pos"]:]

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


def post_break_failure_features(
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

    for pos in range(first_break["pos"], len(day)):
        row = day.iloc[pos]

        if first_break["direction"] == "HIGH":
            if row["low"] <= ib_mid:
                crossed_mid = True

            if row["close"] <= ib_high:
                returned_inside = True
                break

            minutes_outside += 1

        elif first_break["direction"] == "LOW":
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


def close_location(close: float, ib_high: float, ib_low: float) -> str | None:
    if pd.isna(ib_high) or pd.isna(ib_low):
        return None

    if close > ib_high:
        return "ABOVE_IB"

    if close < ib_low:
        return "BELOW_IB"

    return "INSIDE_IB"


def extension_type(broke_high: bool, broke_low: bool) -> str:
    if broke_high and broke_low:
        return "BOTH"

    if broke_high:
        return "HIGH_ONLY"

    if broke_low:
        return "LOW_ONLY"

    return "NONE"


def build_daily_row(ctx: DayContext) -> tuple[dict[str, Any], dict[str, Any]]:
    day = ctx.day
    first = day.iloc[0]
    last = day.iloc[-1]

    day_open = first["open"]
    day_high = day["high"].max()
    day_low = day["low"].min()
    day_close = last["close"]
    day_range = day_high - day_low
    day_body = day_close - day_open

    base: dict[str, Any] = {
        "date": ctx.date,
        "era": ctx.era,
        **ctx.era_flags,
        "bars_count": len(day),
        "session_start": first["datetime"],
        "session_end": last["datetime"],
        "is_complete_session": len(day) >= COMPLETE_SESSION_MIN_BARS,
        "day_open": day_open,
        "day_high": day_high,
        "day_low": day_low,
        "day_close": day_close,
        "day_range": day_range,
        "day_body": day_body,
        "close_position_in_range": safe_divide(day_close - day_low, day_range),
    }

    base.update(gap_features(day, ctx.prev))

    for minutes in CHECKPOINT_MINUTES:
        base.update(opening_window_features(day, minutes))

    if len(day) < IB_MINUTES:
        base.update(
            {
                "ib_high": np.nan,
                "ib_low": np.nan,
                "ib_mid": np.nan,
                "ib_range": np.nan,
                "ib_range_pct": np.nan,
                "ib_efficiency_ratio": np.nan,
                "expansion_factor": np.nan,
                "broke_ib_high": False,
                "broke_ib_low": False,
                "extension_type": "NONE",
                "first_break_direction": None,
                "first_break_time": pd.NaT,
                "first_break_hour": np.nan,
                "minutes_to_first_break": np.nan,
                "first_break_price": np.nan,
                "opposite_break": False,
                "opposite_break_time": pd.NaT,
                "opposite_break_hour": np.nan,
                "minutes_from_first_to_opposite": np.nan,
                "mfe_after_first_break_points": np.nan,
                "mae_after_first_break_points": np.nan,
                "mfe_after_first_break_ib": np.nan,
                "time_to_mfe_after_first_break": np.nan,
                "speed_to_mfe_points_per_min": np.nan,
                "mfe_hour": np.nan,
                "hit_50_after_first_break": False,
                "minutes_to_50_after_first_break": np.nan,
                "speed_to_50_after_first_break": np.nan,
                "first_50_hit_time": pd.NaT,
                "first_50_hit_hour": np.nan,
                "hit_100_after_first_break": False,
                "minutes_to_100_after_first_break": np.nan,
                "speed_to_100_after_first_break": np.nan,
                "first_100_hit_time": pd.NaT,
                "first_100_hit_hour": np.nan,
                "returned_inside_ib": False,
                "crossed_ib_mid_after_break": False,
                "minutes_outside_after_break": 0,
                "close_location_vs_ib": None,
                "closed_inside_ib": None,
                "trend_day_flag": None,
                "rotational_day_flag": None,
                "day_type_rule": None,
                "label_50_before_opposite": False,
                "label_100_before_opposite": False,
                "label_opposite_break": False,
                "label_gap_fill": base["gap_filled"],
                "label_gap_sustain": base["gap_sustain_until_close"],
                "label_trend_day": None,
                "trap_count_before_move": 0,
                "failed_break_count": 0,
                "failed_high_break_count": 0,
                "failed_low_break_count": 0,
                "trap_severity_score": 0.0,
            }
        )
        return base, {"failed_episodes": []}

    ib = day.iloc[:IB_MINUTES]
    ib_high = ib["high"].max()
    ib_low = ib["low"].min()
    ib_mid = (ib_high + ib_low) / 2
    ib_range = ib_high - ib_low
    after_ib = day.iloc[IB_MINUTES:]

    broke_high = bool((after_ib["high"] > ib_high).any())
    broke_low = bool((after_ib["low"] < ib_low).any())
    first_break = find_first_break(day, ib_high, ib_low)
    opposite = find_opposite_break(day, first_break, ib_high, ib_low)
    failure = post_break_failure_features(day, first_break, ib_high, ib_low, ib_mid)
    mfe = favorable_excursion(day, first_break, ib_high, ib_low)
    episodes = failed_break_episodes(day, ib_high, ib_low, IB_MINUTES)

    hit_50 = threshold_hit(
        day,
        first_break["pos"],
        first_break["level"],
        first_break["direction"],
        50,
    )
    hit_100 = threshold_hit(
        day,
        first_break["pos"],
        first_break["level"],
        first_break["direction"],
        100,
    )

    first_to_opp = minutes_between(first_break["time"], opposite["time"])
    minutes_to_first = minutes_between(first["datetime"], first_break["time"])
    minutes_to_50 = minutes_between(first_break["time"], hit_50["time"])
    minutes_to_100 = minutes_between(first_break["time"], hit_100["time"])

    fifty_before_opp = bool(
        hit_50["hit"]
        and (
            not opposite["occurred"]
            or hit_50["pos"] <= opposite["pos"]
        )
    )
    hundred_before_opp = bool(
        hit_100["hit"]
        and (
            not opposite["occurred"]
            or hit_100["pos"] <= opposite["pos"]
        )
    )

    speed_to_mfe = safe_divide(
        mfe["mfe_points"],
        max(mfe["time_to_mfe"], 1) if not pd.isna(mfe["time_to_mfe"]) else np.nan,
    )
    speed_to_50 = safe_divide(50, max(minutes_to_50, 1)) if hit_50["hit"] else np.nan
    speed_to_100 = safe_divide(100, max(minutes_to_100, 1)) if hit_100["hit"] else np.nan

    efficiency = safe_divide(ib_range, day_range)
    expansion = safe_divide(day_range, ib_range)
    close_loc = close_location(day_close, ib_high, ib_low)
    trend_day = bool(expansion >= 2.0) if not pd.isna(expansion) else None
    rotational_day = bool(efficiency >= 0.767) if not pd.isna(efficiency) else None

    if pd.isna(expansion):
        day_type = None
    elif expansion >= 3:
        day_type = "TREND_DAY"
    elif expansion >= 2:
        day_type = "NORMAL_VARIATION"
    else:
        day_type = "NORMAL_OR_ROTATIONAL"

    move_pos = hit_50["pos"] if hit_50["hit"] else None
    trap_before_move = count_failed_before(episodes, move_pos)["trap_count_before_move"]
    trap_stats = trap_summary(
        episodes,
        failure["returned_inside_ib"],
        failure["crossed_ib_mid_after_break"],
        opposite["occurred"],
    )

    base.update(
        {
            "ib_high": ib_high,
            "ib_low": ib_low,
            "ib_mid": ib_mid,
            "ib_range": ib_range,
            "ib_range_pct": safe_divide(ib_range, day_open) * 100,
            "ib_efficiency_ratio": efficiency,
            "expansion_factor": expansion,
            "broke_ib_high": broke_high,
            "broke_ib_low": broke_low,
            "extension_type": extension_type(broke_high, broke_low),
            "first_break_direction": first_break["direction"],
            "first_break_time": first_break["time"],
            "first_break_hour": to_hour(first_break["time"]),
            "minutes_to_first_break": minutes_to_first,
            "first_break_price": first_break["price"],
            "opposite_break": opposite["occurred"],
            "opposite_break_time": opposite["time"],
            "opposite_break_hour": to_hour(opposite["time"]),
            "minutes_from_first_to_opposite": first_to_opp,
            "mfe_after_first_break_points": mfe["mfe_points"],
            "mae_after_first_break_points": mfe["mae_points"],
            "mfe_after_first_break_ib": safe_divide(mfe["mfe_points"], ib_range),
            "time_to_mfe_after_first_break": mfe["time_to_mfe"],
            "speed_to_mfe_points_per_min": speed_to_mfe,
            "mfe_hour": to_hour(mfe["mfe_time"]),
            "hit_50_after_first_break": hit_50["hit"],
            "minutes_to_50_after_first_break": minutes_to_50,
            "speed_to_50_after_first_break": speed_to_50,
            "first_50_hit_time": hit_50["time"],
            "first_50_hit_hour": to_hour(hit_50["time"]),
            "hit_100_after_first_break": hit_100["hit"],
            "minutes_to_100_after_first_break": minutes_to_100,
            "speed_to_100_after_first_break": speed_to_100,
            "first_100_hit_time": hit_100["time"],
            "first_100_hit_hour": to_hour(hit_100["time"]),
            "returned_inside_ib": failure["returned_inside_ib"],
            "crossed_ib_mid_after_break": failure["crossed_ib_mid_after_break"],
            "minutes_outside_after_break": failure["minutes_outside_after_break"],
            "close_location_vs_ib": close_loc,
            "closed_inside_ib": close_loc == "INSIDE_IB",
            "trend_day_flag": trend_day,
            "rotational_day_flag": rotational_day,
            "day_type_rule": day_type,
            "label_50_before_opposite": fifty_before_opp,
            "label_100_before_opposite": hundred_before_opp,
            "label_opposite_break": opposite["occurred"],
            "label_gap_fill": base["gap_filled"],
            "label_gap_sustain": base["gap_sustain_until_close"],
            "label_trend_day": trend_day,
            "trap_count_before_move": trap_before_move,
            **trap_stats,
        }
    )

    aux = {
        "first_break": first_break,
        "opposite": opposite,
        "mfe": mfe,
        "hit_50": hit_50,
        "hit_100": hit_100,
        "failed_episodes": episodes,
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_mid": ib_mid,
        "ib_range": ib_range,
        "opening_range_15m": base["or_15_range"],
    }

    return base, aux


def build_checkpoint_rows(
    ctx: DayContext,
    daily_row: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    day = ctx.day
    session_open = day.iloc[0]["open"]

    for minute in CHECKPOINT_MINUTES:
        window = day.iloc[:minute]
        is_valid = len(window) == minute

        if not is_valid:
            rows.append(
                {
                    "date": ctx.date,
                    "checkpoint_minute": minute,
                    "is_valid_checkpoint": False,
                    "era": ctx.era,
                    **ctx.era_flags,
                }
            )
            continue

        high_so_far = window["high"].max()
        low_so_far = window["low"].min()
        range_so_far = high_so_far - low_so_far
        close = window.iloc[-1]["close"]
        checkpoint_time = window.iloc[-1]["datetime"]

        new_high_count = int((window["high"] > window["high"].cummax().shift(1)).fillna(False).sum())
        new_low_count = int((window["low"] < window["low"].cummin().shift(1)).fillna(False).sum())

        gap_points = daily_row["gap_points"]
        prev_close = daily_row["prev_close"]
        prev_high = daily_row["prev_high"]
        prev_low = daily_row["prev_low"]

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

        if ctx.prev is None:
            prior_traps: list[dict[str, Any]] = []
        else:
            prior_traps = failed_break_episodes(
                day,
                prev_high,
                prev_low,
                0,
                minute - 1,
            )

        trap_stats = trap_summary(
            prior_traps,
            returned_inside=False,
            crossed_mid=False,
            opposite_break=False,
        )

        rows.append(
            {
                "date": ctx.date,
                "checkpoint_minute": minute,
                "checkpoint_time": checkpoint_time,
                "checkpoint_hour": to_hour(checkpoint_time),
                "bars_seen": len(window),
                "is_valid_checkpoint": True,
                "era": ctx.era,
                **ctx.era_flags,
                "session_open": session_open,
                "checkpoint_close": close,
                "high_so_far": high_so_far,
                "low_so_far": low_so_far,
                "range_so_far": range_so_far,
                "body_so_far": close - session_open,
                "return_from_open_points": close - session_open,
                "return_from_open_pct": safe_divide(close - session_open, session_open) * 100,
                "close_position_in_range_so_far": safe_divide(close - low_so_far, range_so_far),
                "signed_speed_points_per_min": safe_divide(close - session_open, minute),
                "abs_speed_points_per_min": safe_divide(abs(close - session_open), minute),
                "range_speed_points_per_min": safe_divide(range_so_far, minute),
                "up_move_from_open": high_so_far - session_open,
                "down_move_from_open": session_open - low_so_far,
                "directional_efficiency": safe_divide(abs(close - session_open), range_so_far),
                "new_high_count": new_high_count,
                "new_low_count": new_low_count,
                "gap_points": gap_points,
                "gap_pct": daily_row["gap_pct"],
                "gap_direction": daily_row["gap_direction"],
                "distance_to_prev_close": close - prev_close if not pd.isna(prev_close) else np.nan,
                "gap_fill_progress_pct": gap_fill_progress * 100 if not pd.isna(gap_fill_progress) else np.nan,
                "gap_filled_by_checkpoint": gap_filled,
                "gap_sustaining_by_checkpoint": gap_sustaining,
                "distance_to_prev_high": close - prev_high if not pd.isna(prev_high) else np.nan,
                "distance_to_prev_low": close - prev_low if not pd.isna(prev_low) else np.nan,
                "position_vs_prev_range": safe_divide(close - prev_low, prev_high - prev_low)
                if not pd.isna(prev_low) and not pd.isna(prev_high)
                else np.nan,
                "opening_range_high": high_so_far,
                "opening_range_low": low_so_far,
                "opening_range_size": range_so_far,
                "opening_range_pct": safe_divide(range_so_far, session_open) * 100,
                "trap_basis": "PREV_RANGE",
                "trap_count_before_move": trap_stats["failed_break_count"],
                **trap_stats,
            }
        )

    return rows


def common_event_context(
    ctx: DayContext,
    daily_row: dict[str, Any],
    aux: dict[str, Any],
    event_time: Any,
    event_pos: int | None,
) -> dict[str, Any]:
    first_break = aux.get("first_break", {})
    opposite = aux.get("opposite", {})
    episodes = aux.get("failed_episodes", [])

    if event_pos is not None:
        trap_stats = count_failed_before(episodes, event_pos)
    else:
        trap_stats = count_failed_before(episodes, None)

    first_time = first_break.get("time", pd.NaT)
    first_pos = first_break.get("pos")
    opposite_pos = opposite.get("pos")
    if (
        first_pos is not None
        and event_pos is not None
        and event_pos >= first_pos
    ):
        minutes_since_first_break = minutes_between(first_time, event_time)
    else:
        minutes_since_first_break = np.nan

    return {
        "date": ctx.date,
        "event_time": event_time,
        "event_hour": to_hour(event_time),
        "event_minute": minutes_between(ctx.day.iloc[0]["datetime"], event_time),
        "era": ctx.era,
        **ctx.era_flags,
        "first_break_direction": first_break.get("direction"),
        "minutes_since_first_break": minutes_since_first_break,
        "opposite_break_had_occurred": bool(
            opposite.get("occurred", False)
            and event_pos is not None
            and opposite_pos is not None
            and opposite_pos <= event_pos
        ),
        "event_before_opposite_break": bool(
            event_pos is not None
            and (
                not opposite.get("occurred", False)
                or opposite_pos is None
                or event_pos <= opposite_pos
            )
        ),
        "gap_direction": daily_row["gap_direction"],
        "ib_range": aux.get("ib_range", np.nan),
        "opening_range_15m": aux.get("opening_range_15m", np.nan),
        "first_break_pos": first_pos,
        **trap_stats,
    }


def event_row(
    ctx: DayContext,
    daily_row: dict[str, Any],
    aux: dict[str, Any],
    event_type_value: str,
    event_subtype: str,
    event_direction: str | None,
    event_time: Any,
    event_pos: int | None,
    anchor_type: str | None,
    anchor_time: Any,
    anchor_price: float,
    trigger_level: float,
    event_price: float,
    threshold_points: float | None = None,
    move_points: float | None = None,
    max_adverse_before_event: float | None = None,
) -> dict[str, Any]:
    minutes_from_anchor = minutes_between(anchor_time, event_time)
    speed_points = safe_divide(
        threshold_points if threshold_points is not None else abs(move_points or 0.0),
        max(minutes_from_anchor, 1) if not pd.isna(minutes_from_anchor) else np.nan,
    )

    row = common_event_context(ctx, daily_row, aux, event_time, event_pos)
    row.update(
        {
            "event_type": event_type_value,
            "event_subtype": event_subtype,
            "event_direction": event_direction,
            "anchor_type": anchor_type,
            "anchor_time": anchor_time,
            "anchor_price": anchor_price,
            "trigger_level": trigger_level,
            "event_price": event_price,
            "threshold_points": threshold_points,
            "move_points": move_points,
            "move_pct": safe_divide(move_points or np.nan, anchor_price) * 100,
            "minutes_from_anchor": minutes_from_anchor,
            "speed_points_per_min": speed_points,
            "speed_ib_per_min": safe_divide(speed_points, row["ib_range"]),
            "max_adverse_before_event": max_adverse_before_event,
            "pullback_before_event": max_adverse_before_event,
        }
    )
    return row


def build_event_rows(
    ctx: DayContext,
    daily_row: dict[str, Any],
    aux: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    day = ctx.day
    session_start = day.iloc[0]["datetime"]

    if ctx.prev is not None and daily_row["gap_direction"] in {"UP", "DOWN"}:
        rows.append(
            event_row(
                ctx,
                daily_row,
                aux,
                "GAP",
                "GAP_OPEN",
                daily_row["gap_direction"],
                session_start,
                0,
                "PREV_CLOSE",
                pd.NaT,
                daily_row["prev_close"],
                daily_row["prev_close"],
                daily_row["day_open"],
                move_points=abs(daily_row["gap_points"]),
            )
        )

        if daily_row["gap_filled"]:
            fill_pos = int(day.index[day["datetime"] == daily_row["gap_fill_time"]][0])
            rows.append(
                event_row(
                    ctx,
                    daily_row,
                    aux,
                    "GAP",
                    "GAP_FILL",
                    "DOWN" if daily_row["gap_direction"] == "UP" else "UP",
                    daily_row["gap_fill_time"],
                    fill_pos,
                    "SESSION_OPEN",
                    session_start,
                    daily_row["day_open"],
                    daily_row["prev_close"],
                    daily_row["prev_close"],
                    move_points=abs(daily_row["gap_points"]),
                )
            )
        elif daily_row["gap_sustain_until_close"]:
            rows.append(
                event_row(
                    ctx,
                    daily_row,
                    aux,
                    "GAP",
                    "GAP_SUSTAIN_CLOSE",
                    daily_row["gap_direction"],
                    day.iloc[-1]["datetime"],
                    len(day) - 1,
                    "SESSION_OPEN",
                    session_start,
                    daily_row["day_open"],
                    daily_row["prev_close"],
                    daily_row["day_close"],
                    move_points=abs(daily_row["day_close"] - daily_row["prev_close"]),
                )
            )

    first_break = aux.get("first_break", {})

    if first_break.get("pos") is not None:
        rows.append(
            event_row(
                ctx,
                daily_row,
                aux,
                "FIRST_BREAK",
                "IB_FIRST_BREAK",
                first_break["direction"],
                first_break["time"],
                first_break["pos"],
                "IB_END",
                day.iloc[IB_MINUTES - 1]["datetime"],
                aux["ib_mid"],
                first_break["level"],
                first_break["price"],
                move_points=abs(first_break["price"] - first_break["level"]),
            )
        )

    opposite = aux.get("opposite", {})

    if opposite.get("occurred", False):
        rows.append(
            event_row(
                ctx,
                daily_row,
                aux,
                "OPPOSITE_BREAK",
                "IB_OPPOSITE_BREAK",
                "LOW" if first_break["direction"] == "HIGH" else "HIGH",
                opposite["time"],
                opposite["pos"],
                "FIRST_BREAK",
                first_break["time"],
                first_break["level"],
                opposite["level"],
                opposite["price"],
                move_points=abs(opposite["price"] - opposite["level"]),
            )
        )

    for episode in aux.get("failed_episodes", []):
        rows.append(
            event_row(
                ctx,
                daily_row,
                aux,
                "TRAP",
                f"FAILED_{episode['side']}_BREAK",
                episode["side"],
                episode["failure_time"],
                episode["failure_pos"],
                "IB",
                episode["break_time"],
                episode["level"],
                episode["level"],
                episode["failure_price"],
                move_points=episode["max_extension"],
                max_adverse_before_event=episode["max_extension"],
            )
        )

    for threshold in POINT_THRESHOLDS:
        for direction in ["HIGH", "LOW"]:
            open_hit = threshold_hit(
                day,
                0,
                daily_row["day_open"],
                direction,
                threshold,
            )

            if open_hit["hit"]:
                rows.append(
                    event_row(
                        ctx,
                        daily_row,
                        aux,
                        "POINT_MOVE",
                        f"FROM_OPEN_{threshold}",
                        direction,
                        open_hit["time"],
                        open_hit["pos"],
                        "SESSION_OPEN",
                        session_start,
                        daily_row["day_open"],
                        daily_row["day_open"] + threshold
                        if direction == "HIGH"
                        else daily_row["day_open"] - threshold,
                        open_hit["price"],
                        threshold_points=threshold,
                        move_points=open_hit["move_points"],
                        max_adverse_before_event=open_hit["max_adverse_before_event"],
                    )
                )

        if first_break.get("pos") is not None:
            break_hit = threshold_hit(
                day,
                first_break["pos"],
                first_break["level"],
                first_break["direction"],
                threshold,
            )

            if break_hit["hit"]:
                rows.append(
                    event_row(
                        ctx,
                        daily_row,
                        aux,
                        "POINT_MOVE",
                        f"FROM_FIRST_BREAK_{threshold}",
                        first_break["direction"],
                        break_hit["time"],
                        break_hit["pos"],
                        "FIRST_BREAK",
                        first_break["time"],
                        first_break["level"],
                        first_break["level"] + threshold
                        if first_break["direction"] == "HIGH"
                        else first_break["level"] - threshold,
                        break_hit["price"],
                        threshold_points=threshold,
                        move_points=break_hit["move_points"],
                        max_adverse_before_event=break_hit["max_adverse_before_event"],
                    )
                )

    return rows


def add_daily_rollups(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.sort_values("date").reset_index(drop=True)

    valid_ib = daily["ib_range"]
    q25 = valid_ib.quantile(0.25)
    q75 = valid_ib.quantile(0.75)

    daily["ib_bucket"] = "NORMAL"
    daily.loc[daily["ib_range"] <= q25, "ib_bucket"] = "NARROW"
    daily.loc[daily["ib_range"] >= q75, "ib_bucket"] = "WIDE"
    daily.loc[daily["ib_range"].isna(), "ib_bucket"] = None

    daily["rolling_20d_ib_median"] = (
        daily["ib_range"].shift(1).rolling(20, min_periods=5).median()
    )
    daily["rolling_20d_day_range_median"] = (
        daily["day_range"].shift(1).rolling(20, min_periods=5).median()
    )
    daily["rolling_20d_opposite_break_rate"] = (
        daily["opposite_break"].astype(float).shift(1).rolling(20, min_periods=5).mean()
    )
    daily["rolling_20d_gap_fill_rate"] = (
        daily["gap_filled"].astype(float).shift(1).rolling(20, min_periods=5).mean()
    )
    daily["rolling_20d_trend_day_rate"] = (
        daily["trend_day_flag"].astype(float).shift(1).rolling(20, min_periods=5).mean()
    )
    daily["ib_vs_rolling_median"] = daily["ib_range"] / daily["rolling_20d_ib_median"]

    return daily


def add_checkpoint_rollups(checkpoints: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    if checkpoints.empty:
        return checkpoints

    context_cols = [
        "date",
        "rolling_20d_ib_median",
        "rolling_20d_day_range_median",
        "rolling_20d_opposite_break_rate",
        "rolling_20d_gap_fill_rate",
        "rolling_20d_trend_day_rate",
    ]
    checkpoints = checkpoints.merge(daily[context_cols], on="date", how="left")
    checkpoints = checkpoints.sort_values(["checkpoint_minute", "date"]).reset_index(drop=True)
    checkpoints["range_vs_20d_checkpoint_median"] = (
        checkpoints.groupby("checkpoint_minute")["range_so_far"]
        .transform(lambda s: s.shift(1).rolling(20, min_periods=5).median())
    )
    checkpoints["range_so_far_vs_checkpoint_median"] = (
        checkpoints["range_so_far"] / checkpoints["range_vs_20d_checkpoint_median"]
    )
    checkpoints = checkpoints.sort_values(["date", "checkpoint_minute"]).reset_index(drop=True)

    return checkpoints


def assign_event_ids(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events

    events = events.sort_values(["date", "event_time", "event_type", "event_subtype"]).reset_index(drop=True)
    events["event_id"] = (
        events.groupby("date").cumcount().add(1).astype(str).str.zfill(3)
    )
    events["event_id"] = events["date"].astype(str) + "_" + events["event_id"]

    cols = ["event_id"] + [col for col in events.columns if col != "event_id"]
    return events[cols]


def build_features(master: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    event_rows_out: list[dict[str, Any]] = []

    prev_daily: dict[str, Any] | None = None

    for date_value, raw_day in master.groupby("date", sort=True):
        day = raw_day.sort_values("datetime").reset_index(drop=True)
        era = classify_era(date_value)
        ctx = DayContext(
            date=date_value,
            day=day,
            prev=prev_daily,
            era=era,
            era_flags=era_flags(era),
        )

        daily_row, aux = build_daily_row(ctx)
        daily_rows.append(daily_row)
        checkpoint_rows.extend(build_checkpoint_rows(ctx, daily_row))
        event_rows_out.extend(build_event_rows(ctx, daily_row, aux))

        prev_daily = {
            "date": date_value,
            "day_high": daily_row["day_high"],
            "day_low": daily_row["day_low"],
            "day_close": daily_row["day_close"],
            "day_range": daily_row["day_range"],
        }

    daily = add_daily_rollups(pd.DataFrame(daily_rows))
    checkpoints = add_checkpoint_rollups(pd.DataFrame(checkpoint_rows), daily)
    events = assign_event_ids(pd.DataFrame(event_rows_out))

    return daily, checkpoints, events


def save_outputs(
    daily: pd.DataFrame,
    checkpoints: pd.DataFrame,
    events: pd.DataFrame,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    daily.to_csv(output_dir / "daily_features.csv", index=False)
    checkpoints.to_csv(output_dir / "checkpoint_features.csv", index=False)
    events.to_csv(output_dir / "event_features.csv", index=False)


def print_summary(
    source_path: Path,
    daily: pd.DataFrame,
    checkpoints: pd.DataFrame,
    events: pd.DataFrame,
    output_dir: Path,
) -> None:
    print("\n" + "=" * 72)
    print("BANK NIFTY FEATURE FACTORY")
    print("=" * 72)
    print(f"Source: {source_path}")
    print(f"Output: {output_dir}")
    print()
    print(f"daily_features rows      : {len(daily):,}")
    print(f"checkpoint_features rows : {len(checkpoints):,}")
    print(f"event_features rows      : {len(events):,}")
    print()
    print("Priority labels")
    print("-" * 72)
    for col in [
        "label_50_before_opposite",
        "label_100_before_opposite",
        "label_opposite_break",
        "label_gap_fill",
        "label_trend_day",
    ]:
        if col in daily:
            value = daily[col].astype(float).mean() * 100
            print(f"{col:<32} {value:>6.2f}%")
    print()
    print("Event counts")
    print("-" * 72)
    print(events["event_type"].value_counts().to_string() if not events.empty else "No events")
    print("\nDone.")


def main() -> None:
    args = parse_args()
    source_path = Path(args.source)
    output_dir = Path(args.output_dir)

    master = load_master(source_path)
    daily, checkpoints, events = build_features(master)
    save_outputs(daily, checkpoints, events, output_dir)
    print_summary(source_path, daily, checkpoints, events, output_dir)


if __name__ == "__main__":
    main()
