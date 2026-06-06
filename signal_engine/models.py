from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SignalRule:
    rule_id: str
    checkpoint_minute: int
    rule: str
    conditions: dict[str, str]
    pct_50_before_opposite: float
    pct_100_before_opposite: float
    pct_opposite_break: float
    edge_score: float
    stable_id: str = ""
    source_rule_id: str = ""
    source_checkpoint_minute: int = 0
    checkpoint_clock: str = ""
    timeframe: str = ""
    median_minutes_to_50: float | None = None
    median_minutes_to_100: float | None = None
    sessions: int = 0


@dataclass(frozen=True)
class TradeSignal:
    date: Any
    checkpoint_minute: int
    checkpoint_time: Any
    rule_id: str
    rule: str
    direction: str
    side: str
    confidence: float
    entry_price: float
    entry_trigger: str
    required_break_direction: str
    target_50: float
    target_100: float
    stop_price: float | None
    stop_reason: str
    ib_high: float | None
    ib_low: float | None
    stable_id: str = ""
    checkpoint_clock: str = ""
    source_rule_id: str = ""
    timeframe: str = ""
    stats: dict[str, float | int | None | str] = field(default_factory=dict)
