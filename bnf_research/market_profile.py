"""Market Profile — POC/VAH/VAL, virgin levels, single prints, day types."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

PRICE_TICK = 20
VALUE_AREA_PCT = 0.70
# Minimum full-session range (pts) to label "Wide Range Day" when not a trend day
WIDE_RANGE_POINTS = 600


def price_bin(price: float, tick: int = PRICE_TICK) -> float:
    return round(price / tick) * tick


def prepare_day_frame(df: pd.DataFrame, *, tick: int = PRICE_TICK) -> pd.DataFrame:
    out = df.copy()
    out["datetime"] = pd.to_datetime(out["datetime"])
    out["date"] = out["datetime"].dt.date
    out["price_bin"] = (out["close"] / tick).round() * tick
    return out


def merge_index_futures_bars(index_df: pd.DataFrame, futures_df: pd.DataFrame) -> pd.DataFrame:
    """
    Index OHLC for price levels + futures volume/OI for profile shape.
    Levels align with the Nifty Bank index chart traders watch.
    """
    idx = index_df.copy()
    idx["datetime"] = pd.to_datetime(idx["datetime"])
    fut = futures_df.copy()
    fut["datetime"] = pd.to_datetime(fut["datetime"])

    ohlc = ["datetime", "open", "high", "low", "close"]
    merged = idx[ohlc].merge(
        fut[["datetime", "volume", "oi"]],
        on="datetime",
        how="inner",
    )
    merged["volume"] = pd.to_numeric(merged["volume"], errors="coerce").fillna(0).astype("int64")
    merged["oi"] = pd.to_numeric(merged["oi"], errors="coerce").fillna(0).astype("int64")
    return merged.sort_values("datetime").reset_index(drop=True)


def build_hybrid_profiles(index_df: pd.DataFrame, futures_df: pd.DataFrame, *, tick: int = PRICE_TICK) -> pd.DataFrame:
    """Daily profiles: index prices binned, futures volume/OI weighted."""
    hybrid = merge_index_futures_bars(index_df, futures_df)
    return build_daily_profiles(hybrid, tick=tick)


def build_daily_profile(day: pd.DataFrame, *, tick: int = PRICE_TICK) -> dict[str, Any]:
    """Volume profile for one session → POC, VAH, VAL, range."""
    if day.empty or "volume" not in day.columns:
        return {}

    vp = day.groupby("price_bin")["volume"].sum().sort_values(ascending=False)
    if vp.empty:
        return {}

    poc = float(vp.index[0])
    total_vol = vp.sum()
    target = total_vol * VALUE_AREA_PCT

    included = {poc}
    running = float(vp.loc[poc])
    remaining = vp.drop(poc)

    while running < target and len(remaining):
        nxt = remaining.idxmax()
        included.add(nxt)
        running += remaining.loc[nxt]
        remaining = remaining.drop(nxt)

    return {
        "POC": poc,
        "VAH": float(max(included)),
        "VAL": float(min(included)),
        "HIGH": float(day["high"].max()),
        "LOW": float(day["low"].min()),
        "total_volume": int(total_vol),
    }


def build_daily_profiles(df: pd.DataFrame, *, tick: int = PRICE_TICK) -> pd.DataFrame:
    """One row per session date with POC/VAH/VAL."""
    prep = prepare_day_frame(df, tick=tick)
    rows: list[dict[str, Any]] = []

    for d in sorted(prep["date"].unique()):
        day = prep[prep["date"] == d]
        prof = build_daily_profile(day, tick=tick)
        if not prof:
            continue
        rows.append({"date": d, **prof})

    return pd.DataFrame(rows)


def poor_high(day: pd.DataFrame, *, tolerance: float = 5.0) -> bool:
    h = day["high"].max()
    return (abs(day["high"] - h) < tolerance).sum() >= 2


def poor_low(day: pd.DataFrame, *, tolerance: float = 5.0) -> bool:
    lo = day["low"].min()
    return (abs(day["low"] - lo) < tolerance).sum() >= 2


def classify_day_type(day: pd.DataFrame) -> str:
    """
    Market Profile day type from full-session open/close location and range.

    Does not use Initial Balance (IB) — wide opening hours were misclassifying
    large trend days as "Normal Day" when IB range was also huge.
    """
    if len(day) < 30:
        return "Unknown"

    day = day.sort_values("datetime")
    day_high = day["high"].max()
    day_low = day["low"].min()
    day_range = day_high - day_low
    if day_range <= 0:
        return "Unknown"

    session_open = float(day.iloc[0]["open"])
    session_close = float(day.iloc[-1]["close"])
    open_pos = (session_open - day_low) / day_range
    close_pos = (session_close - day_low) / day_range

    if open_pos <= 0.25 and close_pos >= 0.75:
        return "Trend Day Up"
    if open_pos >= 0.75 and close_pos <= 0.25:
        return "Trend Day Down"
    if day_range >= WIDE_RANGE_POINTS:
        return "Wide Range Day"
    return "Normal Day"


def virgin_levels(
    profile_df: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    level_cols: tuple[str, ...] = ("POC", "VAH", "VAL"),
) -> dict[str, list[tuple[Any, float]]]:
    """Levels from prior sessions not yet touched by subsequent price."""
    prep = prepare_day_frame(bars)
    result: dict[str, list[tuple[Any, float]]] = {c: [] for c in level_cols}

    for i in range(len(profile_df) - 1):
        session_date = profile_df.iloc[i]["date"]
        future = prep[prep["date"] > session_date]
        if future.empty:
            continue

        for col in level_cols:
            level = float(profile_df.iloc[i][col])
            touched = ((future["low"] <= level) & (future["high"] >= level)).any()
            if not touched:
                result[col].append((session_date, level))

    return result


def single_print_levels(
    day: pd.DataFrame,
    *,
    tick: int = PRICE_TICK,
    tpo_minutes: int = 30,
    min_poc_distance: float = 40.0,
) -> list[tuple[float, float]]:
    """
    Return list of (low, high) price zones where TPO count == 1 (single prints).
    """
    if day.empty:
        return []

    day = day.copy()
    day["datetime"] = pd.to_datetime(day["datetime"])
    if "price_bin" not in day.columns:
        day["price_bin"] = (day["close"] / tick).round() * tick
    day["tpo"] = pd.to_datetime(day["datetime"]).dt.floor(f"{tpo_minutes}min")
    tpo_map: dict[int, set] = {}

    for _, bracket in day.groupby("tpo"):
        low_bin = math.floor(bracket["low"].min() / tick) * tick
        high_bin = math.ceil(bracket["high"].max() / tick) * tick
        for p in range(int(low_bin), int(high_bin) + tick, tick):
            tpo_map.setdefault(p, set()).add(bracket["tpo"].iloc[0])

    poc = float(day.groupby("price_bin")["volume"].sum().idxmax()) if "volume" in day.columns else float("nan")
    singles = [
        p for p, tpos in tpo_map.items() if len(tpos) == 1 and abs(p - poc) > min_poc_distance
    ]
    if not singles:
        return []

    singles.sort()
    zones: list[tuple[float, float]] = []
    start = prev = singles[0]
    for p in singles[1:]:
        if p == prev + tick:
            prev = p
        else:
            zones.append((float(start), float(prev)))
            start = prev = p
    zones.append((float(start), float(prev)))
    return zones
