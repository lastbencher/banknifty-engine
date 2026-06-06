from __future__ import annotations

from typing import Any

import pandas as pd

from bnf_research.config import POINT_THRESHOLDS
from bnf_research.ib import threshold_hit
from bnf_research.session import SessionMeta
from bnf_research.utils import minutes_between, safe_divide, to_hour
from bnf_research.wyckoff import (
    detect_absorption,
    detect_failed_breaks,
    detect_springs,
    detect_upthrusts,
)


def build_event_rows(
    meta: SessionMeta,
    daily_row: dict[str, Any],
    aux: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    day = meta.day
    session_start = meta.session_start
    ib_high = aux.get("ib_high", float("nan"))
    ib_low = aux.get("ib_low", float("nan"))
    ib_range = aux.get("ib_range", float("nan"))

    rows.extend(_gap_events(meta, daily_row, ib_range))
    rows.extend(_break_events(meta, daily_row, aux, ib_range))
    rows.extend(_wyckoff_events(meta, daily_row, ib_high, ib_low, ib_range))
    rows.extend(_point_move_events(meta, daily_row, aux, ib_range))

    for row in rows:
        row.setdefault("date", meta.date)
        row.setdefault("era", daily_row.get("era"))
        row.setdefault("gap_direction", daily_row.get("gap_direction"))
        row.setdefault("ib_range", ib_range)

    return rows


def _gap_events(meta: SessionMeta, daily_row: dict[str, Any], ib_range: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if daily_row.get("gap_direction") not in {"UP", "DOWN"}:
        return rows

    rows.append(
        _event(
            event_type="GAP",
            event_subtype="GAP_OPEN",
            event_direction=daily_row["gap_direction"],
            event_time=meta.session_start,
            event_pos=0,
            anchor_type="PREV_CLOSE",
            anchor_price=daily_row["prev_close"],
            event_price=daily_row["day_open"],
            move_points=abs(daily_row["gap_points"]),
            ib_range=ib_range,
            daily_row=daily_row,
        )
    )

    if daily_row.get("gap_filled"):
        fill_time = daily_row["gap_fill_time"]
        fill_pos = int(meta.day.index[meta.day["datetime"] == fill_time][0])
        rows.append(
            _event(
                event_type="GAP",
                event_subtype="GAP_FILL",
                event_direction="DOWN" if daily_row["gap_direction"] == "UP" else "UP",
                event_time=fill_time,
                event_pos=fill_pos,
                anchor_type="SESSION_OPEN",
                anchor_price=daily_row["day_open"],
                event_price=daily_row["prev_close"],
                move_points=abs(daily_row["gap_points"]),
                ib_range=ib_range,
                daily_row=daily_row,
            )
        )
    elif daily_row.get("gap_sustain_until_close"):
        rows.append(
            _event(
                event_type="GAP",
                event_subtype="GAP_AND_GO",
                event_direction=daily_row["gap_direction"],
                event_time=meta.session_end,
                event_pos=len(meta.day) - 1,
                anchor_type="SESSION_OPEN",
                anchor_price=daily_row["day_open"],
                event_price=daily_row["day_close"],
                move_points=abs(daily_row["day_close"] - daily_row["prev_close"]),
                ib_range=ib_range,
                daily_row=daily_row,
            )
        )

    return rows


def _break_events(
    meta: SessionMeta,
    daily_row: dict[str, Any],
    aux: dict[str, Any],
    ib_range: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first = aux.get("first_break", {})
    opposite = aux.get("opposite", {})

    if first.get("pos") is not None:
        rows.append(
            _event(
                event_type="FIRST_BREAK",
                event_subtype="IB_FIRST_BREAK",
                event_direction=first["direction"],
                event_time=first["time"],
                event_pos=first["pos"],
                anchor_type="IB_END",
                anchor_price=aux.get("ib_mid"),
                trigger_level=first["level"],
                event_price=first["price"],
                move_points=abs(first["price"] - first["level"]),
                ib_range=ib_range,
                daily_row=daily_row,
            )
        )

    if opposite.get("occurred"):
        rows.append(
            _event(
                event_type="OPPOSITE_BREAK",
                event_subtype="IB_OPPOSITE_BREAK",
                event_direction="LOW" if first["direction"] == "HIGH" else "HIGH",
                event_time=opposite["time"],
                event_pos=opposite["pos"],
                anchor_type="FIRST_BREAK",
                anchor_price=first["level"],
                trigger_level=opposite["level"],
                event_price=opposite["price"],
                move_points=abs(opposite["price"] - opposite["level"]),
                ib_range=ib_range,
                daily_row=daily_row,
            )
        )

    return rows


def _wyckoff_events(
    meta: SessionMeta,
    daily_row: dict[str, Any],
    ib_high: float,
    ib_low: float,
    ib_range: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for spring in detect_springs(meta, ib_high, ib_low):
        rows.append(
            _event(
                event_type="WYCKOFF",
                event_subtype="SPRING",
                event_direction="LOW",
                event_time=spring["confirm_time"],
                event_pos=spring["confirm_pos"],
                anchor_type="IB_LOW",
                anchor_price=ib_low,
                trigger_level=spring["level"],
                event_price=spring["confirm_price"],
                move_points=spring["break_price"] - ib_low if not pd.isna(spring["break_price"]) else None,
                ib_range=ib_range,
                daily_row=daily_row,
                context={"test_count": 1, "duration_minutes": spring["duration_minutes"]},
            )
        )

    for upthrust in detect_upthrusts(meta, ib_high, ib_low):
        rows.append(
            _event(
                event_type="WYCKOFF",
                event_subtype="UPTHRUST",
                event_direction="HIGH",
                event_time=upthrust["confirm_time"],
                event_pos=upthrust["confirm_pos"],
                anchor_type="IB_HIGH",
                anchor_price=ib_high,
                trigger_level=upthrust["level"],
                event_price=upthrust["confirm_price"],
                move_points=upthrust["break_price"] - ib_high if not pd.isna(upthrust["break_price"]) else None,
                ib_range=ib_range,
                daily_row=daily_row,
                context={"duration_minutes": upthrust["duration_minutes"]},
            )
        )

    for absorption in detect_absorption(meta, ib_high, ib_low):
        rows.append(
            _event(
                event_type="WYCKOFF",
                event_subtype=absorption["event_subtype"],
                event_direction=absorption["event_direction"],
                event_time=absorption["confirm_time"],
                event_pos=absorption["confirm_pos"],
                anchor_type="IB",
                anchor_price=absorption["level"],
                trigger_level=absorption["level"],
                event_price=absorption["confirm_price"],
                ib_range=ib_range,
                daily_row=daily_row,
                context={"test_count": absorption["test_count"]},
            )
        )

    for failed in detect_failed_breaks(meta, ib_high, ib_low):
        rows.append(
            _event(
                event_type="TRAP",
                event_subtype=failed["event_subtype"],
                event_direction=failed["event_direction"],
                event_time=failed["confirm_time"],
                event_pos=failed["confirm_pos"],
                anchor_type="IB",
                anchor_price=failed["level"],
                trigger_level=failed["level"],
                event_price=failed["confirm_price"],
                move_points=failed.get("max_extension"),
                ib_range=ib_range,
                daily_row=daily_row,
                context={"duration_minutes": failed.get("duration_minutes")},
            )
        )

    return rows


def _point_move_events(
    meta: SessionMeta,
    daily_row: dict[str, Any],
    aux: dict[str, Any],
    ib_range: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    day = meta.day
    first = aux.get("first_break", {})

    for threshold in POINT_THRESHOLDS:
        for direction in ("HIGH", "LOW"):
            open_hit = threshold_hit(day, 0, daily_row["day_open"], direction, threshold)
            if open_hit["hit"]:
                rows.append(
                    _event(
                        event_type="POINT_MOVE",
                        event_subtype=f"FIRST_{threshold}_MOVE_FROM_OPEN",
                        event_direction=direction,
                        event_time=open_hit["time"],
                        event_pos=open_hit["pos"],
                        anchor_type="SESSION_OPEN",
                        anchor_price=daily_row["day_open"],
                        trigger_level=daily_row["day_open"] + threshold
                        if direction == "HIGH"
                        else daily_row["day_open"] - threshold,
                        event_price=open_hit["price"],
                        threshold_points=threshold,
                        move_points=open_hit["move_points"],
                        ib_range=ib_range,
                        daily_row=daily_row,
                    )
                )

        if first.get("pos") is not None:
            break_hit = threshold_hit(day, first["pos"], first["level"], first["direction"], threshold)
            if break_hit["hit"]:
                rows.append(
                    _event(
                        event_type="POINT_MOVE",
                        event_subtype=f"FIRST_{threshold}_MOVE",
                        event_direction=first["direction"],
                        event_time=break_hit["time"],
                        event_pos=break_hit["pos"],
                        anchor_type="FIRST_BREAK",
                        anchor_price=first["level"],
                        trigger_level=first["level"] + threshold
                        if first["direction"] == "HIGH"
                        else first["level"] - threshold,
                        event_price=break_hit["price"],
                        threshold_points=threshold,
                        move_points=break_hit["move_points"],
                        ib_range=ib_range,
                        daily_row=daily_row,
                    )
                )

    return rows


def _event(
    *,
    event_type: str,
    event_subtype: str,
    event_direction: str | None,
    event_time: Any,
    event_pos: int,
    anchor_type: str,
    anchor_price: float,
    event_price: float,
    ib_range: float,
    daily_row: dict[str, Any],
    trigger_level: float | None = None,
    threshold_points: float | None = None,
    move_points: float | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "event_type": event_type,
        "event_subtype": event_subtype,
        "event_direction": event_direction,
        "event_time": event_time,
        "event_hour": to_hour(event_time),
        "event_pos": event_pos,
        "anchor_type": anchor_type,
        "anchor_price": anchor_price,
        "trigger_level": trigger_level,
        "event_price": event_price,
        "threshold_points": threshold_points,
        "move_points": move_points,
        "move_pct": safe_divide(move_points or 0, anchor_price) * 100 if anchor_price else None,
        "ib_range": ib_range,
        "first_break_direction": daily_row.get("first_break_direction"),
        "gap_direction": daily_row.get("gap_direction"),
        "era": daily_row.get("era"),
    }
    if context:
        row.update(context)
    return row


def assign_event_ids(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events

    events = events.sort_values(["date", "event_time", "event_type", "event_subtype"]).reset_index(drop=True)
    events["event_id"] = events.groupby("date").cumcount().add(1).astype(str).str.zfill(3)
    events["event_id"] = events["date"].astype(str) + "_" + events["event_id"]
    return events[["event_id", *[c for c in events.columns if c != "event_id"]]]
