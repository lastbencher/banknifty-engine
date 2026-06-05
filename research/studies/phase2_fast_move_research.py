from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEATURE_DIR = PROJECT_ROOT / "features"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "phase2_fast_moves"
MIN_SLICE_COUNT = 40


LABELS = [
    "label_50_before_opposite",
    "label_100_before_opposite",
    "label_opposite_break",
    "label_gap_fill",
    "label_trend_day",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2: fast 50/100 point move research from canonical features."
    )
    parser.add_argument(
        "--feature-dir",
        default=DEFAULT_FEATURE_DIR,
        type=Path,
        help="Directory containing daily_features.csv, checkpoint_features.csv, and event_features.csv.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Directory where Phase 2 research outputs will be written.",
    )
    return parser.parse_args()


def load_features(feature_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = pd.read_csv(feature_dir / "daily_features.csv", parse_dates=[
        "date",
        "first_break_time",
        "opposite_break_time",
        "first_50_hit_time",
        "first_100_hit_time",
    ])
    checkpoints = pd.read_csv(feature_dir / "checkpoint_features.csv", parse_dates=[
        "date",
        "checkpoint_time",
    ])
    events = pd.read_csv(feature_dir / "event_features.csv", parse_dates=[
        "date",
        "event_time",
        "anchor_time",
    ])

    for frame in [daily, checkpoints, events]:
        for col in frame.columns:
            if col.startswith("label_") or col in [
                "opposite_break",
                "hit_50_after_first_break",
                "hit_100_after_first_break",
                "trend_day_flag",
                "gap_filled",
            ]:
                frame[col] = frame[col].astype("boolean")

    return daily, checkpoints, events


def pct(series: pd.Series) -> float:
    numeric = series.astype(float)
    if numeric.empty:
        return np.nan
    return numeric.mean() * 100


def median_or_nan(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return np.nan
    return clean.median()


def bucket_count(value: float) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    if value == 0:
        return "0"
    if value <= 2:
        return "1-2"
    if value <= 5:
        return "3-5"
    return "6+"


def bucket_hour(value: float) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    hour = int(value)
    if hour <= 10:
        return "09-10"
    if hour == 11:
        return "11"
    if hour == 12:
        return "12"
    if hour == 13:
        return "13"
    if hour == 14:
        return "14"
    return "15+"


def add_quantile_bucket(
    df: pd.DataFrame,
    source_col: str,
    bucket_col: str,
    labels: Iterable[str] = ("Q1_LOW", "Q2", "Q3", "Q4_HIGH"),
    by_col: str | None = None,
) -> pd.DataFrame:
    df = df.copy()
    df[bucket_col] = "UNKNOWN"

    if by_col is None:
        groups = [(None, df.index)]
    else:
        groups = df.groupby(by_col).groups.items()

    for _, idx in groups:
        values = df.loc[idx, source_col]
        valid_idx = values.dropna().index

        if len(valid_idx) < len(tuple(labels)):
            continue

        ranked = values.loc[valid_idx].rank(method="first")
        df.loc[valid_idx, bucket_col] = pd.qcut(
            ranked,
            q=len(tuple(labels)),
            labels=tuple(labels),
        ).astype(str)

    return df


def summarize(
    df: pd.DataFrame,
    group_cols: list[str],
    min_count: int = 0,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        if len(group) < min_count:
            continue

        row = {col: key for col, key in zip(group_cols, keys)}
        row.update(
            {
                "sessions": len(group),
                "pct_50_before_opposite": pct(group["label_50_before_opposite"]),
                "pct_100_before_opposite": pct(group["label_100_before_opposite"]),
                "pct_opposite_break": pct(group["label_opposite_break"]),
                "pct_gap_fill": pct(group["label_gap_fill"]),
                "pct_trend_day": pct(group["label_trend_day"]),
                "median_minutes_to_50": median_or_nan(group["minutes_to_50_after_first_break"]),
                "median_minutes_to_100": median_or_nan(group["minutes_to_100_after_first_break"]),
                "median_speed_to_50": median_or_nan(group["speed_to_50_after_first_break"]),
                "median_speed_to_100": median_or_nan(group["speed_to_100_after_first_break"]),
                "median_ib_range": median_or_nan(group["ib_range"]),
                "median_trap_severity": median_or_nan(group["trap_severity_score"]),
            }
        )
        rows.append(row)

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    return result.sort_values(
        ["pct_50_before_opposite", "pct_100_before_opposite", "sessions"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def build_daily_research(daily: pd.DataFrame) -> dict[str, pd.DataFrame]:
    research = daily[daily["first_break_direction"].notna()].copy()
    research["failed_break_bucket"] = research["failed_break_count"].apply(bucket_count)
    research["trap_before_move_bucket"] = research["trap_count_before_move"].apply(bucket_count)
    research["first_break_hour_bucket"] = research["first_break_hour"].apply(bucket_hour)
    research["gap_abs_points"] = research["gap_points"].abs()
    research["gap_direction"] = research["gap_direction"].fillna("NONE")
    research["ib_bucket"] = research["ib_bucket"].fillna("UNKNOWN")

    research = add_quantile_bucket(
        research,
        "gap_abs_points",
        "gap_size_bucket",
        labels=("Q1_SMALL", "Q2", "Q3", "Q4_LARGE"),
    )
    research = add_quantile_bucket(
        research,
        "trap_severity_score",
        "trap_severity_bucket",
        labels=("Q1_LOW", "Q2", "Q3", "Q4_HIGH"),
    )

    outputs = {
        "overall_summary": pd.DataFrame(
            [
                {
                    "population": "all_sessions",
                    "sessions": len(daily),
                    "first_break_sessions": daily["first_break_direction"].notna().sum(),
                    "pct_50_before_opposite": pct(daily["label_50_before_opposite"]),
                    "pct_100_before_opposite": pct(daily["label_100_before_opposite"]),
                    "pct_opposite_break": pct(daily["label_opposite_break"]),
                    "pct_gap_fill": pct(daily["label_gap_fill"]),
                    "pct_trend_day": pct(daily["label_trend_day"]),
                },
                {
                    "population": "first_break_sessions",
                    "sessions": len(research),
                    "first_break_sessions": len(research),
                    "pct_50_before_opposite": pct(research["label_50_before_opposite"]),
                    "pct_100_before_opposite": pct(research["label_100_before_opposite"]),
                    "pct_opposite_break": pct(research["label_opposite_break"]),
                    "pct_gap_fill": pct(research["label_gap_fill"]),
                    "pct_trend_day": pct(research["label_trend_day"]),
                },
            ]
        ),
        "era_summary": summarize(research, ["era"]),
        "first_break_direction_summary": summarize(research, ["first_break_direction"]),
        "ib_bucket_summary": summarize(research, ["ib_bucket"]),
        "first_break_hour_summary": summarize(research, ["first_break_hour_bucket"]),
        "gap_summary": summarize(research, ["gap_direction", "gap_size_bucket"], min_count=MIN_SLICE_COUNT),
        "trap_summary": summarize(research, ["failed_break_bucket", "trap_severity_bucket"], min_count=MIN_SLICE_COUNT),
        "era_direction_summary": summarize(research, ["era", "first_break_direction"], min_count=MIN_SLICE_COUNT),
    }

    return outputs


def build_checkpoint_research(
    daily: pd.DataFrame,
    checkpoints: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    label_cols = [
        "date",
        "first_break_direction",
        "ib_bucket",
        "label_50_before_opposite",
        "label_100_before_opposite",
        "label_opposite_break",
        "label_gap_fill",
        "label_trend_day",
        "minutes_to_50_after_first_break",
        "minutes_to_100_after_first_break",
        "speed_to_50_after_first_break",
        "speed_to_100_after_first_break",
        "ib_range",
        "trap_severity_score",
    ]

    cp = checkpoints.merge(daily[label_cols], on="date", how="left", suffixes=("", "_daily"))
    cp = cp[cp["first_break_direction"].notna()].copy()
    cp["gap_direction"] = cp["gap_direction"].fillna("NONE")

    bucket_specs = [
        ("abs_speed_points_per_min", "abs_speed_bucket"),
        ("range_speed_points_per_min", "range_speed_bucket"),
        ("directional_efficiency", "directional_efficiency_bucket"),
        ("opening_range_pct", "opening_range_pct_bucket"),
        ("gap_fill_progress_pct", "gap_fill_progress_bucket"),
    ]

    for source, bucket in bucket_specs:
        cp = add_quantile_bucket(cp, source, bucket, by_col="checkpoint_minute")

    checkpoint_summary = summarize(cp, ["checkpoint_minute"])

    univariate_rows: list[pd.DataFrame] = []
    for bucket in [spec[1] for spec in bucket_specs]:
        summary = summarize(cp, ["checkpoint_minute", bucket], min_count=MIN_SLICE_COUNT)
        summary.insert(1, "feature", bucket)
        summary = summary.rename(columns={bucket: "bucket"})
        univariate_rows.append(summary)

    checkpoint_univariate = (
        pd.concat(univariate_rows, ignore_index=True)
        if univariate_rows
        else pd.DataFrame()
    )

    candidate_cols = [
        "checkpoint_minute",
        "range_speed_bucket",
        "directional_efficiency_bucket",
        "gap_direction",
        "era",
    ]
    candidate_slices = summarize(cp, candidate_cols, min_count=MIN_SLICE_COUNT)

    if not candidate_slices.empty:
        base_50 = pct(cp["label_50_before_opposite"])
        base_100 = pct(cp["label_100_before_opposite"])
        candidate_slices["lift_50_vs_checkpoint_base"] = (
            candidate_slices["pct_50_before_opposite"] / base_50
        )
        candidate_slices["lift_100_vs_checkpoint_base"] = (
            candidate_slices["pct_100_before_opposite"] / base_100
        )
        candidate_slices = candidate_slices.sort_values(
            [
                "pct_50_before_opposite",
                "pct_100_before_opposite",
                "pct_opposite_break",
                "sessions",
            ],
            ascending=[False, False, True, False],
        ).reset_index(drop=True)

    return {
        "checkpoint_summary": checkpoint_summary,
        "checkpoint_univariate_summary": checkpoint_univariate,
        "checkpoint_candidate_slices": candidate_slices,
    }


def build_event_research(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    point_moves = events[events["event_type"] == "POINT_MOVE"].copy()

    event_speed_summary = (
        point_moves.groupby(["event_subtype", "event_direction"], dropna=False)
        .agg(
            events=("event_id", "count"),
            median_event_minute=("event_minute", "median"),
            median_minutes_from_anchor=("minutes_from_anchor", "median"),
            median_speed_points_per_min=("speed_points_per_min", "median"),
            median_speed_ib_per_min=("speed_ib_per_min", "median"),
            pct_before_opposite=("event_before_opposite_break", lambda s: pct(s)),
            median_trap_count_before_move=("trap_count_before_move", "median"),
            median_trap_severity=("trap_severity_score", "median"),
        )
        .reset_index()
        .sort_values(["event_subtype", "event_direction"])
    )

    trap_events = events[events["event_type"] == "TRAP"].copy()
    trap_event_summary = (
        trap_events.groupby(["event_subtype", "event_direction"], dropna=False)
        .agg(
            events=("event_id", "count"),
            median_event_minute=("event_minute", "median"),
            median_move_points=("move_points", "median"),
            median_speed_points_per_min=("speed_points_per_min", "median"),
        )
        .reset_index()
        .sort_values("events", ascending=False)
    )

    return {
        "event_speed_summary": event_speed_summary,
        "trap_event_summary": trap_event_summary,
    }


def write_outputs(outputs: dict[str, pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, frame in outputs.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)


def format_pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.2f}%"


def markdown_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_No rows._"

    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)

    for col in data.columns:
        if pd.api.types.is_float_dtype(data[col]):
            data[col] = data[col].map(lambda x: "" if pd.isna(x) else f"{x:.2f}")
        else:
            data[col] = data[col].map(lambda x: "" if pd.isna(x) else str(x))

    headers = list(data.columns)
    rows = data.astype(str).values.tolist()

    header_line = "| " + " | ".join(headers) + " |"
    divider_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = ["| " + " | ".join(row) + " |" for row in rows]

    return "\n".join([header_line, divider_line, *body_lines])


def build_report(outputs: dict[str, pd.DataFrame], output_dir: Path) -> None:
    overall = outputs["overall_summary"]
    first_break = overall[overall["population"] == "first_break_sessions"].iloc[0]
    all_sessions = overall[overall["population"] == "all_sessions"].iloc[0]

    top_candidates = outputs["checkpoint_candidate_slices"].head(10)
    era = outputs["era_summary"]
    direction = outputs["first_break_direction_summary"]
    event_speed = outputs["event_speed_summary"]

    lines = [
        "# Phase 2 Fast Move Research",
        "",
        "Source inputs: canonical `daily_features`, `checkpoint_features`, and `event_features` only.",
        "No raw minute-bar reprocessing is used in this study.",
        "",
        "## Priority Rates",
        "",
        f"All sessions: {int(all_sessions['sessions']):,}",
        f"First-break sessions: {int(first_break['sessions']):,}",
        "",
        f"50 points before opposite break: {format_pct(first_break['pct_50_before_opposite'])}",
        f"100 points before opposite break: {format_pct(first_break['pct_100_before_opposite'])}",
        f"Opposite break rate: {format_pct(first_break['pct_opposite_break'])}",
        f"Gap fill rate: {format_pct(first_break['pct_gap_fill'])}",
        f"Trend day rate: {format_pct(first_break['pct_trend_day'])}",
        "",
        "## Era Summary",
        "",
        markdown_table(era),
        "",
        "## First Break Direction Summary",
        "",
        markdown_table(direction),
        "",
        "## Top Checkpoint Candidate Slices",
        "",
        markdown_table(top_candidates),
        "",
        "## Point Move Speed Summary",
        "",
        markdown_table(event_speed),
        "",
        "## Output Files",
        "",
    ]

    for path in sorted(output_dir.glob("*.csv")):
        lines.append(f"- `{path.name}`")

    (output_dir / "phase2_fast_move_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    daily, checkpoints, events = load_features(args.feature_dir)

    outputs: dict[str, pd.DataFrame] = {}
    outputs.update(build_daily_research(daily))
    outputs.update(build_checkpoint_research(daily, checkpoints))
    outputs.update(build_event_research(events))

    write_outputs(outputs, args.output_dir)
    build_report(outputs, args.output_dir)

    overall = outputs["overall_summary"]
    first_break = overall[overall["population"] == "first_break_sessions"].iloc[0]

    print("\n" + "=" * 72)
    print("PHASE 2 FAST MOVE RESEARCH")
    print("=" * 72)
    print(f"Feature dir : {args.feature_dir}")
    print(f"Output dir  : {args.output_dir}")
    print()
    print(f"First-break sessions       : {int(first_break['sessions']):,}")
    print(f"50 before opposite break   : {first_break['pct_50_before_opposite']:.2f}%")
    print(f"100 before opposite break  : {first_break['pct_100_before_opposite']:.2f}%")
    print(f"Opposite break rate        : {first_break['pct_opposite_break']:.2f}%")
    print()
    print("Top checkpoint slices saved to checkpoint_candidate_slices.csv")
    print("Report saved to phase2_fast_move_report.md")
    print("\nDone.")


if __name__ == "__main__":
    main()
