"""EOD regime + levels summary for Telegram."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from bnf_research.build import load_master
from bnf_research.day_regime import latest_session_label
from bnf_research.futures_data import FUTURES_MASTER_PATH, load_futures_master, seed_from_10d
from bnf_research.market_profile import (
    build_hybrid_profiles,
    classify_day_type,
    merge_index_futures_bars,
    prepare_day_frame,
)
from bnf_research.zone_engine import build_zone_scores, demand_supply_zones


def _next_trading_day(d: date) -> date:
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def format_regime_telegram(
    *,
    as_of: date | None = None,
    index_path: Path | None = None,
    futures_path: Path | None = None,
) -> str:
    """Compact EOD read: regime label + next session key S/R from latest EOD."""
    root = Path(__file__).resolve().parents[1]
    index_path = index_path or root / "banknifty_master.csv"
    futures_path = futures_path or FUTURES_MASTER_PATH

    if not index_path.exists():
        return "No index data — run /update first."

    index = load_master(index_path)
    futures = load_futures_master(futures_path)
    if futures.empty:
        futures = seed_from_10d()

    m = latest_session_label(index)
    if not m:
        return "Could not compute regime for latest session."

    session_date = as_of or m["date"]
    if isinstance(session_date, pd.Timestamp):
        session_date = session_date.date()

    hybrid = merge_index_futures_bars(index, futures) if not futures.empty else index
    prep = prepare_day_frame(hybrid)
    day_frame = prep[prep["date"] == session_date]
    profiles = build_hybrid_profiles(index, futures) if not futures.empty else pd.DataFrame()

    lines = [
        f"📊 Regime — {session_date}",
        f"Label: {m['regime']}",
        f"Day type: {classify_day_type(day_frame) if not day_frame.empty else 'n/a'}",
        f"Range {m['day_range']:.0f} | Net {m['net_move']:+.0f} | Eff {m['efficiency']:.2f}",
        f"Close {m['day_close']:.0f}",
    ]

    if not profiles.empty and session_date in set(profiles["date"]):
        p = profiles[profiles["date"] == session_date].iloc[0]
        lines.append(f"POC {p['POC']:.0f} | VAH {p['VAH']:.0f} | VAL {p['VAL']:.0f}")

    nxt = _next_trading_day(session_date)
    lines.extend(["", f"Next session ({nxt}) — S/R from {session_date} EOD:"])

    if not profiles.empty and session_date in set(profiles["date"]):
        p = profiles[profiles["date"] == session_date].iloc[0]
        lines.append(f"Ref POC/VAH/VAL: {p['POC']:.0f} / {p['VAH']:.0f} / {p['VAL']:.0f}")

    if not futures.empty:
        hist = prep[prep["date"] <= session_date].tail(375 * 5)
        if not hist.empty:
            zones = build_zone_scores(hist)
            demand, supply = demand_supply_zones(zones, float(m["day_close"]))
            if demand:
                lines.append(f"Demand: {', '.join(f'{z:.0f}' for z in demand[:4])}")
            if supply:
                lines.append(f"Supply: {', '.join(f'{z:.0f}' for z in supply[:4])}")

    bias = {
        "WILD_TREND": "Trend day — continuation bias; pullbacks shallow",
        "TREND": "Directional — trade with bias, POC = magnet",
        "CHOPPY": "Two-way — fade breaks, springs at VAH/VAL",
        "BORING": "Tight range — scalp POC only",
    }
    lines.extend(["", bias.get(str(m["regime"]), "See /view for full read")])

    return "\n".join(lines)
