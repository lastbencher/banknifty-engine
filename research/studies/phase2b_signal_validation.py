from __future__ import annotations

import argparse
from itertools import count
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEATURE_DIR = PROJECT_ROOT / "features"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "phase2b_signal_validation"
MIN_RULE_SESSIONS = 60
MIN_STABILITY_SESSIONS = 20


LABEL_COLS = [
    "label_50_before_opposite",
    "label_100_before_opposite",
    "label_opposite_break",
    "label_gap_fill",
    "label_trend_day",
]


KNOWN_DAILY_COLS = [
    "date",
    "first_break_direction",
    "first_break_hour",
    "ib_bucket",
    "ib_range",
    "minutes_to_50_after_first_break",
    "minutes_to_100_after_first_break",
    "speed_to_50_after_first_break",
    "speed_to_100_after_first_break",
    "trap_severity_score",
    *LABEL_COLS,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate early checkpoint signals for fast Bank Nifty moves."
    )
    parser.add_argument("--feature-dir", type=Path, default=DEFAULT_FEATURE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-sessions", type=int, default=MIN_RULE_SESSIONS)
    return parser.parse_args()


def pct(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return np.nan
    return clean.astype(float).mean() * 100


def median(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return np.nan
    return clean.median()


def safe_ratio(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return np.nan
    return numerator / denominator


def load_data(feature_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = pd.read_csv(feature_dir / "daily_features.csv", parse_dates=["date"])
    checkpoints = pd.read_csv(
        feature_dir / "checkpoint_features.csv",
        parse_dates=["date", "checkpoint_time"],
    )

    for frame in [daily, checkpoints]:
        for col in frame.columns:
            if col.startswith("label_") or col.startswith("is_") or col.startswith("gap_"):
                if frame[col].dtype == object and frame[col].dropna().isin(["True", "False"]).all():
                    frame[col] = frame[col].map({"True": True, "False": False}).astype("boolean")

    return daily, checkpoints


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


def prepare_validation_frame(daily: pd.DataFrame, checkpoints: pd.DataFrame) -> pd.DataFrame:
    df = checkpoints.merge(
        daily[KNOWN_DAILY_COLS],
        on="date",
        how="left",
        suffixes=("", "_daily"),
    )
    df = df[df["first_break_direction"].notna()].copy()
    df = df[df["is_valid_checkpoint"].astype(bool)].copy()

    for col in LABEL_COLS:
        df[col] = df[col].astype("boolean")

    df["gap_direction"] = df["gap_direction"].fillna("NONE")
    df["opening_direction"] = df["return_from_open_points"].apply(direction)
    df["opening_pressure"] = df["close_position_in_range_so_far"].apply(pressure_bucket)
    df["trap_count_bucket"] = df["failed_break_count"].apply(count_bucket)
    df["gap_state"] = df.apply(gap_state, axis=1)

    quantile_specs = [
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

    for source, bucket in quantile_specs:
        df = qbucket(df, source, bucket)

    return df


def base_rates(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for checkpoint, group in df.groupby("checkpoint_minute"):
        rows.append(
            {
                "checkpoint_minute": checkpoint,
                "sessions": len(group),
                "pct_50_before_opposite": pct(group["label_50_before_opposite"]),
                "pct_100_before_opposite": pct(group["label_100_before_opposite"]),
                "pct_opposite_break": pct(group["label_opposite_break"]),
                "median_minutes_to_50": median(group["minutes_to_50_after_first_break"]),
                "median_minutes_to_100": median(group["minutes_to_100_after_first_break"]),
            }
        )

    result = pd.DataFrame(rows).sort_values("checkpoint_minute")
    result.loc[len(result)] = {
        "checkpoint_minute": "ALL",
        "sessions": len(df),
        "pct_50_before_opposite": pct(df["label_50_before_opposite"]),
        "pct_100_before_opposite": pct(df["label_100_before_opposite"]),
        "pct_opposite_break": pct(df["label_opposite_break"]),
        "median_minutes_to_50": median(df["minutes_to_50_after_first_break"]),
        "median_minutes_to_100": median(df["minutes_to_100_after_first_break"]),
    }

    return result


def summarize_group(group: pd.DataFrame) -> dict[str, float | int]:
    return {
        "sessions": len(group),
        "pct_50_before_opposite": pct(group["label_50_before_opposite"]),
        "pct_100_before_opposite": pct(group["label_100_before_opposite"]),
        "pct_opposite_break": pct(group["label_opposite_break"]),
        "pct_gap_fill": pct(group["label_gap_fill"]),
        "pct_trend_day": pct(group["label_trend_day"]),
        "median_minutes_to_50": median(group["minutes_to_50_after_first_break"]),
        "median_minutes_to_100": median(group["minutes_to_100_after_first_break"]),
        "median_speed_to_50": median(group["speed_to_50_after_first_break"]),
        "median_speed_to_100": median(group["speed_to_100_after_first_break"]),
        "median_ib_range": median(group["ib_range"]),
        "median_trap_severity": median(group["trap_severity_score_daily"]),
    }


def rule_string(features: list[str], values: tuple[object, ...]) -> str:
    return " & ".join(f"{feature}={value}" for feature, value in zip(features, values))


def stability_metrics(
    group: pd.DataFrame,
    dimension: str,
    prefix: str,
) -> dict[str, float | int]:
    rows = []

    for value, segment in group.groupby(dimension, dropna=False):
        if len(segment) < MIN_STABILITY_SESSIONS:
            continue

        rows.append(
            {
                "value": value,
                "sessions": len(segment),
                "pct_50": pct(segment["label_50_before_opposite"]),
                "pct_100": pct(segment["label_100_before_opposite"]),
                "pct_opp": pct(segment["label_opposite_break"]),
            }
        )

    if not rows:
        return {
            f"{prefix}_coverage": 0,
            f"{prefix}_min_sessions": 0,
            f"{prefix}_min_50": np.nan,
            f"{prefix}_min_100": np.nan,
            f"{prefix}_std_100": np.nan,
            f"{prefix}_max_opposite": np.nan,
        }

    frame = pd.DataFrame(rows)
    return {
        f"{prefix}_coverage": len(frame),
        f"{prefix}_min_sessions": int(frame["sessions"].min()),
        f"{prefix}_min_50": frame["pct_50"].min(),
        f"{prefix}_min_100": frame["pct_100"].min(),
        f"{prefix}_std_100": frame["pct_100"].std(ddof=0),
        f"{prefix}_max_opposite": frame["pct_opp"].max(),
    }


def edge_score(row: pd.Series, base: dict[str, float]) -> float:
    sample_score = min(np.log1p(row["sessions"]) / np.log1p(600), 1.0)

    speed_score = 0.0
    if not pd.isna(row["median_minutes_to_100"]):
        speed_score = max(0.0, 1.0 - min(row["median_minutes_to_100"], 120) / 120)
    elif not pd.isna(row["median_minutes_to_50"]):
        speed_score = max(0.0, 1.0 - min(row["median_minutes_to_50"], 80) / 80)

    era_score = 0.0
    if row["era_coverage"] > 0 and not pd.isna(row["era_min_100"]):
        era_floor = safe_ratio(row["era_min_100"], base["pct_100_before_opposite"])
        era_variability = 1.0 - min((row["era_std_100"] or 0) / 50, 1)
        era_score = min(row["era_coverage"] / 4, 1) * era_floor * era_variability

    return (
        2.0 * (row["pct_100_before_opposite"] - base["pct_100_before_opposite"])
        + 1.0 * (row["pct_50_before_opposite"] - base["pct_50_before_opposite"])
        - 1.2 * (row["pct_opposite_break"] - base["pct_opposite_break"])
        + 10.0 * sample_score
        + 10.0 * speed_score
        + 10.0 * era_score
    )


def candidate_feature_sets() -> list[list[str]]:
    univariate = [
        "opening_direction",
        "opening_pressure",
        "gap_direction",
        "gap_state",
        "abs_speed_bucket",
        "range_speed_bucket",
        "directional_efficiency_bucket",
        "opening_range_pct_bucket",
        "range_vs_recent_bucket",
        "recent_opposite_rate_bucket",
        "recent_trend_rate_bucket",
        "prev_range_position_bucket",
        "trap_count_bucket",
    ]

    two_way = [
        ["range_speed_bucket", "directional_efficiency_bucket"],
        ["range_speed_bucket", "opening_direction"],
        ["range_speed_bucket", "gap_direction"],
        ["directional_efficiency_bucket", "opening_direction"],
        ["directional_efficiency_bucket", "gap_direction"],
        ["opening_pressure", "opening_direction"],
        ["opening_pressure", "gap_direction"],
        ["gap_direction", "gap_state"],
        ["gap_direction", "opening_direction"],
        ["range_vs_recent_bucket", "directional_efficiency_bucket"],
        ["range_vs_recent_bucket", "opening_direction"],
        ["recent_opposite_rate_bucket", "range_speed_bucket"],
        ["recent_trend_rate_bucket", "range_speed_bucket"],
        ["opening_range_pct_bucket", "directional_efficiency_bucket"],
        ["trap_count_bucket", "range_speed_bucket"],
        ["gap_fill_progress_bucket", "opening_direction"],
    ]

    three_way = [
        ["range_speed_bucket", "directional_efficiency_bucket", "gap_direction"],
        ["range_speed_bucket", "directional_efficiency_bucket", "opening_direction"],
        ["range_speed_bucket", "opening_pressure", "opening_direction"],
        ["gap_direction", "opening_direction", "range_speed_bucket"],
        ["gap_direction", "gap_state", "directional_efficiency_bucket"],
        ["range_vs_recent_bucket", "directional_efficiency_bucket", "opening_direction"],
        ["recent_opposite_rate_bucket", "range_speed_bucket", "directional_efficiency_bucket"],
    ]

    return [[feature] for feature in univariate] + two_way + three_way


def build_signal_table(df: pd.DataFrame, min_sessions: int) -> pd.DataFrame:
    base_all = base_rates(df)
    all_row = base_all[base_all["checkpoint_minute"].astype(str) == "ALL"].iloc[0].to_dict()
    rule_id = count(1)
    rows = []

    for feature_set in candidate_feature_sets():
        group_cols = ["checkpoint_minute", *feature_set]

        for keys, group in df.groupby(group_cols, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)

            if len(group) < min_sessions:
                continue

            checkpoint = keys[0]
            values = keys[1:]
            row = {
                "rule_id": f"S{next(rule_id):04d}",
                "checkpoint_minute": checkpoint,
                "feature_set": "+".join(feature_set),
                "rule": rule_string(feature_set, values),
            }
            row.update(summarize_group(group))
            row.update(stability_metrics(group, "era", "era"))
            row.update(stability_metrics(group, "first_break_direction", "direction"))
            rows.append(row)

    signals = pd.DataFrame(rows)

    if signals.empty:
        return signals

    signals["lift_50"] = signals["pct_50_before_opposite"].apply(
        lambda x: safe_ratio(x, all_row["pct_50_before_opposite"])
    )
    signals["lift_100"] = signals["pct_100_before_opposite"].apply(
        lambda x: safe_ratio(x, all_row["pct_100_before_opposite"])
    )
    signals["opposite_risk_ratio"] = signals["pct_opposite_break"].apply(
        lambda x: safe_ratio(x, all_row["pct_opposite_break"])
    )
    signals["edge_score"] = signals.apply(edge_score, axis=1, base=all_row)

    sort_cols = [
        "edge_score",
        "pct_100_before_opposite",
        "pct_50_before_opposite",
        "sessions",
    ]

    return signals.sort_values(sort_cols, ascending=[False, False, False, False]).reset_index(drop=True)


def build_stability_tables(df: pd.DataFrame, signals: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    era_rows = []
    direction_rows = []

    top = signals.head(100)

    for _, signal in top.iterrows():
        features = signal["feature_set"].split("+")
        mask = df["checkpoint_minute"].eq(signal["checkpoint_minute"])

        for feature, value in zip(features, signal["rule"].split(" & ")):
            actual_value = value.split("=", 1)[1]
            mask &= df[feature].astype(str).eq(actual_value)

        group = df[mask]

        for era, segment in group.groupby("era"):
            era_rows.append(
                {
                    "rule_id": signal["rule_id"],
                    "era": era,
                    **summarize_group(segment),
                }
            )

        for direction_value, segment in group.groupby("first_break_direction"):
            direction_rows.append(
                {
                    "rule_id": signal["rule_id"],
                    "first_break_direction": direction_value,
                    **summarize_group(segment),
                }
            )

    return pd.DataFrame(era_rows), pd.DataFrame(direction_rows)


def write_report(
    output_dir: Path,
    base: pd.DataFrame,
    signals: pd.DataFrame,
    top50: pd.DataFrame,
    top100: pd.DataFrame,
    low_opp: pd.DataFrame,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    all_base = base[base["checkpoint_minute"].astype(str) == "ALL"].iloc[0]
    lines = [
        "# Phase 2B Signal Validation",
        "",
        "Inputs: canonical `daily_features` and `checkpoint_features` only.",
        "Signals use checkpoint-known features. Future labels are used only for validation.",
        "",
        "## Base Rates",
        "",
        f"Sessions per checkpoint: {int(all_base['sessions']):,}",
        f"50 before opposite break: {all_base['pct_50_before_opposite']:.2f}%",
        f"100 before opposite break: {all_base['pct_100_before_opposite']:.2f}%",
        f"Opposite break: {all_base['pct_opposite_break']:.2f}%",
        "",
        "## Best Overall Signals",
        "",
        table(signals.head(15)),
        "",
        "## Best 50-Point Signals",
        "",
        table(top50.head(15)),
        "",
        "## Best 100-Point Signals",
        "",
        table(top100.head(15)),
        "",
        "## Lowest Opposite-Break Risk Signals",
        "",
        table(low_opp.head(15)),
        "",
    ]

    (output_dir / "phase2b_signal_validation_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"

    display_cols = [
        "rule_id",
        "checkpoint_minute",
        "sessions",
        "rule",
        "edge_score",
        "pct_50_before_opposite",
        "pct_100_before_opposite",
        "pct_opposite_break",
        "median_minutes_to_50",
        "median_minutes_to_100",
        "era_coverage",
        "era_min_100",
    ]
    data = frame[[col for col in display_cols if col in frame.columns]].copy()

    for col in data.columns:
        if pd.api.types.is_float_dtype(data[col]):
            data[col] = data[col].map(lambda x: "" if pd.isna(x) else f"{x:.2f}")
        else:
            data[col] = data[col].map(lambda x: "" if pd.isna(x) else str(x))

    headers = list(data.columns)
    rows = data.values.tolist()
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
            *["| " + " | ".join(row) + " |" for row in rows],
        ]
    )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    daily, checkpoints = load_data(args.feature_dir)
    validation = prepare_validation_frame(daily, checkpoints)

    base = base_rates(validation)
    signals = build_signal_table(validation, args.min_sessions)

    if signals.empty:
        raise RuntimeError("No candidate signals passed the minimum session threshold.")

    top50 = signals.sort_values(
        ["pct_50_before_opposite", "pct_100_before_opposite", "sessions"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    top100 = signals.sort_values(
        ["pct_100_before_opposite", "pct_50_before_opposite", "sessions"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    low_opp = signals.sort_values(
        ["pct_opposite_break", "pct_100_before_opposite", "sessions"],
        ascending=[True, False, False],
    ).reset_index(drop=True)
    era_stability, direction_stability = build_stability_tables(validation, signals)

    base.to_csv(args.output_dir / "checkpoint_base_rates.csv", index=False)
    signals.to_csv(args.output_dir / "ranked_fast_move_signals.csv", index=False)
    top50.head(100).to_csv(args.output_dir / "top_50_before_opposite_signals.csv", index=False)
    top100.head(100).to_csv(args.output_dir / "top_100_before_opposite_signals.csv", index=False)
    low_opp.head(100).to_csv(args.output_dir / "low_opposite_break_risk_signals.csv", index=False)
    era_stability.to_csv(args.output_dir / "era_stability_by_signal.csv", index=False)
    direction_stability.to_csv(args.output_dir / "first_break_direction_by_signal.csv", index=False)

    write_report(args.output_dir, base, signals, top50, top100, low_opp)

    all_base = base[base["checkpoint_minute"].astype(str) == "ALL"].iloc[0]
    best = signals.iloc[0]

    print("\n" + "=" * 72)
    print("PHASE 2B SIGNAL VALIDATION")
    print("=" * 72)
    print(f"Feature dir : {args.feature_dir}")
    print(f"Output dir  : {args.output_dir}")
    print(f"Candidate signals passing threshold: {len(signals):,}")
    print()
    print("Base")
    print(f"50 before opposite : {all_base['pct_50_before_opposite']:.2f}%")
    print(f"100 before opposite: {all_base['pct_100_before_opposite']:.2f}%")
    print(f"Opposite break     : {all_base['pct_opposite_break']:.2f}%")
    print()
    print("Best ranked signal")
    print(f"{best['rule_id']} | {best['checkpoint_minute']}m | {best['rule']}")
    print(f"sessions={int(best['sessions'])}, score={best['edge_score']:.2f}")
    print(f"50={best['pct_50_before_opposite']:.2f}%, 100={best['pct_100_before_opposite']:.2f}%, opposite={best['pct_opposite_break']:.2f}%")
    print("\nDone.")


if __name__ == "__main__":
    main()
