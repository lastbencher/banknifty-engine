from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from bnf_research.config import (
    FIVE_MIN_CHECKPOINTS,
    FIVE_MIN_TRANSFER_TARGETS,
    THREE_MIN_CHECKPOINTS,
    clock_label,
)
from signal_engine.models import SignalRule

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = PROJECT_ROOT / "config" / "signal_rules.json"
DEFAULT_RANKED_CSV = (
    PROJECT_ROOT / "research" / "outputs" / "phase2b_signal_validation" / "ranked_fast_move_signals.csv"
)


def stable_rule_id(checkpoint_minute: int, rule: str) -> str:
    payload = f"{checkpoint_minute}|{rule}"
    return hashlib.md5(payload.encode()).hexdigest()[:12]


def parse_rule_string(rule: str) -> dict[str, str]:
    conditions: dict[str, str] = {}
    for part in rule.split(" & "):
        feature, value = part.split("=", 1)
        conditions[feature.strip()] = value.strip()
    return conditions


def rule_timeframe(source_checkpoint: int) -> str:
    if source_checkpoint in THREE_MIN_CHECKPOINTS and source_checkpoint not in FIVE_MIN_CHECKPOINTS:
        return "3MIN"
    if source_checkpoint in FIVE_MIN_CHECKPOINTS:
        return "5MIN"
    if source_checkpoint in THREE_MIN_CHECKPOINTS:
        return "3MIN+5MIN"
    return "5MIN"


def transfer_checkpoints(source_checkpoint: int) -> list[int]:
    """
    Remap research checkpoints to live evaluation times.

    3-min rules  → every 3-min slot (09:18, 09:21, 09:24 … 09:45)
    5-min rules  → source minute + 15 min + 30 min (09:20→09:30→09:45)
    """
    if source_checkpoint == 3:
        return list(THREE_MIN_CHECKPOINTS)

    if source_checkpoint in THREE_MIN_CHECKPOINTS and source_checkpoint not in FIVE_MIN_CHECKPOINTS:
        return [source_checkpoint]

    if source_checkpoint == 30:
        return [30]

    if source_checkpoint == 15:
        return [15, 30]

    if source_checkpoint in FIVE_MIN_CHECKPOINTS:
        return sorted({source_checkpoint, *FIVE_MIN_TRANSFER_TARGETS})

    return [source_checkpoint]


def expand_rule(rule: SignalRule) -> list[SignalRule]:
    targets = transfer_checkpoints(rule.source_checkpoint_minute or rule.checkpoint_minute)
    expanded: list[SignalRule] = []

    for minute in targets:
        suffix = "" if minute == rule.checkpoint_minute else f"@{minute}m"
        expanded.append(
            replace(
                rule,
                rule_id=f"{rule.source_rule_id or rule.rule_id}{suffix}",
                checkpoint_minute=minute,
                checkpoint_clock=clock_label(minute),
                stable_id=stable_rule_id(minute, rule.rule),
            )
        )

    return expanded


def rule_from_dict(item: dict) -> SignalRule:
    checkpoint = int(item["checkpoint_minute"])
    rule_text = item["rule"]
    source = int(item.get("source_checkpoint_minute", checkpoint))
    return SignalRule(
        rule_id=str(item["rule_id"]),
        source_rule_id=str(item.get("source_rule_id", item["rule_id"])),
        source_checkpoint_minute=source,
        checkpoint_minute=checkpoint,
        checkpoint_clock=item.get("checkpoint_clock") or clock_label(checkpoint),
        timeframe=item.get("timeframe") or rule_timeframe(source),
        rule=rule_text,
        conditions=parse_rule_string(rule_text),
        pct_50_before_opposite=float(item["pct_50_before_opposite"]),
        pct_100_before_opposite=float(item["pct_100_before_opposite"]),
        pct_opposite_break=float(item["pct_opposite_break"]),
        edge_score=float(item["edge_score"]),
        stable_id=item.get("stable_id") or stable_rule_id(checkpoint, rule_text),
        median_minutes_to_50=_optional_float(item.get("median_minutes_to_50")),
        median_minutes_to_100=_optional_float(item.get("median_minutes_to_100")),
        sessions=int(item.get("sessions", 0)),
    )


def rule_from_row(row: pd.Series) -> SignalRule:
    rule_text = str(row["rule"])
    checkpoint = int(row["checkpoint_minute"])
    return SignalRule(
        rule_id=str(row["rule_id"]),
        source_rule_id=str(row["rule_id"]),
        source_checkpoint_minute=checkpoint,
        checkpoint_minute=checkpoint,
        checkpoint_clock=clock_label(checkpoint),
        timeframe=rule_timeframe(checkpoint),
        rule=rule_text,
        conditions=parse_rule_string(rule_text),
        pct_50_before_opposite=float(row["pct_50_before_opposite"]),
        pct_100_before_opposite=float(row["pct_100_before_opposite"]),
        pct_opposite_break=float(row["pct_opposite_break"]),
        edge_score=float(row["edge_score"]),
        stable_id=stable_rule_id(checkpoint, rule_text),
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
    expand: bool = True,
) -> list[SignalRule]:
    frame = pd.read_csv(path)
    filtered = frame[
        (frame["sessions"] >= min_sessions)
        & (frame["pct_opposite_break"] <= max_opposite_break_pct)
    ]
    base = [rule_from_row(row) for _, row in filtered.head(top_n).iterrows()]
    return _expand_all(base) if expand else base


def _expand_all(base_rules: list[SignalRule]) -> list[SignalRule]:
    expanded: list[SignalRule] = []
    seen: set[tuple[int, str]] = set()

    for rule in base_rules:
        for candidate in expand_rule(rule):
            key = (candidate.checkpoint_minute, candidate.rule)
            if key in seen:
                continue
            seen.add(key)
            expanded.append(candidate)

    return expanded


def load_rules(path: Path | None = None, *, expand: bool = True) -> list[SignalRule]:
    rules_path = path or DEFAULT_RULES_PATH

    if rules_path.suffix == ".json":
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        base = [rule_from_dict(item) for item in payload["rules"]]
        return _expand_all(base) if expand else base

    return load_rules_from_csv(rules_path, expand=expand)
