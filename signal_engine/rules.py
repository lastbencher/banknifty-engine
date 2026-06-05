from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from signal_engine.models import SignalRule

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = PROJECT_ROOT / "config" / "signal_rules.json"
DEFAULT_RANKED_CSV = (
    PROJECT_ROOT / "research" / "outputs" / "phase2b_signal_validation" / "ranked_fast_move_signals.csv"
)


def parse_rule_string(rule: str) -> dict[str, str]:
    conditions: dict[str, str] = {}
    for part in rule.split(" & "):
        feature, value = part.split("=", 1)
        conditions[feature.strip()] = value.strip()
    return conditions


def rule_from_row(row: pd.Series) -> SignalRule:
    rule_text = str(row["rule"])
    return SignalRule(
        rule_id=str(row["rule_id"]),
        checkpoint_minute=int(row["checkpoint_minute"]),
        rule=rule_text,
        conditions=parse_rule_string(rule_text),
        pct_50_before_opposite=float(row["pct_50_before_opposite"]),
        pct_100_before_opposite=float(row["pct_100_before_opposite"]),
        pct_opposite_break=float(row["pct_opposite_break"]),
        edge_score=float(row["edge_score"]),
        median_minutes_to_50=_optional_float(row.get("median_minutes_to_50")),
        median_minutes_to_100=_optional_float(row.get("median_minutes_to_100")),
        sessions=int(row.get("sessions", 0)),
    )


def _optional_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    return float(value)


def load_rules_from_csv(
    path: Path = DEFAULT_RANKED_CSV,
    *,
    top_n: int = 15,
    min_sessions: int = 60,
    max_opposite_break_pct: float = 18.0,
) -> list[SignalRule]:
    frame = pd.read_csv(path)
    filtered = frame[
        (frame["sessions"] >= min_sessions)
        & (frame["pct_opposite_break"] <= max_opposite_break_pct)
    ]
    return [rule_from_row(row) for _, row in filtered.head(top_n).iterrows()]


def load_rules(path: Path | None = None) -> list[SignalRule]:
    rules_path = path or DEFAULT_RULES_PATH

    if rules_path.suffix == ".json":
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        return [
            SignalRule(
                rule_id=item["rule_id"],
                checkpoint_minute=int(item["checkpoint_minute"]),
                rule=item["rule"],
                conditions=parse_rule_string(item["rule"]),
                pct_50_before_opposite=float(item["pct_50_before_opposite"]),
                pct_100_before_opposite=float(item["pct_100_before_opposite"]),
                pct_opposite_break=float(item["pct_opposite_break"]),
                edge_score=float(item["edge_score"]),
                median_minutes_to_50=item.get("median_minutes_to_50"),
                median_minutes_to_100=item.get("median_minutes_to_100"),
                sessions=int(item.get("sessions", 0)),
            )
            for item in payload["rules"]
        ]

    return load_rules_from_csv(rules_path)
