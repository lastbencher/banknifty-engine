from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_FEATURE_DIR = Path("features")
DEFAULT_REPORT = Path("features/phase_2b_audit.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Phase 2B feature outputs for coverage, consistency, and leakage risk."
    )
    parser.add_argument("--feature-dir", type=Path, default=DEFAULT_FEATURE_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def percent(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value * 100:.2f}%"


def pct_missing(series: pd.Series) -> float:
    return float(series.isna().mean())


def bool_rate(series: pd.Series) -> float:
    return float(series.fillna(False).astype(bool).mean())


def add_section(lines: list[str], title: str) -> None:
    lines.extend(["", f"## {title}", ""])


def markdown_table(rows: Iterable[dict[str, object]]) -> list[str]:
    rows = list(rows)
    if not rows:
        return ["No rows."]

    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return lines


def load_outputs(feature_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = pd.read_csv(feature_dir / "daily_features.csv", parse_dates=["date"])
    checkpoints = pd.read_csv(feature_dir / "checkpoint_features.csv", parse_dates=["date"])
    events = pd.read_csv(feature_dir / "event_features.csv", parse_dates=["date"])
    return daily, checkpoints, events


def audit_daily(daily: pd.DataFrame) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    warnings: list[str] = []

    duplicate_dates = int(daily["date"].duplicated().sum())
    incomplete_sessions = int((~daily["is_complete_session"].astype(bool)).sum())

    if duplicate_dates:
        warnings.append(f"Daily table has {duplicate_dates} duplicate dates.")

    if incomplete_sessions:
        warnings.append(f"Daily table has {incomplete_sessions} incomplete sessions.")

    rows = [
        {"Metric": "Rows", "Value": f"{len(daily):,}"},
        {"Metric": "Date range", "Value": f"{daily['date'].min().date()} to {daily['date'].max().date()}"},
        {"Metric": "Duplicate dates", "Value": duplicate_dates},
        {"Metric": "Incomplete sessions", "Value": incomplete_sessions},
        {"Metric": "Median IB range", "Value": f"{daily['ib_range'].median():.2f}"},
        {"Metric": "Median day range", "Value": f"{daily['day_range'].median():.2f}"},
    ]
    lines.extend(markdown_table(rows))

    label_cols = [col for col in daily.columns if col.startswith("label_")]
    label_rows = [
        {
            "Label": col,
            "Positive rate": percent(bool_rate(daily[col])),
            "Missing": percent(pct_missing(daily[col])),
        }
        for col in label_cols
    ]
    add_section(lines, "Daily Labels")
    lines.extend(markdown_table(label_rows))

    missing_rows = []
    for col in daily.columns:
        missing = pct_missing(daily[col])
        if missing >= 0.20:
            missing_rows.append({"Column": col, "Missing": percent(missing)})
    missing_rows = sorted(missing_rows, key=lambda row: row["Missing"], reverse=True)
    add_section(lines, "High Missingness Columns")
    lines.extend(markdown_table(missing_rows[:25]))

    incomplete = daily.loc[
        ~daily["is_complete_session"].astype(bool),
        ["date", "bars_count", "session_start", "session_end"],
    ].copy()
    add_section(lines, "Incomplete Sessions")
    if incomplete.empty:
        lines.append("No incomplete sessions found.")
    else:
        incomplete["date"] = incomplete["date"].dt.date
        lines.extend(markdown_table(incomplete.to_dict("records")))

    leak_like_cols = [
        col
        for col in daily.columns
        if any(token in col for token in ["after_first_break", "opposite", "trend_day", "day_high", "day_low", "day_close"])
        and not col.startswith("label_")
    ]
    add_section(lines, "Leakage Watchlist")
    lines.append(
        "Columns below may be useful labels or post-event analysis fields, but should not be used as pre-open or early-checkpoint predictors."
    )
    lines.extend(markdown_table({"Column": col} for col in leak_like_cols))

    return lines, warnings


def audit_checkpoints(checkpoints: pd.DataFrame, daily: pd.DataFrame) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    warnings: list[str] = []

    expected_rows = len(daily) * checkpoints["checkpoint_minute"].nunique()
    invalid_rows = int((~checkpoints["is_valid_checkpoint"].astype(bool)).sum())
    duplicate_keys = int(checkpoints.duplicated(["date", "checkpoint_minute"]).sum())

    if len(checkpoints) != expected_rows:
        warnings.append(
            f"Checkpoint row count is {len(checkpoints):,}; expected {expected_rows:,} from daily rows x checkpoint count."
        )

    if duplicate_keys:
        warnings.append(f"Checkpoint table has {duplicate_keys} duplicate date/checkpoint keys.")

    rows = [
        {"Metric": "Rows", "Value": f"{len(checkpoints):,}"},
        {"Metric": "Checkpoint minutes", "Value": ", ".join(map(str, sorted(checkpoints["checkpoint_minute"].unique())))},
        {"Metric": "Expected rows", "Value": f"{expected_rows:,}"},
        {"Metric": "Invalid checkpoints", "Value": invalid_rows},
        {"Metric": "Duplicate keys", "Value": duplicate_keys},
    ]
    lines.extend(markdown_table(rows))

    by_minute = []
    for minute, group in checkpoints.groupby("checkpoint_minute"):
        by_minute.append(
            {
                "Minute": int(minute),
                "Median range": f"{group['range_so_far'].median():.2f}",
                "Median abs speed": f"{group['abs_speed_points_per_min'].median():.2f}",
                "Gap filled rate": percent(bool_rate(group["gap_filled_by_checkpoint"])),
            }
        )
    add_section(lines, "Checkpoint Profiles")
    lines.extend(markdown_table(by_minute))

    return lines, warnings


def audit_events(events: pd.DataFrame, daily: pd.DataFrame) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    warnings: list[str] = []

    duplicate_event_ids = int(events["event_id"].duplicated().sum())
    events_without_daily = int((~events["date"].isin(daily["date"])).sum())

    if duplicate_event_ids:
        warnings.append(f"Event table has {duplicate_event_ids} duplicate event ids.")

    if events_without_daily:
        warnings.append(f"Event table has {events_without_daily} rows without matching daily dates.")

    rows = [
        {"Metric": "Rows", "Value": f"{len(events):,}"},
        {"Metric": "Duplicate event ids", "Value": duplicate_event_ids},
        {"Metric": "Rows without daily match", "Value": events_without_daily},
        {"Metric": "Median events per day", "Value": f"{events.groupby('date').size().median():.1f}"},
    ]
    lines.extend(markdown_table(rows))

    event_counts = (
        events["event_type"]
        .value_counts()
        .rename_axis("Event type")
        .reset_index(name="Rows")
    )
    event_counts["Share"] = event_counts["Rows"].div(len(events)).map(percent)
    add_section(lines, "Event Mix")
    lines.extend(markdown_table(event_counts.to_dict("records")))

    subtype_counts = (
        events["event_subtype"]
        .value_counts()
        .head(20)
        .rename_axis("Subtype")
        .reset_index(name="Rows")
    )
    subtype_counts["Share"] = subtype_counts["Rows"].div(len(events)).map(percent)
    add_section(lines, "Top Event Subtypes")
    lines.extend(markdown_table(subtype_counts.to_dict("records")))

    return lines, warnings


def build_report(daily: pd.DataFrame, checkpoints: pd.DataFrame, events: pd.DataFrame) -> str:
    lines: list[str] = [
        "# Phase 2B Feature Audit",
        "",
        "This report audits the generated feature datasets for coverage, basic consistency, label balance, event mix, and leakage watchlist columns.",
    ]
    warnings: list[str] = []

    add_section(lines, "Daily Table")
    section, section_warnings = audit_daily(daily)
    lines.extend(section)
    warnings.extend(section_warnings)

    add_section(lines, "Checkpoint Table")
    section, section_warnings = audit_checkpoints(checkpoints, daily)
    lines.extend(section)
    warnings.extend(section_warnings)

    add_section(lines, "Event Table")
    section, section_warnings = audit_events(events, daily)
    lines.extend(section)
    warnings.extend(section_warnings)

    add_section(lines, "Audit Warnings")
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("No structural warnings found.")

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    daily, checkpoints, events = load_outputs(args.feature_dir)
    report = build_report(daily, checkpoints, events)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report)
    print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
