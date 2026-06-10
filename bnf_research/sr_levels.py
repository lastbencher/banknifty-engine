"""Support/resistance layer — market profile + volume zones for spring entries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from bnf_research.market_profile import (
    build_daily_profiles,
    single_print_levels,
    virgin_levels,
)
from bnf_research.zone_engine import build_zone_scores, demand_supply_zones, zones_near_price


@dataclass
class SessionLevels:
    """Prior-session context for trading session `session_date`."""

    session_date: date
    prior_date: date | None
    poc: float | None = None
    vah: float | None = None
    val: float | None = None
    virgin_pocs: list[float] = field(default_factory=list)
    virgin_vahs: list[float] = field(default_factory=list)
    virgin_vals: list[float] = field(default_factory=list)
    single_prints: list[tuple[float, float]] = field(default_factory=list)
    demand_zones: list[float] = field(default_factory=list)
    supply_zones: list[float] = field(default_factory=list)
    zone_scores: list[dict[str, Any]] = field(default_factory=list)

    def all_support_levels(self) -> list[float]:
        levels = list(self.virgin_vals) + list(self.demand_zones)
        if self.val is not None:
            levels.append(self.val)
        for lo, _hi in self.single_prints:
            levels.append(lo)
        return sorted(set(levels))

    def all_resistance_levels(self) -> list[float]:
        levels = list(self.virgin_vahs) + list(self.supply_zones)
        if self.vah is not None:
            levels.append(self.vah)
        for _lo, hi in self.single_prints:
            levels.append(hi)
        return sorted(set(levels))


def build_levels_cache(
    futures_df: pd.DataFrame,
    *,
    index_df: pd.DataFrame | None = None,
    zone_lookback_days: int = 5,
) -> dict[date, SessionLevels]:
    """
    Precompute per-session S/R from futures volume/OI.
    When index_df is supplied, profile levels use index OHLC (chart-aligned).
    Uses only data strictly before each session date (no look-ahead).
    """
    if futures_df.empty:
        return {}

    if index_df is not None and not index_df.empty:
        from bnf_research.market_profile import merge_index_futures_bars

        bars = merge_index_futures_bars(index_df, futures_df)
    else:
        bars = futures_df.copy()

    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars["date"] = bars["datetime"].dt.date

    profiles = build_daily_profiles(bars)
    if profiles.empty:
        return {}

    virgin = virgin_levels(profiles, bars)
    cache: dict[date, SessionLevels] = {}
    session_dates = sorted(bars["date"].unique())

    for session_date in session_dates:
        prior_profiles = profiles[profiles["date"] < session_date]
        if prior_profiles.empty:
            continue

        prior = prior_profiles.iloc[-1]
        prior_date = prior["date"]

        hist_bars = bars[bars["date"] < session_date]
        if hist_bars.empty:
            continue

        lookback_start = pd.Timestamp(session_date) - pd.Timedelta(days=zone_lookback_days)
        zone_bars = hist_bars[hist_bars["datetime"] >= lookback_start]
        zones = build_zone_scores(zone_bars)

        ref = float(prior["POC"])
        demand, supply = demand_supply_zones(zones, ref)

        prior_day = bars[bars["date"] == prior_date]
        singles = single_print_levels(prior_day) if not prior_day.empty else []

        untouched_pocs = [lvl for d, lvl in virgin["POC"] if d < session_date]
        untouched_vahs = [lvl for d, lvl in virgin["VAH"] if d < session_date]
        untouched_vals = [lvl for d, lvl in virgin["VAL"] if d < session_date]

        cache[session_date] = SessionLevels(
            session_date=session_date,
            prior_date=prior_date,
            poc=float(prior["POC"]),
            vah=float(prior["VAH"]),
            val=float(prior["VAL"]),
            virgin_pocs=untouched_pocs[-5:],
            virgin_vahs=untouched_vahs[-5:],
            virgin_vals=untouched_vals[-5:],
            single_prints=singles,
            demand_zones=demand,
            supply_zones=supply,
            zone_scores=zones[:15],
        )

    return cache


def has_sr_confluence(
    levels: SessionLevels,
    price: float,
    side: str,
    *,
    tolerance: float = 40.0,
    min_zone_score: float = 20.0,
) -> bool:
    """
    True if spring/upthrust level aligns with MP or scored zone.
    LONG → support confluence; SHORT → resistance confluence.
    """
    if side == "LONG":
        candidates = levels.all_support_levels()
        near_zones = zones_near_price(levels.zone_scores, price, tolerance=tolerance, min_score=min_zone_score)
        mp_near = any(abs(price - lvl) <= tolerance for lvl in candidates)
        return mp_near or len(near_zones) > 0

    candidates = levels.all_resistance_levels()
    near_zones = zones_near_price(levels.zone_scores, price, tolerance=tolerance, min_score=min_zone_score)
    mp_near = any(abs(price - lvl) <= tolerance for lvl in candidates)
    return mp_near or len(near_zones) > 0


def nearest_target_level(
    levels: SessionLevels,
    entry: float,
    side: str,
    *,
    min_distance: float = 30.0,
) -> float | None:
    """Next structural level in trade direction (for effort/reward exit)."""
    if side == "LONG":
        candidates = [p for p in levels.all_resistance_levels() if p > entry + min_distance]
        return min(candidates) if candidates else None

    candidates = [p for p in levels.all_support_levels() if p < entry - min_distance]
    return max(candidates) if candidates else None
