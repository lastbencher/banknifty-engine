from __future__ import annotations

from typing import Iterable, Literal

import numpy as np
import pandas as pd

BucketMode = Literal["full", "walkforward"]

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

DEFAULT_WALKFORWARD_MIN_SESSIONS = 60
DEFAULT_WALKFORWARD_WINDOW = 252
BUCKET_LABELS = ("Q1_LOW", "Q2", "Q3", "Q4_HIGH")


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


def assign_quantile_bucket(
    value: float,
    reference: pd.Series,
    labels: Iterable[str] = BUCKET_LABELS,
) -> str:
    labels = tuple(labels)
    ref = reference.dropna()

    if pd.isna(value) or len(ref) < len(labels):
        return "UNKNOWN"

    ranked = ref.rank(method="first")
    try:
        ref_buckets = pd.qcut(ranked, q=len(labels), labels=labels)
    except ValueError:
        return "UNKNOWN"

    for label in labels:
        bucket_values = ref[ref_buckets == label]
        if bucket_values.empty:
            continue
        if bucket_values.min() <= value <= bucket_values.max():
            return label

    if value <= ref.min():
        return labels[0]
    return labels[-1]


def qbucket(
    df: pd.DataFrame,
    source_col: str,
    bucket_col: str,
    by_col: str = "checkpoint_minute",
    labels: Iterable[str] = BUCKET_LABELS,
) -> pd.DataFrame:
    """In-sample quartiles across all dates (research only — has look-ahead bias)."""
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


def qbucket_walkforward(
    df: pd.DataFrame,
    source_col: str,
    bucket_col: str,
    *,
    by_col: str = "checkpoint_minute",
    min_sessions: int = DEFAULT_WALKFORWARD_MIN_SESSIONS,
    window: int = DEFAULT_WALKFORWARD_WINDOW,
    labels: Iterable[str] = BUCKET_LABELS,
) -> pd.DataFrame:
    """Quartile buckets using only prior sessions (no look-ahead)."""
    df = df.copy()
    labels = tuple(labels)
    df[bucket_col] = "UNKNOWN"
    df["_sort_date"] = pd.to_datetime(df["date"])

    for _, idx in df.groupby(by_col).groups.items():
        group = df.loc[idx].sort_values("_sort_date")
        history_values: list[float] = []

        for row_idx, row in group.iterrows():
            if len(history_values) >= min_sessions:
                ref = pd.Series(history_values[-window:])
                df.at[row_idx, bucket_col] = assign_quantile_bucket(
                    row[source_col],
                    ref,
                    labels=labels,
                )

            value = row[source_col]
            if pd.notna(value):
                history_values.append(float(value))

    return df.drop(columns=["_sort_date"])


def prepare_checkpoint_frame(
    daily: pd.DataFrame,
    checkpoints: pd.DataFrame,
    *,
    require_first_break: bool = True,
    bucket_mode: BucketMode = "full",
    walkforward_min_sessions: int = DEFAULT_WALKFORWARD_MIN_SESSIONS,
    walkforward_window: int = DEFAULT_WALKFORWARD_WINDOW,
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

    bucket_fn = qbucket if bucket_mode == "full" else qbucket_walkforward
    bucket_kwargs = (
        {}
        if bucket_mode == "full"
        else {
            "min_sessions": walkforward_min_sessions,
            "window": walkforward_window,
        }
    )

    for source, bucket in QUANTILE_SPECS:
        if source in df.columns:
            df = bucket_fn(df, source, bucket, **bucket_kwargs)

    return df


def row_matches_conditions(row: pd.Series, conditions: dict[str, str]) -> bool:
    for feature, expected in conditions.items():
        actual = row.get(feature)
        if pd.isna(actual):
            return False
        if str(actual) != expected:
            return False
    return True
