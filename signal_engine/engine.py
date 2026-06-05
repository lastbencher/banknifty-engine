from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from signal_engine.features import prepare_checkpoint_frame, row_matches_conditions
from signal_engine.models import SignalRule, TradeSignal
from signal_engine.rules import load_rules

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURE_DIR = PROJECT_ROOT / "features"
TARGET_POINTS = (50, 100)


class SignalEngine:
    def __init__(
        self,
        rules: list[SignalRule] | None = None,
        *,
        feature_dir: Path = DEFAULT_FEATURE_DIR,
        rules_path: Path | None = None,
    ) -> None:
        self.rules = rules if rules is not None else load_rules(rules_path)
        self.feature_dir = feature_dir
        self._daily: pd.DataFrame | None = None
        self._checkpoints: pd.DataFrame | None = None
        self._prepared: pd.DataFrame | None = None

    def load_features(self) -> None:
        self._daily = pd.read_csv(
            self.feature_dir / "daily_features.csv",
            parse_dates=["date", "first_break_time", "opposite_break_time"],
        )
        self._checkpoints = pd.read_csv(
            self.feature_dir / "checkpoint_features.csv",
            parse_dates=["date", "checkpoint_time"],
        )
        self._prepared = prepare_checkpoint_frame(self._daily, self._checkpoints)

    @property
    def prepared(self) -> pd.DataFrame:
        if self._prepared is None:
            self.load_features()
        assert self._prepared is not None
        return self._prepared

    def rules_for_minute(self, checkpoint_minute: int) -> list[SignalRule]:
        return [rule for rule in self.rules if rule.checkpoint_minute == checkpoint_minute]

    def evaluate_row(self, row: pd.Series, rule: SignalRule) -> TradeSignal | None:
        if int(row["checkpoint_minute"]) != rule.checkpoint_minute:
            return None
        if not row_matches_conditions(row, rule.conditions):
            return None
        return self._build_signal(row, rule)

    def evaluate_checkpoint(
        self,
        row: pd.Series,
        *,
        best_only: bool = True,
    ) -> list[TradeSignal]:
        minute = int(row["checkpoint_minute"])
        matches: list[TradeSignal] = []

        for rule in self.rules_for_minute(minute):
            signal = self.evaluate_row(row, rule)
            if signal is not None:
                matches.append(signal)

        if not matches:
            return []

        matches.sort(key=lambda s: s.confidence, reverse=True)
        return [matches[0]] if best_only else matches

    def scan_history(
        self,
        *,
        start_date: Any | None = None,
        end_date: Any | None = None,
        best_only: bool = True,
    ) -> list[TradeSignal]:
        frame = self.prepared.copy()
        frame["date"] = pd.to_datetime(frame["date"])

        if start_date is not None:
            frame = frame[frame["date"] >= pd.Timestamp(start_date)]
        if end_date is not None:
            frame = frame[frame["date"] <= pd.Timestamp(end_date)]

        signals: list[TradeSignal] = []
        seen: set[tuple[Any, int]] = set()

        for _, row in frame.iterrows():
            day = row["date"]
            minute = int(row["checkpoint_minute"])
            key = (day, minute)

            if best_only and key in seen:
                continue

            matched = self.evaluate_checkpoint(row, best_only=best_only)
            if matched:
                signals.extend(matched)
                seen.add(key)

        return signals

    def _build_signal(self, row: pd.Series, rule: SignalRule) -> TradeSignal:
        side, direction = self._infer_side(row, rule)
        entry_price = float(row["checkpoint_close"])
        ib_high = _optional_float(row.get("ib_high"))
        ib_low = _optional_float(row.get("ib_low"))
        stop_price, stop_reason = self._stop_plan(side, ib_high, ib_low)

        if side == "LONG":
            target_50 = entry_price + TARGET_POINTS[0]
            target_100 = entry_price + TARGET_POINTS[1]
        else:
            target_50 = entry_price - TARGET_POINTS[0]
            target_100 = entry_price - TARGET_POINTS[1]

        confidence = self._confidence(rule)

        return TradeSignal(
            date=row["date"],
            checkpoint_minute=int(row["checkpoint_minute"]),
            checkpoint_time=row.get("checkpoint_time"),
            rule_id=rule.rule_id,
            rule=rule.rule,
            direction=direction,
            side=side,
            confidence=confidence,
            entry_price=entry_price,
            entry_trigger="FIRST_IB_BREAK",
            target_50=target_50,
            target_100=target_100,
            stop_price=stop_price,
            stop_reason=stop_reason,
            ib_high=ib_high,
            ib_low=ib_low,
            stats={
                "pct_50_before_opposite": rule.pct_50_before_opposite,
                "pct_100_before_opposite": rule.pct_100_before_opposite,
                "pct_opposite_break": rule.pct_opposite_break,
                "edge_score": rule.edge_score,
                "median_minutes_to_50": rule.median_minutes_to_50,
                "median_minutes_to_100": rule.median_minutes_to_100,
                "sessions": rule.sessions,
            },
        )

    @staticmethod
    def _infer_side(row: pd.Series, rule: SignalRule) -> tuple[str, str]:
        opening = str(row.get("opening_direction", "UNKNOWN"))

        if "opening_direction" in rule.conditions:
            opening = rule.conditions["opening_direction"]

        if opening == "UP":
            return "LONG", "UP"
        if opening == "DOWN":
            return "SHORT", "DOWN"

        if "gap_direction" in rule.conditions:
            gap = rule.conditions["gap_direction"]
            if gap == "UP":
                return "LONG", "UP"
            if gap == "DOWN":
                return "SHORT", "DOWN"

        return "FLAT", opening

    @staticmethod
    def _stop_plan(
        side: str,
        ib_high: float | None,
        ib_low: float | None,
    ) -> tuple[float | None, str]:
        if side == "LONG" and ib_low is not None:
            return ib_low, "OPPOSITE_IB_BREAK"
        if side == "SHORT" and ib_high is not None:
            return ib_high, "OPPOSITE_IB_BREAK"
        return None, "OPPOSITE_IB_BREAK"

    @staticmethod
    def _confidence(rule: SignalRule) -> float:
        hit_rate = rule.pct_100_before_opposite / 100
        trap_penalty = 1.0 - min(rule.pct_opposite_break / 100, 1.0)
        edge_factor = min(rule.edge_score / 100, 1.0)
        sample_factor = min(rule.sessions / 200, 1.0)
        return round(hit_rate * trap_penalty * (0.6 + 0.4 * edge_factor) * (0.7 + 0.3 * sample_factor), 4)


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
