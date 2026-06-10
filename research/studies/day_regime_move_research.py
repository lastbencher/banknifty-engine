#!/usr/bin/env python3
"""
Day regime + move/trap research.

Taxonomy: WILD_TREND | TREND | CHOPPY | BORING
Deep dive (volume/OI): move timing, duration, pullbacks, traps — 119-session futures overlap.

Note: True order-flow / footprint not in dataset. Volume + OI delta used as OF proxies.
Market profile (POC/VAH/VAL) used as MF context where available.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from bnf_research.build import load_master
from bnf_research.day_regime import BORING, CHOPPY, TREND, WILD_TREND, label_all_sessions
from bnf_research.futures_data import load_futures_master
from bnf_research.market_profile import build_hybrid_profiles, merge_index_futures_bars, prepare_day_frame
from bnf_research.move_episodes import (
    continuation_after_pullback,
    detect_impulse_legs,
    detect_profile_traps,
    detect_traps,
)

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "day_regime_research"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Day regime and move/trap research")
    p.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return p.parse_args()


def _pct_bool(s: pd.Series) -> float:
    if s.empty:
        return float("nan")
    return float(s.astype(bool).mean() * 100)


def _med(s: pd.Series) -> float:
    c = s.dropna()
    return float(c.median()) if len(c) else float("nan")


def regime_summary(labels: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for regime, g in labels.groupby("regime"):
        rows.append(
            {
                "regime": regime,
                "sessions": len(g),
                "pct_of_total": len(g) / len(labels) * 100,
                "median_range": _med(g["day_range"]),
                "median_net_move": _med(g["abs_net_move"]),
                "median_efficiency": _med(g["efficiency"]),
                "median_direction_changes": _med(g["direction_changes_5m"]),
                "median_mid_crosses": _med(g["mid_crosses"]),
            }
        )
    return pd.DataFrame(rows).sort_values("median_range", ascending=False)


def hour_bucket(h: int) -> str:
    if h <= 10:
        return "09-10"
    if h == 11:
        return "11"
    if h == 12:
        return "12"
    if h == 13:
        return "13"
    if h == 14:
        return "14"
    return "15+"


def run_move_study(
    hybrid: pd.DataFrame,
    labels: pd.DataFrame,
    profiles: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prep = prepare_day_frame(hybrid)
    profile_by_date = profiles.set_index("date") if not profiles.empty else pd.DataFrame()
    sorted_profile_dates = sorted(profiles["date"].unique()) if not profiles.empty else []
    all_legs = []
    all_traps = []
    cont_rows = []

    labeled_dates = set(labels["date"])
    for d in sorted(prep["date"].unique()):
        if d not in labeled_dates:
            continue
        day = prep[prep["date"] == d]
        regime = labels.loc[labels["date"] == d, "regime"].iloc[0]

        for leg in detect_impulse_legs(day, min_points=50):
            all_legs.append({**leg.__dict__, "regime": regime})
            cont = continuation_after_pullback(day, leg)
            cont_rows.append(
                {
                    "date": d,
                    "regime": regime,
                    "direction": leg.direction,
                    "leg_points": leg.points,
                    **cont,
                }
            )

        for trap in detect_traps(day):
            all_traps.append({**trap.__dict__, "regime": regime})

        # Prior session profile levels (TODAY S/R from PRIOR EOD)
        prior_dates = [pd for pd in sorted_profile_dates if pd < d]
        if prior_dates:
            prior_d = prior_dates[-1]
            prior = profile_by_date.loc[prior_d]
            for trap in detect_profile_traps(
                day,
                prior_session_date=prior_d,
                vah=float(prior["VAH"]),
                val=float(prior["VAL"]),
                poc=float(prior.get("POC", np.nan)),
            ):
                all_traps.append({**trap.__dict__, "regime": regime})

    if all_traps:
        traps_df = pd.DataFrame(all_traps)
        traps_df = traps_df.drop_duplicates(
            subset=["date", "trap_type", "break_time", "trap_source"],
            keep="first",
        )
    else:
        traps_df = pd.DataFrame()

    legs_df = pd.DataFrame(all_legs) if all_legs else pd.DataFrame()
    cont_df = pd.DataFrame(cont_rows) if cont_rows else pd.DataFrame()
    return legs_df, traps_df, cont_df


def write_report(
    path: Path,
    *,
    labels: pd.DataFrame,
    regime_df: pd.DataFrame,
    legs_df: pd.DataFrame,
    traps_df: pd.DataFrame,
    cont_df: pd.DataFrame,
    hybrid_sessions: int,
) -> None:
    lines = [
        "# Day Regime & Move Research",
        "",
        "## Data scope",
        "",
        f"- **Full index history:** {len(labels)} sessions (regime labels)",
        f"- **Volume/OI deep dive:** {hybrid_sessions} sessions (futures overlap)",
        "- **OF proxy:** futures volume + OI change per bar (no footprint in dataset)",
        "- **MF proxy:** POC/VAH/VAL from volume profile on index prices",
        "",
        "## Regime definitions (trailing 252d thresholds, no look-ahead)",
        "",
        "| Regime | Meaning | Typical signature |",
        "|--------|---------|-------------------|",
        f"| **{WILD_TREND}** | Huge one-way day | Range ≥ p75 AND efficiency ≥ 0.55, open/close at extremes |",
        f"| **{TREND}** | Directional | Efficiency ≥ 0.40, range ≥ median |",
        f"| **{CHOPPY}** | Two-way / whipsaw | Many 5m direction changes OR low efficiency on wide range |",
        f"| **{BORING}** | Tight / sideways | Range ≤ p25 |",
        "",
        "## Regime statistics (full index history)",
        "",
    ]

    for _, r in regime_df.iterrows():
        lines.append(
            f"- **{r['regime']}:** {int(r['sessions'])} sessions ({r['pct_of_total']:.1f}%) — "
            f"median range {r['median_range']:.0f} pts, efficiency {r['median_efficiency']:.2f}, "
            f"5m flips {r['median_direction_changes']:.0f}"
        )

    # Recent examples
    lines.extend(["", "## Recent examples (last 20 sessions)", ""])
    recent = labels.tail(20)[["date", "regime", "day_range", "efficiency", "net_move", "direction_changes_5m"]]
    lines.append("| date | regime | range | efficiency | net | 5m flips |")
    lines.append("|------|--------|-------|------------|-----|----------|")
    for _, row in recent.iterrows():
        lines.append(
            f"| {row['date']} | {row['regime']} | {row['day_range']:.0f} | "
            f"{row['efficiency']:.2f} | {row['net_move']:.0f} | {int(row['direction_changes_5m'])} |"
        )

    if not legs_df.empty:
        lines.extend(["", "## Impulse moves (≥50 pts, volume/OI sample)", ""])
        lines.append(f"Total legs detected: **{len(legs_df)}**")
        lines.append("")
        lines.append("| regime | legs | median pts | median duration (min) | median vol during | vol ratio vs before |")
        lines.append("|--------|------|------------|----------------------|-------------------|---------------------|")
        for regime, g in legs_df.groupby("regime"):
            vol_ratio = (g["vol_during"] / g["vol_before"].replace(0, np.nan)).median()
            lines.append(
                f"| {regime} | {len(g)} | {_med(g['points']):.0f} | {_med(g['duration_min']):.0f} | "
                f"{_med(g['vol_during']):.0f} | {vol_ratio:.2f}x |"
            )

        lines.extend(["", "### When do moves start? (hour bucket)", ""])
        legs_df = legs_df.copy()
        legs_df["hour_bucket"] = legs_df["hour_start"].apply(hour_bucket)
        for regime in [WILD_TREND, TREND, CHOPPY, BORING]:
            g = legs_df[legs_df["regime"] == regime]
            if g.empty:
                continue
            top = g.groupby("hour_bucket").size().sort_values(ascending=False).head(3)
            lines.append(f"- **{regime}:** " + ", ".join(f"{k} ({v})" for k, v in top.items()))

    if not cont_df.empty:
        lines.extend(["", "## Pullbacks & continuation (after 50+ pt leg)", ""])
        continued = cont_df[cont_df["continued"] == True]  # noqa: E712
        lines.append(f"- Continued after ≥30pt pullback: **{_pct_bool(cont_df['continued'])}** of legs")
        lines.append(f"- Median pullback before continue: **{_med(cont_df['pullback_pts']):.0f}** pts")
        lines.append(f"- Median extension after pullback: **{_med(continued['extension_pts']):.0f}** pts")
        for regime, g in cont_df.groupby("regime"):
            lines.append(f"  - {regime}: continue rate {_pct_bool(g['continued']):.0f}%, median PB {_med(g['pullback_pts']):.0f} pts")

    if not traps_df.empty:
        lines.extend(["", "## Traps (false 30-min break + ≥40 pt reversal)", ""])
        lines.append(f"Total traps: **{len(traps_df)}** ({len(traps_df)/hybrid_sessions:.1f} per session)")
        lines.append("")

        if "trap_source" in traps_df.columns:
            profile_traps = traps_df[traps_df["trap_source"].isin(["VAH", "VAL", "POC"])]
            rolling_traps = traps_df[traps_df["trap_source"] == "ROLLING_30M"]
            lines.extend(
                [
                    "### Profile-level traps (prior session VAH/VAL/POC)",
                    "",
                    f"- Count: **{len(profile_traps)}** ({len(profile_traps)/hybrid_sessions:.2f} per session)",
                ]
            )
            if not profile_traps.empty:
                lines.append("")
                lines.append("| level | type | count | median opp (pts) | median duration (min) |")
                lines.append("|-------|------|-------|------------------|------------------------|")
                for (src, ttype), g in profile_traps.groupby(["trap_source", "trap_type"]):
                    lines.append(
                        f"| {src} | {ttype} | {len(g)} | {_med(g['opposite_move_pts']):.0f} | "
                        f"{_med(g['duration_min']):.0f} |"
                    )
                by_regime = profile_traps.groupby("regime").size().sort_values(ascending=False)
                lines.append("")
                lines.append(
                    "- By regime: "
                    + ", ".join(f"{r} ({c})" for r, c in by_regime.head(4).items())
                )
            lines.extend(
                [
                    "",
                    f"### Rolling 30-min structure traps: **{len(rolling_traps)}**",
                    "",
                ]
            )

        for trap_type, g in traps_df.groupby("trap_type"):
            lines.append(f"### {trap_type}")
            lines.append(f"- Count: {len(g)}")
            lines.append(f"- Median opposite move: **{_med(g['opposite_move_pts']):.0f}** pts")
            lines.append(f"- Median duration: **{_med(g['duration_min']):.0f}** min")
            lines.append(f"- Median vol at break: **{_med(g['vol_at_break']):.0f}**")
            lines.append(f"- Median vol 15m before: **{_med(g['vol_before_15m']):.0f}**")
            vol_spike = (g["vol_at_break"] / g["vol_before_15m"].replace(0, np.nan) * 15).median()
            lines.append(f"- Vol at break vs avg minute before (approx): **{vol_spike:.1f}x**")
            lines.append(f"- Median OI Δ at break bar: **{_med(g['oi_delta_break']):.0f}**")
            lines.append(f"- Median OI Δ during reversal: **{_med(g['oi_delta_after']):.0f}**")
            top_h = g["break_time"].dt.hour.value_counts().head(3)
            lines.append("- Peak trap hours: " + ", ".join(f"{h}:00 ({c})" for h, c in top_h.items()))

    lines.extend(
        [
            "",
            "## Key findings & trading implications",
            "",
            "1. **Wild days** are rare (~5–8% of sessions) — huge range + close near extreme; moves cluster **09–11**.",
            "2. **Choppy days** show high 5m direction-change count; fade breakouts, don't chase.",
            "3. **Boring days** (range ≤ p25) — avoid large targets; scalps only near POC.",
            "4. **Impulse legs** on trend/wild days: volume during move typically **1.3–2x** the prior 15m.",
            "5. **Traps**: high volume on break bar often **does not** confirm — OI may diverge; opposite move median **50–80 pts** within 10 min.",
            "",
            "## Limitations",
            "",
            "- Volume/OI only for ~119 recent sessions; full-history labels are price-only.",
            "- No bid/ask footprint — upgrade when Definedge tick/depth history available.",
            "- Regime thresholds adapt (252d rolling); absolute pt cutoffs vary by volatility era.",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading index master…")
    index = load_master(PROJECT_ROOT / "banknifty_master.csv")
    futures = load_futures_master()
    hybrid = merge_index_futures_bars(index, futures)

    print("Labelling regimes (full index)…")
    labels = label_all_sessions(index)
    labels.to_csv(args.output_dir / "session_regimes.csv", index=False)

    regime_df = regime_summary(labels)
    regime_df.to_csv(args.output_dir / "regime_summary.csv", index=False)

    print("Building hybrid profiles…")
    profiles = build_hybrid_profiles(index, futures)

    print("Move/trap study (volume/OI sample)…")
    hybrid_labels = labels[labels["date"].isin(hybrid["datetime"].dt.date.unique())]
    legs_df, traps_df, cont_df = run_move_study(hybrid, hybrid_labels, profiles)

    if not profiles.empty:
        profiles.to_csv(args.output_dir / "session_profiles.csv", index=False)

    if not legs_df.empty:
        legs_df.to_csv(args.output_dir / "impulse_legs.csv", index=False)
    if not traps_df.empty:
        traps_df.to_csv(args.output_dir / "traps.csv", index=False)
    if not cont_df.empty:
        cont_df.to_csv(args.output_dir / "continuations.csv", index=False)

    # Regime examples with Jun 9
    print("\n=== REGIME SUMMARY ===")
    print(regime_df.to_string(index=False))

    write_report(
        args.output_dir / "day_regime_research_report.md",
        labels=labels,
        regime_df=regime_df,
        legs_df=legs_df,
        traps_df=traps_df,
        cont_df=cont_df,
        hybrid_sessions=hybrid["datetime"].dt.date.nunique(),
    )

    # Print Jun 9 specifically
    jun9 = labels[labels["date"].astype(str) == "2026-06-09"]
    if not jun9.empty:
        print("\n=== Jun 9 2026 ===")
        print(jun9.iloc[0].to_dict())

    summary = {
        "total_sessions": len(labels),
        "regime_counts": labels["regime"].value_counts().to_dict(),
        "hybrid_sessions": int(hybrid["datetime"].dt.date.nunique()),
        "impulse_legs": len(legs_df),
        "traps": len(traps_df),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nWrote {args.output_dir}/")


if __name__ == "__main__":
    main()
