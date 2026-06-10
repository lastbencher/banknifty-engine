"""Volume/OI zone scoring — institutional S/R from futures flow."""
from __future__ import annotations

from typing import Any

import pandas as pd

PRICE_TICK = 20


def build_zone_scores(
    df: pd.DataFrame,
    *,
    tick: int = PRICE_TICK,
    vol_weight: float = 40.0,
    oi_weight: float = 30.0,
    lb_weight: float = 15.0,
    sc_weight: float = 15.0,
) -> list[dict[str, Any]]:
    """
    Score price bins by volume concentration, OI build, long build, short cover.
    Returns zones sorted by score descending.
    """
    if df.empty:
        return []

    work = df.copy()
    work["price_bin"] = (work["close"] / tick).round() * tick
    work["price_change"] = work["close"].diff()
    work["oi_change"] = work["oi"].diff() if "oi" in work.columns else 0

    volume_profile = work.groupby("price_bin")["volume"].sum()
    oi_profile = work.groupby("price_bin")["oi_change"].sum()

    long_build = (
        work[(work["price_change"] > 0) & (work["oi_change"] > 0)]
        .groupby("price_bin")
        .size()
    )
    short_cover = (
        work[(work["price_change"] > 0) & (work["oi_change"] < 0)]
        .groupby("price_bin")
        .size()
    )

    max_vol = max(float(volume_profile.max()), 1.0)
    pos_oi = oi_profile[oi_profile > 0]
    max_oi = max(float(pos_oi.max()) if len(pos_oi) else 1.0, 1.0)
    max_lb = max(float(long_build.max()) if len(long_build) else 1.0, 1.0)
    max_sc = max(float(short_cover.max()) if len(short_cover) else 1.0, 1.0)

    zones: list[dict[str, Any]] = []
    for price in sorted(work["price_bin"].unique()):
        vol_score = float(volume_profile.get(price, 0)) / max_vol * vol_weight
        oi_score = max(0.0, float(oi_profile.get(price, 0))) / max_oi * oi_weight
        lb_score = float(long_build.get(price, 0)) / max_lb * lb_weight
        sc_score = float(short_cover.get(price, 0)) / max_sc * sc_weight
        total = round(vol_score + oi_score + lb_score + sc_score, 2)
        zones.append(
            {
                "price": float(price),
                "score": total,
                "volume": int(volume_profile.get(price, 0)),
                "oi_change": float(oi_profile.get(price, 0)),
                "long_build": int(long_build.get(price, 0)),
                "short_cover": int(short_cover.get(price, 0)),
            }
        )

    return sorted(zones, key=lambda z: z["score"], reverse=True)


def top_zones(zones: list[dict[str, Any]], n: int = 15) -> list[dict[str, Any]]:
    return zones[:n]


def zones_near_price(
    zones: list[dict[str, Any]],
    price: float,
    *,
    tolerance: float = 40.0,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Zones within tolerance of price, optionally filtered by min score."""
    return [
        z
        for z in zones
        if abs(z["price"] - price) <= tolerance and z["score"] >= min_score
    ]


def demand_supply_zones(
    zones: list[dict[str, Any]],
    ref_price: float,
    *,
    top_n: int = 5,
) -> tuple[list[float], list[float]]:
    """Split top zones into demand (below ref) and supply (above ref)."""
    demand = [z["price"] for z in zones if z["price"] < ref_price][:top_n]
    supply = [z["price"] for z in zones if z["price"] > ref_price][:top_n]
    return demand, supply
