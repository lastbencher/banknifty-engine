"""Intraday move legs, pullbacks, and trap episodes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class MoveLeg:
    date: Any
    direction: str  # UP / DOWN
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    start_price: float
    end_price: float
    points: float
    duration_min: float
    bars: int
    vol_during: int
    vol_before: int
    oi_delta: int
    hour_start: int


@dataclass
class TrapEpisode:
    date: Any
    trap_type: str  # BULL_TRAP / BEAR_TRAP
    break_time: pd.Timestamp
    break_price: float
    confirm_time: pd.Timestamp
    confirm_price: float
    opposite_move_pts: float
    duration_min: float
    vol_at_break: int
    vol_before_15m: int
    oi_delta_break: int
    oi_delta_after: int
    trap_source: str = "ROLLING_30M"  # ROLLING_30M | VAH | VAL | POC
    profile_level: float | None = None
    prior_session_date: Any | None = None


def _window_volume(day: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> int:
    if "volume" not in day.columns:
        return 0
    w = day[(day["datetime"] >= start) & (day["datetime"] <= end)]
    return int(w["volume"].sum())


def _window_oi_delta(day: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> int:
    if "oi" not in day.columns:
        return 0
    w = day[(day["datetime"] >= start) & (day["datetime"] <= end)]
    if len(w) < 2:
        return 0
    return int(w["oi"].iloc[-1] - w["oi"].iloc[0])


def detect_impulse_legs(
    day: pd.DataFrame,
    *,
    min_points: float = 50.0,
    max_pullback: float = 25.0,
) -> list[MoveLeg]:
    """
    Impulse legs: consecutive minute bars in one direction until pullback > max_pullback.
    """
    day = day.sort_values("datetime").reset_index(drop=True)
    if len(day) < 5:
        return []

    legs: list[MoveLeg] = []
    session_date = day["datetime"].iloc[0].date()

    i = 1
    while i < len(day):
        # find start of move from local pivot
        direction: str | None = None
        start_idx = i - 1
        start_price = float(day.iloc[start_idx]["close"])
        extreme = start_price
        j = i

        while j < len(day):
            row = day.iloc[j]
            hi, lo, cl = float(row["high"]), float(row["low"]), float(row["close"])

            if direction is None:
                if cl - start_price >= 15:
                    direction = "UP"
                    extreme = hi
                elif start_price - cl >= 15:
                    direction = "DOWN"
                    extreme = lo
                else:
                    j += 1
                    start_idx = j - 1
                    start_price = float(day.iloc[start_idx]["close"])
                    continue
            elif direction == "UP":
                extreme = max(extreme, hi)
                if extreme - lo > max_pullback:
                    break
            else:
                extreme = min(extreme, lo)
                if hi - extreme > max_pullback:
                    break
            j += 1

        if direction is None or j - start_idx < 3:
            i += 1
            continue

        end_idx = j - 1
        end_row = day.iloc[end_idx]
        end_price = float(end_row["close"] if direction == "UP" else end_row["close"])
        if direction == "UP":
            pts = float(day.iloc[start_idx:end_idx + 1]["high"].max()) - start_price
            end_price = float(day.iloc[start_idx:end_idx + 1]["high"].max())
        else:
            pts = start_price - float(day.iloc[start_idx:end_idx + 1]["low"].min())
            end_price = float(day.iloc[start_idx:end_idx + 1]["low"].min())

        if pts >= min_points:
            t0 = pd.Timestamp(day.iloc[start_idx]["datetime"])
            t1 = pd.Timestamp(day.iloc[end_idx]["datetime"])
            before_start = t0 - pd.Timedelta(minutes=15)
            legs.append(
                MoveLeg(
                    date=session_date,
                    direction=direction,
                    start_time=t0,
                    end_time=t1,
                    start_price=start_price,
                    end_price=end_price,
                    points=pts,
                    duration_min=(t1 - t0).total_seconds() / 60,
                    bars=end_idx - start_idx + 1,
                    vol_during=_window_volume(day, t0, t1),
                    vol_before=_window_volume(day, before_start, t0 - pd.Timedelta(minutes=1)),
                    oi_delta=_window_oi_delta(day, t0, t1),
                    hour_start=t0.hour,
                )
            )
            i = end_idx + 1
        else:
            i += 1

    return legs


def detect_traps(
    day: pd.DataFrame,
    *,
    lookback_bars: int = 30,
    min_break: float = 20.0,
    min_opposite: float = 40.0,
    confirm_bars: int = 10,
) -> list[TrapEpisode]:
    """
    Trap = break of rolling 30-min high/low then close back inside + opposite move.
    """
    day = day.sort_values("datetime").reset_index(drop=True)
    if len(day) < lookback_bars + confirm_bars + 5:
        return []

    session_date = day["datetime"].iloc[0].date()
    traps: list[TrapEpisode] = []
    used_until = 0

    for i in range(lookback_bars, len(day) - confirm_bars):
        if i < used_until:
            continue

        window = day.iloc[i - lookback_bars : i]
        res_high = float(window["high"].max())
        res_low = float(window["low"].min())

        row = day.iloc[i]
        t_break = pd.Timestamp(row["datetime"])
        hi, lo, cl = float(row["high"]), float(row["low"]), float(row["close"])

        trap_type: str | None = None
        break_price = cl

        if hi > res_high + min_break and cl < res_high:
            trap_type = "BULL_TRAP"
            break_price = hi
        elif lo < res_low - min_break and cl > res_low:
            trap_type = "BEAR_TRAP"
            break_price = lo

        if trap_type is None:
            continue

        # measure opposite move over next confirm_bars
        after = day.iloc[i : i + confirm_bars + 1]
        if trap_type == "BULL_TRAP":
            opp = break_price - float(after["low"].min())
            confirm_idx = after["low"].idxmin()
        else:
            opp = float(after["high"].max()) - break_price
            confirm_idx = after["high"].idxmax()

        if opp < min_opposite:
            continue

        confirm_row = day.loc[confirm_idx]
        before_start = t_break - pd.Timedelta(minutes=15)

        traps.append(
            TrapEpisode(
                date=session_date,
                trap_type=trap_type,
                break_time=t_break,
                break_price=break_price,
                confirm_time=pd.Timestamp(confirm_row["datetime"]),
                confirm_price=float(confirm_row["close"]),
                opposite_move_pts=opp,
                duration_min=(pd.Timestamp(confirm_row["datetime"]) - t_break).total_seconds() / 60,
                vol_at_break=int(row["volume"]) if "volume" in row else 0,
                vol_before_15m=_window_volume(day, before_start, t_break - pd.Timedelta(minutes=1)),
                oi_delta_break=int(row["oi"] - day.iloc[i - 1]["oi"]) if "oi" in row and i > 0 else 0,
                oi_delta_after=_window_oi_delta(day, t_break, pd.Timestamp(confirm_row["datetime"])),
                trap_source="ROLLING_30M",
            )
        )
        used_until = i + confirm_bars

    return traps


def detect_profile_traps(
    day: pd.DataFrame,
    *,
    prior_session_date: Any,
    vah: float,
    val: float,
    poc: float | None = None,
    min_pierce: float = 15.0,
    min_opposite: float = 40.0,
    confirm_bars: int = 15,
    tolerance: float = 5.0,
) -> list[TrapEpisode]:
    """
    Traps at prior session profile levels (VAH/VAL/POC).

    BULL_TRAP: pierce above VAH (or POC) then fail back inside with ≥min_opposite down.
    BEAR_TRAP: pierce below VAL (or POC) then fail back inside with ≥min_opposite up.
    """
    day = day.sort_values("datetime").reset_index(drop=True)
    if len(day) < confirm_bars + 5:
        return []

    session_date = day["datetime"].iloc[0].date()
    traps: list[TrapEpisode] = []
    used_until = 0

    levels: list[tuple[str, float]] = [("VAH", vah), ("VAL", val)]
    if poc is not None and not np.isnan(poc):
        levels.append(("POC", poc))

    for i in range(len(day) - confirm_bars):
        if i < used_until:
            continue

        row = day.iloc[i]
        t_break = pd.Timestamp(row["datetime"])
        hi, lo, cl = float(row["high"]), float(row["low"]), float(row["close"])

        for level_name, level_price in levels:
            trap_type: str | None = None
            break_price = cl

            if level_name in ("VAH", "POC") and hi > level_price + min_pierce and cl < level_price + tolerance:
                trap_type = "BULL_TRAP"
                break_price = hi
            elif level_name in ("VAL", "POC") and lo < level_price - min_pierce and cl > level_price - tolerance:
                trap_type = "BEAR_TRAP"
                break_price = lo

            if trap_type is None:
                continue

            after = day.iloc[i : i + confirm_bars + 1]
            if trap_type == "BULL_TRAP":
                opp = break_price - float(after["low"].min())
                confirm_idx = after["low"].idxmin()
            else:
                opp = float(after["high"].max()) - break_price
                confirm_idx = after["high"].idxmax()

            if opp < min_opposite:
                continue

            confirm_row = day.loc[confirm_idx]
            before_start = t_break - pd.Timedelta(minutes=15)

            traps.append(
                TrapEpisode(
                    date=session_date,
                    trap_type=trap_type,
                    break_time=t_break,
                    break_price=break_price,
                    confirm_time=pd.Timestamp(confirm_row["datetime"]),
                    confirm_price=float(confirm_row["close"]),
                    opposite_move_pts=opp,
                    duration_min=(pd.Timestamp(confirm_row["datetime"]) - t_break).total_seconds() / 60,
                    vol_at_break=int(row["volume"]) if "volume" in row else 0,
                    vol_before_15m=_window_volume(day, before_start, t_break - pd.Timedelta(minutes=1)),
                    oi_delta_break=int(row["oi"] - day.iloc[i - 1]["oi"]) if "oi" in row and i > 0 else 0,
                    oi_delta_after=_window_oi_delta(day, t_break, pd.Timestamp(confirm_row["datetime"])),
                    trap_source=level_name,
                    profile_level=level_price,
                    prior_session_date=prior_session_date,
                )
            )
            used_until = i + confirm_bars
            break

    return traps


def continuation_after_pullback(
    day: pd.DataFrame,
    leg: MoveLeg,
    *,
    pullback_threshold: float = 30.0,
) -> dict[str, Any]:
    """After an impulse leg, measure pullback depth and whether trend continued."""
    after = day[day["datetime"] > leg.end_time].copy()
    if after.empty:
        return {"continued": False, "pullback_pts": np.nan, "extension_pts": np.nan}

    if leg.direction == "UP":
        pb = leg.end_price - float(after.head(30)["low"].min())
        if pb < pullback_threshold:
            return {"continued": False, "pullback_pts": pb, "extension_pts": 0.0}
        ext = float(after["high"].max()) - leg.end_price
        return {"continued": ext > 30, "pullback_pts": pb, "extension_pts": ext}

    pb = float(after.head(30)["high"].max()) - leg.end_price
    if pb < pullback_threshold:
        return {"continued": False, "pullback_pts": pb, "extension_pts": 0.0}
    ext = leg.end_price - float(after["low"].min())
    return {"continued": ext > 30, "pullback_pts": pb, "extension_pts": ext}
