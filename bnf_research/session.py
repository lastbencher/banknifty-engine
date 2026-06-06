from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from bnf_research.config import COMPLETE_SESSION_FRACTION, IB_DURATION_MINUTES


@dataclass(frozen=True)
class SessionMeta:
    date: Any
    day: pd.DataFrame
    session_start: pd.Timestamp
    session_end: pd.Timestamp
    bars_count: int
    median_session_bars: float
    is_complete_session: bool
    ib_end_time: pd.Timestamp
    ib_bars: pd.DataFrame
    after_ib: pd.DataFrame
    has_ib: bool


def compute_median_session_bars(master: pd.DataFrame) -> float:
    counts = master.groupby("date").size()
    return float(counts.median())


def slice_to_minute(day: pd.DataFrame, session_start: pd.Timestamp, minutes: int) -> pd.DataFrame:
    cutoff = session_start + pd.Timedelta(minutes=minutes)
    return day[day["datetime"] <= cutoff].copy()


def build_session_meta(
    date_value: Any,
    day: pd.DataFrame,
    median_session_bars: float,
) -> SessionMeta:
    day = day.sort_values("datetime").reset_index(drop=True)
    session_start = pd.Timestamp(day.iloc[0]["datetime"])
    session_end = pd.Timestamp(day.iloc[-1]["datetime"])
    bars_count = len(day)

    ib_end_time = session_start + pd.Timedelta(minutes=IB_DURATION_MINUTES)
    ib_bars = day[day["datetime"] < ib_end_time].copy()
    after_ib = day[day["datetime"] >= ib_end_time].copy()
    has_ib = len(ib_bars) >= IB_DURATION_MINUTES * 0.75

    is_complete = bars_count >= median_session_bars * COMPLETE_SESSION_FRACTION

    return SessionMeta(
        date=date_value,
        day=day,
        session_start=session_start,
        session_end=session_end,
        bars_count=bars_count,
        median_session_bars=median_session_bars,
        is_complete_session=is_complete,
        ib_end_time=ib_end_time,
        ib_bars=ib_bars,
        after_ib=after_ib,
        has_ib=has_ib,
    )
