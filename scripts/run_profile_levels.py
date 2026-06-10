#!/usr/bin/env python3
"""Print daily market profile + zone levels (index prices, futures volume/OI)."""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from bnf_research.build import load_master
from bnf_research.futures_data import FUTURES_MASTER_PATH, load_futures_master, seed_from_10d
from bnf_research.market_profile import (
    build_hybrid_profiles,
    classify_day_type,
    merge_index_futures_bars,
    poor_high,
    poor_low,
    prepare_day_frame,
    single_print_levels,
    virgin_levels,
)
from bnf_research.sr_levels import build_levels_cache
from bnf_research.zone_engine import build_zone_scores, top_zones


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Market profile + zone report from futures data.")
    parser.add_argument("--futures", type=Path, default=FUTURES_MASTER_PATH)
    parser.add_argument("--index", type=Path, default=PROJECT_ROOT / "banknifty_master.csv")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "features" / "daily_profiles.csv")
    parser.add_argument("--days", type=int, default=5, help="Prior sessions to list in history section")
    parser.add_argument("--as-of", type=str, default=None, help="Session date YYYY-MM-DD (default: latest in data)")
    return parser.parse_args()


def _session_date(profiles: pd.DataFrame, as_of: str | None) -> date:
    if as_of:
        return pd.Timestamp(as_of).date()
    return profiles.iloc[-1]["date"]


def _print_profile_block(title: str, session: date, day: pd.DataFrame, row: pd.Series) -> None:
    dtype = classify_day_type(day)
    day_range = float(row["HIGH"]) - float(row["LOW"])
    print()
    print(title)
    print("-" * 50)
    print(f"DATE : {session}")
    print(f"RANGE: {row['LOW']:.0f} – {row['HIGH']:.0f} ({day_range:.0f} pts)")
    print(f"POC  : {row['POC']:.0f}")
    print(f"VAH  : {row['VAH']:.0f}")
    print(f"VAL  : {row['VAL']:.0f}")
    print(f"TYPE : {dtype}")
    print(f"POOR HIGH : {poor_high(day)}")
    print(f"POOR LOW  : {poor_low(day)}")


def main() -> None:
    args = parse_args()
    futures = load_futures_master(args.futures)
    if futures.empty:
        futures = seed_from_10d()
    if futures.empty:
        print("No futures data — run update_pipeline or scripts/update_futures_pipeline.py")
        sys.exit(1)

    index = load_master(args.index) if args.index.exists() else pd.DataFrame()
    if index.empty:
        print("Warning: no index master — levels will use futures prices (offset from chart)", file=sys.stderr)
        from bnf_research.market_profile import build_daily_profiles

        hybrid = futures
        profiles = build_daily_profiles(futures)
    else:
        hybrid = merge_index_futures_bars(index, futures)
        profiles = build_hybrid_profiles(index, futures)

    prep = prepare_day_frame(hybrid)
    virgin = virgin_levels(profiles, hybrid)
    cache = build_levels_cache(futures, index_df=index if not index.empty else None)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(args.output, index=False)
    print(f"Saved {args.output} ({len(profiles)} sessions, index-priced + futures volume)")

    session = _session_date(profiles, args.as_of)
    if session not in set(profiles["date"]):
        print(f"No profile for session {session}. Latest: {profiles.iloc[-1]['date']}")
        sys.exit(1)

    today_row = profiles[profiles["date"] == session].iloc[0]
    today_day = prep[prep["date"] == session]

    prior_rows = profiles[profiles["date"] < session]
    prior_session = prior_rows.iloc[-1]["date"] if not prior_rows.empty else None
    prior_row = prior_rows.iloc[-1] if not prior_rows.empty else None
    prior_day = prep[prep["date"] == prior_session] if prior_session else pd.DataFrame()

    print()
    print("REPORT:", datetime.now().strftime("%d.%m.%Y | %H:%M"))
    print("=" * 70)
    print("LEVELS USE INDEX PRICES + FUTURES VOLUME/OI")
    print("=" * 70)

    _print_profile_block(f"TODAY — {session}", session, today_day, today_row)

    if prior_row is not None and prior_session is not None:
        _print_profile_block(
            f"PRIOR SESSION S/R REFERENCE — {prior_session} (used for spring confluence)",
            prior_session,
            prior_day,
            prior_row,
        )

    levels = cache.get(session)
    if levels:
        print()
        print("=" * 70)
        print(f"ACTIVE S/R FOR {session} (from history through {levels.prior_date})")
        print("=" * 70)
        print(f"Reference POC/VAH/VAL: {levels.poc:.0f} / {levels.vah:.0f} / {levels.val:.0f}")
        print(f"Demand zones: {', '.join(f'{z:.0f}' for z in levels.demand_zones[:5])}")
        print(f"Supply zones: {', '.join(f'{z:.0f}' for z in levels.supply_zones[:5])}")

        lookback = prep[(prep["date"] < session)].tail(375 * args.days)
        if not lookback.empty:
            zones = build_zone_scores(lookback)
            print()
            print("TOP SCORED ZONES (5d lookback)")
            print("-" * 40)
            for z in top_zones(zones, 10):
                print(
                    f"{z['price']:8.0f} | score={z['score']:5.1f} | "
                    f"vol={z['volume']} | oiΔ={int(z['oi_change'])}"
                )

    singles = single_print_levels(today_day)
    if singles:
        print()
        print("=" * 70)
        print(f"SINGLE PRINTS — {session}")
        print("=" * 70)
        for lo, hi in singles:
            if lo == hi:
                print(f"  {lo:.0f}")
            else:
                print(f"  {lo:.0f} -> {hi:.0f}")

    if args.days > 0:
        print()
        print("=" * 70)
        print(f"RECENT SESSION HISTORY (last {args.days})")
        print("=" * 70)
        for _, row in profiles[profiles["date"] <= session].tail(args.days).iterrows():
            d = row["date"]
            day = prep[prep["date"] == d]
            _print_profile_block(f"  {d}", d, day, row)

    print()
    print("=" * 70)
    print("VIRGIN POCS (untouched)")
    print("=" * 70)
    for d, poc in virgin["POC"][-8:]:
        print(d, "->", int(poc))


if __name__ == "__main__":
    main()
