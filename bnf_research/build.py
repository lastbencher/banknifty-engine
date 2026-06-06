from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from bnf_research.checkpoint_builder import build_checkpoint_rows
from bnf_research.daily_builder import build_daily_row
from bnf_research.event_builder import assign_event_ids, build_event_rows
from bnf_research.rollups import add_checkpoint_rollups, add_daily_rollups
from bnf_research.session import build_session_meta, compute_median_session_bars


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


def build_features(master: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    median_bars = compute_median_session_bars(master)

    daily_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    prev_daily: dict[str, Any] | None = None

    for date_value, raw_day in master.groupby("date", sort=True):
        meta = build_session_meta(date_value, raw_day, median_bars)
        daily_row, aux = build_daily_row(meta, prev_daily)
        daily_rows.append(daily_row)
        checkpoint_rows.extend(build_checkpoint_rows(meta, daily_row))
        event_rows.extend(build_event_rows(meta, daily_row, aux))

        prev_daily = {
            "date": date_value,
            "day_high": daily_row["day_high"],
            "day_low": daily_row["day_low"],
            "day_close": daily_row["day_close"],
            "day_range": daily_row["day_range"],
        }

    daily = add_daily_rollups(pd.DataFrame(daily_rows))
    checkpoints = add_checkpoint_rollups(pd.DataFrame(checkpoint_rows), daily)
    events = assign_event_ids(pd.DataFrame(event_rows))

    return daily, checkpoints, events
