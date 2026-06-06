"""Platform configuration — clock checkpoints and research constants."""

from __future__ import annotations

from dataclasses import dataclass

IB_DURATION_MINUTES = 60
POINT_THRESHOLDS = (50, 100)
ABSORPTION_MIN_TESTS = 3
COMPLETE_SESSION_FRACTION = 0.80

SESSION_OPEN_HOUR = 9
SESSION_OPEN_MINUTE = 15


@dataclass(frozen=True)
class CheckpointDef:
    minutes_from_open: int
    clock_label: str
    view_layer: str | None
    cadence: str  # "3MIN" | "5MIN"


def clock_label(minutes_from_open: int) -> str:
    total = SESSION_OPEN_HOUR * 60 + SESSION_OPEN_MINUTE + minutes_from_open
    return f"{total // 60:02d}:{total % 60:02d}"


THREE_MIN_CHECKPOINTS: tuple[int, ...] = tuple(range(3, 31, 3))
FIVE_MIN_CHECKPOINTS: tuple[int, ...] = tuple(range(5, 31, 5))
ALL_CHECKPOINT_MINUTES: tuple[int, ...] = tuple(
    sorted(set(THREE_MIN_CHECKPOINTS) | set(FIVE_MIN_CHECKPOINTS))
)

VIEW_LAYERS: dict[str, int] = {
    "QUICK": 5,
    "CONFIRMED": 15,
    "CONVICTION": 30,
}

# Maturity bands for every checkpoint on the 3-min + 5-min grid.
VIEW_MATURITY_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (15, "QUICK"),
    (30, "CONFIRMED"),
    (999, "CONVICTION"),
)


def view_maturity(minute: int) -> str:
    for upper, label in VIEW_MATURITY_THRESHOLDS:
        if minute < upper:
            return label
    return "CONVICTION"


def _view_layer(minute: int) -> str | None:
    return view_maturity(minute)


def _cadence(minute: int) -> str:
    on_three = minute in THREE_MIN_CHECKPOINTS
    on_five = minute in FIVE_MIN_CHECKPOINTS
    if on_three and on_five:
        return "3MIN+5MIN"
    if on_three:
        return "3MIN"
    return "5MIN"


CHECKPOINTS: tuple[CheckpointDef, ...] = tuple(
    CheckpointDef(
        minutes_from_open=minute,
        clock_label=clock_label(minute),
        view_layer=_view_layer(minute),
        cadence=_cadence(minute),
    )
    for minute in ALL_CHECKPOINT_MINUTES
)

# Signal rule transfer: 5-min research rules also fire at 15 and 30 min.
FIVE_MIN_TRANSFER_TARGETS: tuple[int, ...] = (15, 30)
