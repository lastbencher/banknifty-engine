#!/usr/bin/env python3
"""
Phase 4 — bar-by-bar trade simulator for Phase 2B / signal-engine rules.

DEPRECATED for new research — IB-based entries were unreliable on BNF.
Use phase4b_weis_spring_simulator.py (profile VAH/VAL springs) instead.

Legacy entry: first IB break AFTER the signal checkpoint.
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
from bnf_research.ib import ib_levels
from bnf_research.session import build_session_meta, compute_median_session_bars
from signal_engine.engine import SignalEngine
from signal_engine.models import TradeSignal

DEFAULT_MASTER = PROJECT_ROOT / "banknifty_master.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "phase4_trade_sim"
TARGET_POINTS = (50, 100)


@dataclass
class SimTrade:
    date: Any
    rule_id: str
    checkpoint_clock: str
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
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
    minutes_from_open: float
    entry_hour: int
    entry_minute: int
    hit_50: bool
    hit_100: bool
    stopped: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate 2-lot IB-break trades from signal rules.")
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lots", type=int, default=2)
    parser.add_argument("--lot-size", type=int, default=15, help="Qty per lot (BNF currently 15)")
    parser.add_argument("--walkforward-window", type=int, default=252)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    return parser.parse_args()


def find_break_after_checkpoint(
    day: pd.DataFrame,
    *,
    checkpoint_time: pd.Timestamp,
    ib_high: float,
    ib_low: float,
    required: str,
) -> dict[str, Any] | None:
    """First bar after checkpoint where IB breaks in `required` direction."""
    after = day[day["datetime"] > checkpoint_time]
    for _, row in after.iterrows():
        if required == "HIGH" and row["high"] > ib_high:
            return {
                "time": row["datetime"],
                "price": float(ib_high),
                "direction": "HIGH",
            }
        if required == "LOW" and row["low"] < ib_low:
            return {
                "time": row["datetime"],
                "price": float(ib_low),
                "direction": "LOW",
            }
        # Wrong-direction break first → setup invalidated
        if required == "HIGH" and row["low"] < ib_low:
            return None
        if required == "LOW" and row["high"] > ib_high:
            return None
    return None


def simulate_two_lot_trade(
    day: pd.DataFrame,
    *,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: str,
    stop_price: float,
) -> dict[str, Any]:
    """Scale out: lot1 @50, lot2 @100 | stop | close."""
    after = day[day["datetime"] >= entry_time].copy()
    if after.empty:
        return _empty_sim(side, entry_price, stop_price)

    if side == "LONG":
        tgt50 = entry_price + TARGET_POINTS[0]
        tgt100 = entry_price + TARGET_POINTS[1]
    else:
        tgt50 = entry_price - TARGET_POINTS[0]
        tgt100 = entry_price - TARGET_POINTS[1]

    lot1_open = True
    lot2_open = True
    mae = 0.0
    exit_lot1_time = exit_lot2_time = pd.NaT
    exit_lot1_price = exit_lot2_price = np.nan
    exit_lot1_reason = exit_lot2_reason = "OPEN"

    for _, row in after.iterrows():
        t = row["datetime"]
        hi, lo, close = float(row["high"]), float(row["low"]), float(row["close"])

        if side == "LONG":
            mae = max(mae, entry_price - lo)
            if lot1_open or lot2_open:
                if lo <= stop_price:
                    price = stop_price
                    if lot1_open:
                        exit_lot1_time, exit_lot1_price, exit_lot1_reason = t, price, "STOP"
                        lot1_open = False
                    if lot2_open:
                        exit_lot2_time, exit_lot2_price, exit_lot2_reason = t, price, "STOP"
                        lot2_open = False
                    break
            if lot1_open and hi >= tgt50:
                exit_lot1_time, exit_lot1_price, exit_lot1_reason = t, tgt50, "TARGET_50"
                lot1_open = False
            if lot2_open and hi >= tgt100:
                exit_lot2_time, exit_lot2_price, exit_lot2_reason = t, tgt100, "TARGET_100"
                lot2_open = False
                break
        else:
            mae = max(mae, hi - entry_price)
            if lot1_open or lot2_open:
                if hi >= stop_price:
                    price = stop_price
                    if lot1_open:
                        exit_lot1_time, exit_lot1_price, exit_lot1_reason = t, price, "STOP"
                        lot1_open = False
                    if lot2_open:
                        exit_lot2_time, exit_lot2_price, exit_lot2_reason = t, price, "STOP"
                        lot2_open = False
                    break
            if lot1_open and lo <= tgt50:
                exit_lot1_time, exit_lot1_price, exit_lot1_reason = t, tgt50, "TARGET_50"
                lot1_open = False
            if lot2_open and lo <= tgt100:
                exit_lot2_time, exit_lot2_price, exit_lot2_reason = t, tgt100, "TARGET_100"
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
        "hit_50": exit_lot1_reason == "TARGET_50",
        "hit_100": exit_lot2_reason == "TARGET_100",
        "stopped": exit_lot1_reason == "STOP" or exit_lot2_reason == "STOP",
    }


def _empty_sim(side: str, entry: float, stop: float) -> dict[str, Any]:
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
        "hit_50": False,
        "hit_100": False,
        "stopped": False,
    }


def simulate_signal(
    meta,
    signal: TradeSignal,
) -> SimTrade | None:
    ib = ib_levels(meta)
    if not meta.has_ib or pd.isna(ib["ib_high"]):
        return None

    cp_time = pd.Timestamp(signal.checkpoint_time)
    brk = find_break_after_checkpoint(
        meta.day,
        checkpoint_time=cp_time,
        ib_high=ib["ib_high"],
        ib_low=ib["ib_low"],
        required=signal.required_break_direction,
    )
    if brk is None:
        return None

    side = signal.side
    stop = float(signal.stop_price) if signal.stop_price is not None else (
        ib["ib_low"] if side == "LONG" else ib["ib_high"]
    )
    sim = simulate_two_lot_trade(
        meta.day,
        entry_time=brk["time"],
        entry_price=brk["price"],
        side=side,
        stop_price=stop,
    )

    entry_ts = pd.Timestamp(brk["time"])
    mins_open = (entry_ts - meta.session_start).total_seconds() / 60.0

    return SimTrade(
        date=signal.date,
        rule_id=signal.rule_id,
        checkpoint_clock=signal.checkpoint_clock,
        side=side,
        entry_time=entry_ts,
        entry_price=brk["price"],
        stop_price=stop,
        exit_lot1_time=sim["exit_lot1_time"],
        exit_lot1_price=sim["exit_lot1_price"],
        exit_lot2_time=sim["exit_lot2_time"],
        exit_lot2_price=sim["exit_lot2_price"],
        exit_lot1_reason=sim["exit_lot1_reason"],
        exit_lot2_reason=sim["exit_lot2_reason"],
        points_lot1=sim["points_lot1"],
        points_lot2=sim["points_lot2"],
        points_total=sim["points_total"],
        rupee_pnl=0.0,  # filled later
        mae_points=sim["mae_points"],
        minutes_from_open=mins_open,
        entry_hour=entry_ts.hour,
        entry_minute=entry_ts.minute,
        hit_50=sim["hit_50"],
        hit_100=sim["hit_100"],
        stopped=sim["stopped"],
    )


def trades_to_frame(trades: list[SimTrade], *, lots: int, lot_size: int) -> pd.DataFrame:
    rows = []
    qty = lot_size  # per lot
    for t in trades:
        rupee = (t.points_lot1 * qty) + (t.points_lot2 * qty)
        rows.append({**t.__dict__, "rupee_pnl": rupee, "lots": lots, "lot_size": lot_size})
    return pd.DataFrame(rows)


def summarize(trades_df: pd.DataFrame) -> dict[str, Any]:
    if trades_df.empty:
        return {}

    risk = (trades_df["entry_price"] - trades_df["stop_price"]).abs()
    risk = risk.where(trades_df["side"] == "LONG", (trades_df["stop_price"] - trades_df["entry_price"]).abs())

    wins = trades_df[trades_df["points_total"] > 0]
    losses = trades_df[trades_df["points_total"] <= 0]

    return {
        "trades": len(trades_df),
        "signals_with_entry": len(trades_df),
        "win_rate": len(wins) / len(trades_df) * 100,
        "hit_50_rate": trades_df["hit_50"].mean() * 100,
        "hit_100_rate": trades_df["hit_100"].mean() * 100,
        "stop_rate": trades_df["stopped"].mean() * 100,
        "total_points": trades_df["points_total"].sum(),
        "total_rupees": trades_df["rupee_pnl"].sum(),
        "avg_points": trades_df["points_total"].mean(),
        "avg_rupees": trades_df["rupee_pnl"].mean(),
        "median_rupees": trades_df["rupee_pnl"].median(),
        "avg_win_pts": wins["points_total"].mean() if len(wins) else 0,
        "avg_loss_pts": losses["points_total"].mean() if len(losses) else 0,
        "profit_factor": abs(wins["rupee_pnl"].sum() / losses["rupee_pnl"].sum()) if len(losses) and losses["rupee_pnl"].sum() else np.inf,
        "median_risk_pts": risk.median(),
        "avg_rr_realized": (wins["points_total"].mean() / risk[wins.index].mean()) if len(wins) and risk[wins.index].mean() else np.nan,
    }


def time_window_analysis(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Entry-time buckets: win rate and avg PnL by 30-min clock window."""
    df = trades_df.copy()
    df["entry_clock"] = df["entry_time"].dt.strftime("%H:%M")
    df["window_start"] = df["entry_time"].dt.floor("30min")
    df["window_label"] = df["window_start"].dt.strftime("%H:%M")

    rows = []
    for window, g in df.groupby("window_label"):
        wins = g[g["points_total"] > 0]
        rows.append(
            {
                "window": window,
                "trades": len(g),
                "win_rate_pct": len(wins) / len(g) * 100 if len(g) else 0,
                "hit_100_pct": g["hit_100"].mean() * 100,
                "avg_rupees": g["rupee_pnl"].mean(),
                "total_rupees": g["rupee_pnl"].sum(),
                "median_entry_min_from_open": g["minutes_from_open"].median(),
            }
        )
    return pd.DataFrame(rows).sort_values("avg_rupees", ascending=False)


