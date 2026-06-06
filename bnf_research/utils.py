from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator is None or pd.isna(denominator) or denominator == 0:
        return np.nan
    return numerator / denominator


def minutes_between(start: Any, end: Any) -> float:
    if pd.isna(start) or pd.isna(end):
        return np.nan
    return (pd.Timestamp(end) - pd.Timestamp(start)).total_seconds() / 60.0


def to_hour(ts: Any) -> float:
    if pd.isna(ts):
        return np.nan
    return float(pd.Timestamp(ts).hour)


def direction_from_points(value: float) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    if value > 0:
        return "UP"
    if value < 0:
        return "DOWN"
    return "FLAT"


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
