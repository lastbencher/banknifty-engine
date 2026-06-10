#!/usr/bin/env python3
"""
Phase 4B — Weis spring/upthrust simulator with MP + zone S/R confluence.

Entry:  spring/upthrust confirm at prior session VAH/VAL (profile-based, not IB).
Stop:   below spring low / above upthrust high (structural danger point).
Exit:   lot1 @ +50 pts or half-distance to next S/R; lot2 @ next S/R or +100 pts.
Filter: optional MP/zone confluence; time windows 10:30–11:30 + 13:30–15:00.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from bnf_research.build import load_master
from bnf_research.futures_data import FUTURES_MASTER_PATH, load_futures_master, seed_from_10d
from bnf_research.session import build_session_meta, compute_median_session_bars
from bnf_research.sr_levels import build_levels_cache, has_sr_confluence, nearest_target_level
from bnf_research.wyckoff import detect_springs_at_range, detect_upthrusts_at_range

DEFAULT_MASTER = PROJECT_ROOT / "banknifty_master.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "phase4b_weis_spring_sim"
STOP_BUFFER = 5.0
DEFAULT_TARGETS = (50, 100)

# IST entry windows (inclusive start, exclusive end on minute)
MORNING_WINDOW = ((10, 30), (11, 30))
AFTERNOON_WINDOW = ((13, 30), (15, 0))


@dataclass
class SpringTrade:
    date: Any
    event: str
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    sr_confluence: bool
    exit_lot1_time: pd.Timestamp | None
    exit_lot1_price: float | None
    exit_lot2_time: pd.Timestamp | None
    exit_lot2_price: float | None
    exit_lot1_reason: str
    exit_lot2_reason: str
    points_lot1: float
    points_lot2: float
    points_total: float
    rupee_pnl: float
    mae_points: float
    sr_target: float | None
    stopped: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weis spring/upthrust trade simulator.")
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--futures", type=Path, default=FUTURES_MASTER_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lots", type=int, default=2)
    parser.add_argument("--lot-size", type=int, default=15)
    parser.add_argument("--require-sr", action="store_true", help="Only take trades with MP/zone confluence")
    parser.add_argument("--morning-only", action="store_true", help="Restrict to 10:30–11:30")
    parser.add_argument("--no-time-filter", action="store_true", help="Allow entries all session")
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    return parser.parse_args()


def in_time_window(ts: pd.Timestamp, *, morning_only: bool, no_filter: bool) -> bool:
    if no_filter:
        return True
    h, m = ts.hour, ts.minute
    minute = h * 60 + m

    def in_range(start: tuple[int, int], end: tuple[int, int]) -> bool:
        s = start[0] * 60 + start[1]
        e = end[0] * 60 + end[1]
        return s <= minute < e

    if morning_only:
        return in_range(*MORNING_WINDOW)
    return in_range(*MORNING_WINDOW) or in_range(*AFTERNOON_WINDOW)


def simulate_structural_trade(
    day: pd.DataFrame,
    *,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: str,
    stop_price: float,
    sr_target: float | None,
) -> dict[str, Any]:
    """Two-lot exit: lot1 @50 or mid to S/R; lot2 @ S/R or 100."""
    after = day[day["datetime"] >= entry_time].copy()
    if after.empty:
        return _empty()

    if side == "LONG":
        tgt50 = entry_price + DEFAULT_TARGETS[0]
        tgt100 = entry_price + DEFAULT_TARGETS[1]
        if sr_target is not None and sr_target > entry_price:
            mid = entry_price + (sr_target - entry_price) / 2
            lot1_target = min(tgt50, mid) if mid > entry_price + 10 else tgt50
            lot2_target = min(tgt100, sr_target)
        else:
            lot1_target, lot2_target = tgt50, tgt100
    else:
        tgt50 = entry_price - DEFAULT_TARGETS[0]
        tgt100 = entry_price - DEFAULT_TARGETS[1]
        if sr_target is not None and sr_target < entry_price:
            mid = entry_price - (entry_price - sr_target) / 2
            lot1_target = max(tgt50, mid) if mid < entry_price - 10 else tgt50
            lot2_target = max(tgt100, sr_target)
        else:
            lot1_target, lot2_target = tgt50, tgt100

    lot1_open = lot2_open = True
    mae = 0.0
    exit_lot1_time = exit_lot2_time = pd.NaT
    exit_lot1_price = exit_lot2_price = np.nan
    exit_lot1_reason = exit_lot2_reason = "OPEN"

    for _, row in after.iterrows():
        t = row["datetime"]
        hi, lo = float(row["high"]), float(row["low"])

        if side == "LONG":
            mae = max(mae, entry_price - lo)
            if lo <= stop_price:
                price = stop_price
                if lot1_open:
                    exit_lot1_time, exit_lot1_price, exit_lot1_reason = t, price, "STOP"
                    lot1_open = False
                if lot2_open:
                    exit_lot2_time, exit_lot2_price, exit_lot2_reason = t, price, "STOP"
                    lot2_open = False
                break
            if lot1_open and hi >= lot1_target:
                exit_lot1_time, exit_lot1_price, exit_lot1_reason = t, lot1_target, "TARGET_1"
                lot1_open = False
            if lot2_open and hi >= lot2_target:
                exit_lot2_time, exit_lot2_price, exit_lot2_reason = t, lot2_target, "TARGET_2"
                lot2_open = False
                break
        else:
            mae = max(mae, hi - entry_price)
            if hi >= stop_price:
                price = stop_price
                if lot1_open:
                    exit_lot1_time, exit_lot1_price, exit_lot1_reason = t, price, "STOP"
                    lot1_open = False
                if lot2_open:
                    exit_lot2_time, exit_lot2_price, exit_lot2_reason = t, price, "STOP"
                    lot2_open = False
                break
            if lot1_open and lo <= lot1_target:
                exit_lot1_time, exit_lot1_price, exit_lot1_reason = t, lot1_target, "TARGET_1"
                lot1_open = False
            if lot2_open and lo <= lot2_target:
                exit_lot2_time, exit_lot2_price, exit_lot2_reason = t, lot2_target, "TARGET_2"
                lot2_open = False
                break

        if not lot1_open and not lot2_open:
            break

    last = after.iloc[-1]
    if lot1_open:
        exit_lot1_time, exit_lot1_price, exit_lot1_reason = last["datetime"], float(last["close"]), "EOD"
    if lot2_open:
        exit_lot2_time, exit_lot2_price, exit_lot2_reason = last["datetime"], float(last["close"]), "EOD"

    pts1 = (exit_lot1_price - entry_price) if side == "LONG" else (entry_price - exit_lot1_price)
    pts2 = (exit_lot2_price - entry_price) if side == "LONG" else (entry_price - exit_lot2_price)

    return {
        "exit_lot1_time": exit_lot1_time,
        "exit_lot1_price": float(exit_lot1_price),
        "exit_lot2_time": exit_lot2_time,
        "exit_lot2_price": float(exit_lot2_price),
        "exit_lot1_reason": exit_lot1_reason,
        "exit_lot2_reason": exit_lot2_reason,
        "points_lot1": float(pts1),
        "points_lot2": float(pts2),
        "points_total": float(pts1 + pts2),
        "mae_points": float(mae),
        "stopped": exit_lot1_reason == "STOP" or exit_lot2_reason == "STOP",
    }


def _empty() -> dict[str, Any]:
    return {
        "exit_lot1_time": pd.NaT,
        "exit_lot1_price": np.nan,
        "exit_lot2_time": pd.NaT,
        "exit_lot2_price": np.nan,
        "exit_lot1_reason": "NO_DATA",
        "exit_lot2_reason": "NO_DATA",
        "points_lot1": 0.0,
        "points_lot2": 0.0,
        "points_total": 0.0,
        "mae_points": np.nan,
        "stopped": False,
    }


def summarize(trades_df: pd.DataFrame) -> dict[str, Any]:
    if trades_df.empty:
        return {}

    wins = trades_df[trades_df["points_total"] > 0]
    losses = trades_df[trades_df["points_total"] <= 0]
    risk = (trades_df["entry_price"] - trades_df["stop_price"]).abs()

    return {
        "trades": len(trades_df),
        "win_rate": len(wins) / len(trades_df) * 100,
        "stop_rate": trades_df["stopped"].mean() * 100,
        "sr_confluence_rate": trades_df["sr_confluence"].mean() * 100,
        "total_points": trades_df["points_total"].sum(),
        "total_rupees": trades_df["rupee_pnl"].sum(),
        "avg_points": trades_df["points_total"].mean(),
        "avg_rupees": trades_df["rupee_pnl"].mean(),
        "profit_factor": abs(wins["rupee_pnl"].sum() / losses["rupee_pnl"].sum())
        if len(losses) and losses["rupee_pnl"].sum()
        else np.inf,
        "median_risk_pts": risk.median(),
        "avg_mae_pts": trades_df["mae_points"].mean(),
    }


def write_report(path: Path, summary: dict[str, Any], trades_df: pd.DataFrame, *, args) -> None:
    lines = [
        "# Phase 4B Weis Spring Simulator",
        "",
        "**Entry:** spring/upthrust confirm at prior session VAH/VAL (profile-based)",
        f"**Stop:** structural ±{STOP_BUFFER} pts beyond break extreme",
        "**Exit:** lot1 @50/mid-SR, lot2 @ S/R or 100",
        f"**SR filter:** {'required' if args.require_sr else 'optional'}",
        f"**Time filter:** {'none' if args.no_time_filter else ('morning only' if args.morning_only else '10:30–11:30 + 13:30–15:00')}",
        "",
        "## Summary",
        "",
    ]
    for k, v in summary.items():
        if isinstance(v, float):
            lines.append(f"- **{k}:** {v:,.2f}")
        else:
            lines.append(f"- **{k}:** {v}")

    if not trades_df.empty:
        lines.extend(["", "## By event type", ""])
        for event, g in trades_df.groupby("event"):
            wins = (g["points_total"] > 0).sum()
            lines.append(
                f"- **{event}:** {len(g)} trades, win rate {wins/len(g)*100:.1f}%, "
                f"total ₹{g['rupee_pnl'].sum():,.0f}"
            )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading index master…")
    master = load_master(args.master)
    if args.start:
        master = master[master["date"] >= pd.Timestamp(args.start).date()]
    if args.end:
        master = master[master["date"] <= pd.Timestamp(args.end).date()]

    futures = load_futures_master(args.futures)
    if futures.empty:
        futures = seed_from_10d()
    print(f"Futures bars: {len(futures)} sessions={futures['datetime'].dt.date.nunique() if not futures.empty else 0}")

    levels_cache = build_levels_cache(futures, index_df=master)
    median_bars = compute_median_session_bars(master)
    sessions = {d: build_session_meta(d, g, median_bars) for d, g in master.groupby("date", sort=True)}

    trades: list[SpringTrade] = []
    for day_date, meta in sessions.items():
        levels = levels_cache.get(day_date)
        if levels is None or levels.vah is None or levels.val is None:
            continue

        range_high = float(levels.vah)
        range_low = float(levels.val)

        events: list[tuple[str, dict]] = []
        for ev in detect_springs_at_range(meta, range_high, range_low):
            events.append(("SPRING", ev))
        for ev in detect_upthrusts_at_range(meta, range_high, range_low):
            events.append(("UPTHRUST", ev))

        for event_name, ev in events:
            confirm_time = pd.Timestamp(ev["confirm_time"])
            if not in_time_window(confirm_time, morning_only=args.morning_only, no_filter=args.no_time_filter):
                continue

            side = "LONG" if event_name == "SPRING" else "SHORT"
            level = float(ev["level"])
            confluence = False
            if levels is not None:
                confluence = has_sr_confluence(levels, level, side)
            if args.require_sr and not confluence:
                continue

            entry_price = float(ev["confirm_price"])
            break_extreme = float(ev["break_price"])
            if side == "LONG":
                stop_price = break_extreme - STOP_BUFFER
            else:
                stop_price = break_extreme + STOP_BUFFER

            sr_target = None
            if levels is not None:
                sr_target = nearest_target_level(levels, entry_price, side)

            sim = simulate_structural_trade(
                meta.day,
                entry_time=confirm_time,
                entry_price=entry_price,
                side=side,
                stop_price=stop_price,
                sr_target=sr_target,
            )

            rupee = (sim["points_lot1"] + sim["points_lot2"]) * args.lot_size
            trades.append(
                SpringTrade(
                    date=day_date,
                    event=event_name,
                    side=side,
                    entry_time=confirm_time,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    sr_confluence=confluence,
                    exit_lot1_time=sim["exit_lot1_time"],
                    exit_lot1_price=sim["exit_lot1_price"],
                    exit_lot2_time=sim["exit_lot2_time"],
                    exit_lot2_price=sim["exit_lot2_price"],
                    exit_lot1_reason=sim["exit_lot1_reason"],
                    exit_lot2_reason=sim["exit_lot2_reason"],
                    points_lot1=sim["points_lot1"],
                    points_lot2=sim["points_lot2"],
                    points_total=sim["points_total"],
                    rupee_pnl=rupee,
                    mae_points=sim["mae_points"],
                    sr_target=sr_target,
                    stopped=sim["stopped"],
                )
            )

    df = pd.DataFrame([t.__dict__ for t in trades])
    df.to_csv(args.output_dir / "spring_trades.csv", index=False)

    summary = summarize(df)
    write_report(args.output_dir / "phase4b_weis_spring_report.md", summary, df, args=args)

    print(f"Trades: {len(trades)}")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {args.output_dir}/")


if __name__ == "__main__":
    main()
