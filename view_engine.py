#!/usr/bin/env python3
"""
View Engine — session views at every 3-min and 5-min checkpoint.

Grid (from 09:15 open): 09:18, 09:20, 09:21, 09:24, 09:25, 09:27, 09:30,
09:33, 09:35, 09:36, 09:39, 09:40, 09:42, 09:45

Maturity bands (same logic at each cadence slot):
  QUICK      — minutes < 15  (early bias from opening momentum)
  CONFIRMED  — 15 ≤ minutes < 30  (trend / rotation / trap read)
  CONVICTION — minutes ≥ 30  (day-type classification)

Anchor layers (legacy): Quick @ 09:20, Confirmed @ 09:30, Conviction @ 09:45.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bnf_research.config import CHECKPOINTS, view_maturity


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FEATURE_DIR = PROJECT_ROOT / "features"


@dataclass(frozen=True)
class SessionView:
    date: Any
    layer: str
    checkpoint_minute: int
    checkpoint_clock: str
    cadence: str
    bias: str
    trend_probability: float
    opposite_break_probability: float
    trap_probability: float
    expected_excursion_50: float
    expected_excursion_100: float
    day_type: str | None
    signals: dict[str, Any]


class ViewEngine:
    def __init__(self, feature_dir: Path = DEFAULT_FEATURE_DIR) -> None:
        self.feature_dir = feature_dir
        self._daily: pd.DataFrame | None = None
        self._checkpoints: pd.DataFrame | None = None
        self._base_rates: dict[str, float] = {}

    def load(self) -> None:
        self._daily = pd.read_csv(
            self.feature_dir / "daily_features.csv",
            parse_dates=["date", "session_start", "session_end"],
        )
        self._checkpoints = pd.read_csv(
            self.feature_dir / "checkpoint_features.csv",
            parse_dates=["date", "checkpoint_time"],
        )
        self._compute_base_rates()

    @property
    def daily(self) -> pd.DataFrame:
        if self._daily is None:
            self.load()
        assert self._daily is not None
        return self._daily

    @property
    def checkpoints(self) -> pd.DataFrame:
        if self._checkpoints is None:
            self.load()
        assert self._checkpoints is not None
        return self._checkpoints

    def _compute_base_rates(self) -> None:
        d = self.daily
        self._base_rates = {
            "pct_50_before_opposite": float(d["label_50_before_opposite"].astype(float).mean()),
            "pct_100_before_opposite": float(d["label_100_before_opposite"].astype(float).mean()),
            "pct_opposite_break": float(d["label_opposite_break"].astype(float).mean()),
            "pct_trend_day": float(d["label_trend_day"].astype(float).mean()),
            "pct_gap_fill": float(d["label_gap_fill"].astype(float).mean()),
            "median_ib_range": float(d["ib_range"].median()),
        }

    def view_for_date(
        self,
        date_value: Any,
        *,
        cadence: str | None = None,
        minute: int | None = None,
        layer: str | None = None,
    ) -> list[SessionView]:
        date_ts = pd.Timestamp(date_value).date()
        daily_row = self.daily[pd.to_datetime(self.daily["date"]).dt.date == date_ts]
        ib_bucket = daily_row.iloc[0]["ib_bucket"] if not daily_row.empty else None
        daily_series = daily_row.iloc[0] if not daily_row.empty else None

        views: list[SessionView] = []
        for cp in CHECKPOINTS:
            if minute is not None and cp.minutes_from_open != minute:
                continue
            if cadence is not None and cp.cadence != cadence:
                continue

            maturity = view_maturity(cp.minutes_from_open)
            if layer is not None and maturity != layer:
                continue

            cp_frame = self.checkpoints[
                (pd.to_datetime(self.checkpoints["date"]).dt.date == date_ts)
                & (self.checkpoints["checkpoint_minute"] == cp.minutes_from_open)
            ]
            if cp_frame.empty or not bool(cp_frame.iloc[0].get("is_valid_checkpoint", False)):
                continue

            row = cp_frame.iloc[0]
            cadence_label = str(row.get("checkpoint_cadence") or cp.cadence)

            if maturity == "QUICK":
                views.append(self._quick_view(date_ts, row, ib_bucket, cadence_label))
            elif maturity == "CONFIRMED":
                views.append(self._confirmed_view(date_ts, row, ib_bucket, cadence_label))
            else:
                views.append(self._conviction_view(date_ts, row, daily_series, cadence_label))

        return views

    def _quick_view(
        self,
        date_value: Any,
        row: pd.Series,
        ib_bucket: Any,
        cadence: str,
    ) -> SessionView:
        opening = row.get("opening_direction", "UNKNOWN")
        speed = float(row.get("range_speed_points_per_min") or 0)
        efficiency = float(row.get("directional_efficiency") or 0)

        if opening == "UP" and speed > 3:
            bias = "BULLISH"
        elif opening == "DOWN" and speed > 3:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        trend_p = self._adjust_rate(
            self._base_rates["pct_trend_day"],
            speed_factor=min(speed / 5, 2),
            ib_bucket=ib_bucket,
        )
        opp_p = self._adjust_rate(
            self._base_rates["pct_opposite_break"],
            speed_factor=1.0 if efficiency > 0.5 else 1.2,
            ib_bucket=ib_bucket,
            invert_narrow=True,
        )

        return SessionView(
            date=date_value,
            layer="QUICK",
            checkpoint_minute=int(row["checkpoint_minute"]),
            checkpoint_clock=str(row.get("checkpoint_clock", "")),
            cadence=cadence,
            bias=bias,
            trend_probability=round(trend_p, 3),
            opposite_break_probability=round(opp_p, 3),
            trap_probability=round(min(opp_p * 1.1, 0.95), 3),
            expected_excursion_50=50.0,
            expected_excursion_100=100.0,
            day_type=None,
            signals={
                "opening_direction": opening,
                "range_speed": speed,
                "directional_efficiency": efficiency,
                "gap_direction": row.get("gap_direction"),
            },
        )

    def _confirmed_view(
        self,
        date_value: Any,
        row: pd.Series,
        ib_bucket: Any,
        cadence: str,
    ) -> SessionView:
        opening = row.get("opening_direction", "UNKNOWN")
        tests_high = int(row.get("tests_of_prev_high") or 0)
        tests_low = int(row.get("tests_of_prev_low") or 0)
        gap_filled = bool(row.get("gap_filled_by_checkpoint", False))
        efficiency = float(row.get("directional_efficiency") or 0)

        if efficiency > 0.6 and opening in {"UP", "DOWN"}:
            day_type = "POTENTIAL_TREND"
            bias = "BULLISH" if opening == "UP" else "BEARISH"
        elif tests_high >= 2 and tests_low >= 2:
            day_type = "POTENTIAL_ROTATION"
            bias = "NEUTRAL"
        elif gap_filled and efficiency < 0.4:
            day_type = "POTENTIAL_TRAP"
            bias = "NEUTRAL"
        else:
            day_type = "UNDECIDED"
            bias = "NEUTRAL"

        trend_p = self._adjust_rate(self._base_rates["pct_trend_day"], ib_bucket=ib_bucket)
        opp_p = self._adjust_rate(
            self._base_rates["pct_opposite_break"],
            ib_bucket=ib_bucket,
            invert_narrow=True,
        )

        return SessionView(
            date=date_value,
            layer="CONFIRMED",
            checkpoint_minute=int(row["checkpoint_minute"]),
            checkpoint_clock=str(row.get("checkpoint_clock", "")),
            cadence=cadence,
            bias=bias,
            trend_probability=round(trend_p, 3),
            opposite_break_probability=round(opp_p, 3),
            trap_probability=round(opp_p * 1.15 if day_type == "POTENTIAL_TRAP" else opp_p, 3),
            expected_excursion_50=50.0,
            expected_excursion_100=100.0,
            day_type=day_type,
            signals={
                "tests_of_prev_high": tests_high,
                "tests_of_prev_low": tests_low,
                "gap_filled_by_checkpoint": gap_filled,
                "opening_pressure": row.get("opening_pressure"),
            },
        )

    def _conviction_view(
        self,
        date_value: Any,
        row: pd.Series,
        daily_row: pd.Series | None,
        cadence: str,
    ) -> SessionView:
        opening = row.get("opening_direction", "UNKNOWN")
        speed = float(row.get("range_speed_points_per_min") or 0)
        efficiency = float(row.get("directional_efficiency") or 0)

        if daily_row is not None and bool(daily_row.get("label_trend_day")):
            day_type = "TREND_DAY"
        elif speed > 4 and efficiency > 0.55:
            day_type = "TREND_DAY"
        elif row.get("tests_of_prev_high", 0) and row.get("tests_of_prev_low", 0):
            day_type = "ROTATIONAL_DAY"
        elif efficiency < 0.35 and bool(row.get("gap_filled_by_checkpoint")):
            day_type = "FAILED_BREAKOUT_DAY"
        else:
            day_type = "MIXED"

        bias = "BULLISH" if opening == "UP" else "BEARISH" if opening == "DOWN" else "NEUTRAL"

        return SessionView(
            date=date_value,
            layer="CONVICTION",
            checkpoint_minute=int(row["checkpoint_minute"]),
            checkpoint_clock=str(row.get("checkpoint_clock", "")),
            cadence=cadence,
            bias=bias,
            trend_probability=round(self._base_rates["pct_trend_day"], 3),
            opposite_break_probability=round(self._base_rates["pct_opposite_break"], 3),
            trap_probability=round(self._base_rates["pct_opposite_break"] * 1.1, 3),
            expected_excursion_50=50.0,
            expected_excursion_100=100.0,
            day_type=day_type,
            signals={
                "range_so_far": row.get("range_so_far"),
                "range_speed": speed,
                "directional_efficiency": efficiency,
            },
        )

    def _adjust_rate(
        self,
        base: float,
        *,
        speed_factor: float = 1.0,
        ib_bucket: Any = None,
        invert_narrow: bool = False,
    ) -> float:
        rate = base * speed_factor
        if ib_bucket == "WIDE":
            rate *= 0.9 if invert_narrow else 1.05
        elif ib_bucket == "NARROW" and invert_narrow:
            rate *= 1.15
        return float(np.clip(rate, 0.05, 0.95))


def format_session_telegram(
    date_value: str,
    *,
    feature_dir: Path = DEFAULT_FEATURE_DIR,
    layers: tuple[str, ...] = ("QUICK", "CONFIRMED", "CONVICTION"),
) -> str:
    """Compact Telegram summary — one anchor view per maturity band."""
    engine = ViewEngine(feature_dir)
    views = engine.view_for_date(date_value)
    if not views:
        return f"No views for {date_value} (features may still be rebuilding)."

    picked: dict[str, SessionView] = {}
    for view in views:
        if view.layer not in layers:
            continue
        if view.layer not in picked or view.checkpoint_minute > picked[view.layer].checkpoint_minute:
            picked[view.layer] = view

    lines = [f"📈 Session view — {date_value}"]
    for layer in layers:
        view = picked.get(layer)
        if not view:
            continue
        extra = f" | {view.day_type}" if view.day_type else ""
        lines.append(
            f"{layer} @ {view.checkpoint_clock} ({view.cadence})\n"
            f"  {view.bias}{extra} | trend {view.trend_probability:.0%} | "
            f"opp break {view.opposite_break_probability:.0%}"
        )
    return "\n".join(lines)


def latest_view_date(feature_dir: Path = DEFAULT_FEATURE_DIR) -> str | None:
    daily_path = feature_dir / "daily_features.csv"
    if not daily_path.exists():
        return None
    df = pd.read_csv(daily_path, parse_dates=["date"])
    if df.empty:
        return None
    return pd.Timestamp(df["date"].max()).strftime("%Y-%m-%d")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate session views from checkpoint features.")
    parser.add_argument("--feature-dir", type=Path, default=DEFAULT_FEATURE_DIR)
    parser.add_argument("--date", type=str, required=True, help="Session date YYYY-MM-DD")
    parser.add_argument(
        "--cadence",
        choices=["3MIN", "5MIN", "3MIN+5MIN"],
        help="Filter to one cadence (default: all checkpoints)",
    )
    parser.add_argument("--minute", type=int, help="Filter to one checkpoint minute from open")
    parser.add_argument(
        "--layer",
        choices=["QUICK", "CONFIRMED", "CONVICTION"],
        help="Filter to one maturity band",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = ViewEngine(args.feature_dir)
    views = engine.view_for_date(
        args.date,
        cadence=args.cadence,
        minute=args.minute,
        layer=args.layer,
    )

    print(f"\nSession views for {args.date}")
    print("=" * 60)
    for view in views:
        print(
            f"\n{view.layer} | {view.checkpoint_clock} (+{view.checkpoint_minute}m) | {view.cadence}"
        )
        print(f"  Bias              : {view.bias}")
        print(f"  Trend probability : {view.trend_probability:.1%}")
        print(f"  Opposite break    : {view.opposite_break_probability:.1%}")
        print(f"  Trap probability  : {view.trap_probability:.1%}")
        if view.day_type:
            print(f"  Day type          : {view.day_type}")
        print(f"  Signals           : {view.signals}")


if __name__ == "__main__":
    main()