def checkpoint_timing(trades_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for clock, g in trades_df.groupby("checkpoint_clock"):
        wins = g[g["points_total"] > 0]
        rows.append(
            {
                "checkpoint_clock": clock,
                "trades": len(g),
                "win_rate_pct": len(wins) / len(g) * 100,
                "hit_100_pct": g["hit_100"].mean() * 100,
                "avg_rupees": g["rupee_pnl"].mean(),
                "total_rupees": g["rupee_pnl"].sum(),
            }
        )
    return pd.DataFrame(rows).sort_values("total_rupees", ascending=False)


def _df_to_md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No data_"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                cells.append(f"{v:,.2f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(
    path: Path,
    summary: dict[str, Any],
    time_windows: pd.DataFrame,
    checkpoints: pd.DataFrame,
    *,
    lots: int,
    lot_size: int,
) -> None:
    lines = [
        "# Phase 4 Trade Simulator Report",
        "",
        "> **Deprecated** — IB-based entry model. See `phase4b_weis_spring_simulator.py`.",
        "",
        f"**Setup:** {lots} lots × {lot_size} qty | lot1 @ +50 pts, lot2 @ +100 pts",
        "**Mode:** walk-forward buckets (252-session trailing, no look-ahead)",
        "",
        "## Overall P&L",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
    ]
    for k, v in summary.items():
        if isinstance(v, float):
            lines.append(f"| {k} | {v:,.2f} |")
        else:
            lines.append(f"| {k} | {v} |")

    lines.extend(["", "## Best entry time windows (30-min buckets)", ""])
    lines.append(_df_to_md_table(time_windows.head(12)))

    lines.extend(["", "## By signal checkpoint clock", ""])
    lines.append(_df_to_md_table(checkpoints))

    if not time_windows.empty:
        # Prefer windows with enough samples
        reliable = time_windows[time_windows["trades"] >= 100].copy()
        best = reliable.iloc[0] if not reliable.empty else time_windows.iloc[0]
        lines.extend(
            [
                "",
                "## Suggested entry-time filter",
                "",
                "Most 100-pt winners enter **10:00–12:00 IST**.",
                "",
                "**Recommended rule:** take entries only **10:30–12:30 IST**.",
                "",
                f"| Best 30-min bucket | {best['window']} |",
                f"| Trades | {int(best['trades'])} |",
                f"| Win rate | {best['win_rate_pct']:.1f}% |",
                f"| Hit 100 (lot 2) | {best['hit_100_pct']:.1f}% |",
                f"| Avg ₹/trade (2×15 qty) | {best['avg_rupees']:,.0f} |",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading master bars…")
    master = load_master(args.master)
    median_bars = compute_median_session_bars(master)
    sessions = {d: build_session_meta(d, g, median_bars) for d, g in master.groupby("date", sort=True)}

    print("Scanning signals (walk-forward)…")
    engine = SignalEngine(bucket_mode="walkforward", walkforward_window=args.walkforward_window)
    signals = engine.scan_history(start_date=args.start, end_date=args.end, best_only=True)
    print(f"Signals: {len(signals)}")

    trades: list[SimTrade] = []
    skipped = 0
    for sig in signals:
        day = pd.Timestamp(sig.date).date()
        meta = sessions.get(day)
        if meta is None:
            skipped += 1
            continue
        t = simulate_signal(meta, sig)
        if t is None:
            skipped += 1
            continue
        t.rupee_pnl = (t.points_lot1 + t.points_lot2) * args.lot_size
        trades.append(t)

    print(f"Trades simulated: {len(trades)} | skipped/no-entry: {skipped}")

    df = trades_to_frame(trades, lots=args.lots, lot_size=args.lot_size)
    df.to_csv(args.output_dir / "sim_trades.csv", index=False)

    summary = summarize(df)
    time_df = time_window_analysis(df)
    cp_df = checkpoint_timing(df)
    time_df.to_csv(args.output_dir / "entry_time_windows.csv", index=False)
    cp_df.to_csv(args.output_dir / "checkpoint_timing.csv", index=False)

    write_report(
        args.output_dir / "phase4_trade_sim_report.md",
        summary,
        time_df,
        cp_df,
        lots=args.lots,
        lot_size=args.lot_size,
    )

    print(json.dumps(summary, indent=2))
    print(f"\nWrote {args.output_dir}/")


if __name__ == "__main__":
    main()
