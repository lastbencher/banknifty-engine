from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

KNOWN_DAILY_COLS = [
    "date",
    "first_break_direction",
    "first_break_hour",
    "ib_bucket",
    "ib_range",
    "ib_high",
    "ib_low",
    "minutes_to_50_after_first_break",
    "minutes_to_100_after_first_break",
    "speed_to_50_after_first_break",
    "speed_to_100_after_first_break",
    "trap_severity_score",
    "label_50_before_opposite",
    "label_100_before_opposite",
    "label_opposite_break",
    "label_gap_fill",
    "label_trend_day",
]

QUANTILE_SPECS = [
    ("abs_speed_points_per_min", "abs_speed_bucket"),
    ("range_speed_points_per_min", "range_speed_bucket"),
    ("directional_efficiency", "directional_efficiency_bucket"),
    ("opening_range_pct", "opening_range_pct_bucket"),
    ("gap_fill_progress_pct", "gap_fill_progress_bucket"),
    ("range_so_far_vs_checkpoint_median", "range_vs_recent_bucket"),
    ("rolling_20d_opposite_break_rate", "recent_opposite_rate_bucket"),
    ("rolling_20d_trend_day_rate", "recent_trend_rate_bucket"),
    ("position_vs_prev_range", "prev_range_position_bucket"),
]


def direction(value: float) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    if value > 0:
        return "UP"
    if value < 0:
        return "DOWN"
    return "FLAT"


def pressure_bucket(value: float) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    if value >= 0.67:
        return "UPPER_THIRD"
    if value <= 0.33:
        return "LOWER_THIRD"
    return "MIDDLE_THIRD"


def count_bucket(value: float) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    if value == 0:
        return "0"
    if value <= 2:
        return "1-2"
    if value <= 5:
        return "3-5"
    return "6+"


def gap_state(row: pd.Series) -> str:
    gap_direction = row.get("gap_direction")

    if pd.isna(gap_direction) or gap_direction in {"NONE", "FLAT"}:
        return "NO_GAP"
    if bool(row.get("gap_filled_by_checkpoint", False)):
        return "GAP_FILLED_BY_CHECKPOINT"
    if bool(row.get("gap_sustaining_by_checkpoint", False)):
        return "GAP_SUSTAINING"
    return "GAP_OPEN_UNFILLED"


def qbucket(
    df: pd.DataFrame,
    source_col: str,
    bucket_col: str,
    by_col: str = "checkpoint_minute",
    labels: Iterable[str] = ("Q1_LOW", "Q2", "Q3", "Q4_HIGH"),
) -> pd.DataFrame:
    df = df.copy()
    labels = tuple(labels)
    df[bucket_col] = "UNKNOWN"

    for _, idx in df.groupby(by_col).groups.items():
        values = df.loc[idx, source_col]
        valid_idx = values.dropna().index

        if len(valid_idx) < len(labels):
            continue

        ranked = values.loc[valid_idx].rank(method="first")
        df.loc[valid_idx, bucket_col] = pd.qcut(
            ranked,
            q=len(labels),
            labels=labels,
        ).astype(str)

    return df


def prepare_checkpoint_frame(
    daily: pd.DataFrame,
    checkpoints: pd.DataFrame,
    *,
    require_first_break: bool = True,
) -> pd.DataFrame:
    daily_cols = [col for col in KNOWN_DAILY_COLS if col in daily.columns]
    df = checkpoints.merge(daily[daily_cols], on="date", how="left", suffixes=("", "_daily"))

    if require_first_break and "first_break_direction" in df.columns:
        df = df[df["first_break_direction"].notna()].copy()

    df = df[df["is_valid_checkpoint"].astype(bool)].copy()

    for col in [c for c in df.columns if c.startswith("label_")]:
        if col in df.columns:
            df[col] = df[col].astype("boolean")

    df["gap_direction"] = df["gap_direction"].fillna("NONE")
    df["opening_direction"] = df["return_from_open_points"].apply(direction)
    df["opening_pressure"] = df["close_position_in_range_so_far"].apply(pressure_bucket)
    df["trap_count_bucket"] = df["failed_break_count"].apply(count_bucket)
    df["gap_state"] = df.apply(gap_state, axis=1)

    for source, bucket in QUANTILE_SPECS:
        if source in df.columns:
            df = qbucket(df, source, bucket)

    return df


def row_matches_conditions(row: pd.Series, conditions: dict[str, str]) -> bool:
    for feature, expected in conditions.items():
        actual = row.get(feature)
        if pd.isna(actual):
            return False
        if str(actual) != expected:
            return False
    return True
