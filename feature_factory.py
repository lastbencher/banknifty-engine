#!/usr/bin/env python3
"""
Bank Nifty Feature Factory — builds three canonical research datasets.

Outputs:
  features/daily_features.csv
  features/checkpoint_features.csv
  features/event_features.csv

Checkpoints — 3-min grid (09:18, 09:21, 09:24 …) plus 5-min grid (09:20, 09:25 … 09:45).
Signal rules expand at load: 3MIN rules → all 3-min slots; 5MIN rules → +15m +30m.
Session metadata is derived dynamically from each day's actual bar count and times.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from bnf_research.build import build_features, load_master


DEFAULT_SOURCE = "banknifty_master.csv"
DEFAULT_OUTPUT_DIR = "features"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Bank Nifty daily, checkpoint, and event feature datasets."
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


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
    print("BANK NIFTY QUANT RESEARCH PLATFORM — FEATURE FACTORY")
    print("=" * 72)
    print(f"Source : {source_path}")
    print(f"Output : {output_dir}")
    print()
    print(f"daily_features rows      : {len(daily):,}")
    print(f"checkpoint_features rows : {len(checkpoints):,}")
    print(f"event_features rows      : {len(events):,}")
    print()
    print("Checkpoints:", ", ".join(
        sorted(checkpoints["checkpoint_clock"].dropna().unique().tolist())
    ))
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
        if col in daily.columns:
            print(f"{col:<32} {daily[col].astype(float).mean() * 100:>6.2f}%")
    print()
    print("Event counts")
    print("-" * 72)
    if not events.empty:
        print(events["event_type"].value_counts().to_string())
        print()
        print("Wyckoff subtypes")
        wyckoff = events[events["event_type"].isin(["WYCKOFF", "TRAP"])]
        if not wyckoff.empty:
            print(wyckoff["event_subtype"].value_counts().head(10).to_string())
    else:
        print("No events")
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
