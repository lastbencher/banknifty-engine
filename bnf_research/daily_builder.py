from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from bnf_research.ib import (
    favorable_excursion,
    find_first_break,
    find_opposite_break,
    ib_levels,
    post_break_acceptance,
    threshold_hit,
)
from bnf_research.session import SessionMeta
from bnf_research.utils import (
    classify_era,
    close_location,
    era_flags,
    extension_type,
    minutes_between,
    safe_divide,
    to_hour,
)


def gap_features(day: pd.DataFrame, prev: dict[str, Any] | None) -> dict[str, Any]:
    day_open = day.iloc[0]["open"]

    if prev is None:
        return {
            "prev_date": None,
            "prev_high": np.nan,
            "prev_low": np.nan,
            "prev_close": np.nan,
            "prev_day_range": np.nan,
            "gap_points": np.nan,
            "gap_pct": np.nan,
            "gap_direction": None,
            "gap_type": None,
            "opened_above_prev_high": None,
            "opened_below_prev_low": None,
            "opened_inside_prev_range": None,
            "gap_filled": None,
            "gap_fill_time": pd.NaT,
            "minutes_to_gap_fill": np.nan,
            "gap_sustain_until_close": None,
        }

    prev_close = prev["day_close"]
    gap_points = day_open - prev_close

    if gap_points > 0:
        gap_direction = "UP"
        gap_type = "GAP_UP"
        fill_mask = day["low"] <= prev_close
        sustain = (not fill_mask.any()) and day.iloc[-1]["close"] > prev_close
    elif gap_points < 0:
        gap_direction = "DOWN"
        gap_type = "GAP_DOWN"
        fill_mask = day["high"] >= prev_close
        sustain = (not fill_mask.any()) and day.iloc[-1]["close"] < prev_close
    else:
        gap_direction = "FLAT"
        gap_type = "FLAT"
        fill_mask = pd.Series(False, index=day.index)
        sustain = False

    if fill_mask.any():
        fill_pos = fill_mask[fill_mask].index[0]
        fill_time = day.loc[fill_pos, "datetime"]
        minutes_to_fill = minutes_between(day.iloc[0]["datetime"], fill_time)
        gap_filled = True
    else:
        fill_time = pd.NaT
        minutes_to_fill = np.nan
        gap_filled = False

    return {
        "prev_date": prev["date"],
        "prev_high": prev["day_high"],
        "prev_low": prev["day_low"],
        "prev_close": prev_close,
        "prev_day_range": prev["day_range"],
        "gap_points": gap_points,
        "gap_pct": safe_divide(gap_points, prev_close) * 100,
        "gap_direction": gap_direction,
        "gap_type": gap_type,
        "opened_above_prev_high": bool(day_open > prev["day_high"]),
        "opened_below_prev_low": bool(day_open < prev["day_low"]),
        "opened_inside_prev_range": bool(prev["day_low"] <= day_open <= prev["day_high"]),
        "gap_filled": gap_filled,
        "gap_fill_time": fill_time,
        "minutes_to_gap_fill": minutes_to_fill,
        "gap_sustain_until_close": bool(sustain),
    }


def build_daily_row(
    meta: SessionMeta,
    prev: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    day = meta.day
    first = day.iloc[0]
    last = day.iloc[-1]
    era = classify_era(meta.date)

    day_open = first["open"]
    day_high = day["high"].max()
    day_low = day["low"].min()
    day_close = last["close"]
    day_range = day_high - day_low
    day_body = day_close - day_open

    row: dict[str, Any] = {
        "date": meta.date,
        "era": era,
        **era_flags(era),
        "bars_count": meta.bars_count,
        "session_start": meta.session_start,
        "session_end": meta.session_end,
        "median_session_bars": meta.median_session_bars,
        "is_complete_session": meta.is_complete_session,
        "day_open": day_open,
        "day_high": day_high,
        "day_low": day_low,
        "day_close": day_close,
        "day_range": day_range,
        "day_body": day_body,
        "close_position_in_range": safe_divide(day_close - day_low, day_range),
    }
    row.update(gap_features(day, prev))

    ib = ib_levels(meta)
    ib_high = ib["ib_high"]
    ib_low = ib["ib_low"]
    ib_mid = ib["ib_mid"]
    ib_range = ib["ib_range"]

    if not meta.has_ib:
        row.update(_empty_ib_daily(row))
        return row, {"failed_episodes": [], "ib": ib}

    broke_high = bool((meta.after_ib["high"] > ib_high).any()) if not meta.after_ib.empty else False
    broke_low = bool((meta.after_ib["low"] < ib_low).any()) if not meta.after_ib.empty else False

    first_break = find_first_break(meta, ib_high, ib_low)
    opposite = find_opposite_break(meta, first_break, ib_high, ib_low)
    acceptance = post_break_acceptance(meta.day, first_break, ib_high, ib_low, ib_mid)
    mfe = favorable_excursion(meta.day, first_break, ib_high, ib_low)

    hit_50 = threshold_hit(meta.day, first_break["pos"], first_break["level"], first_break["direction"], 50)
    hit_100 = threshold_hit(meta.day, first_break["pos"], first_break["level"], first_break["direction"], 100)

    first_to_opp = minutes_between(first_break["time"], opposite["time"])
    minutes_to_first = minutes_between(first["datetime"], first_break["time"])
    minutes_to_50 = minutes_between(first_break["time"], hit_50["time"])
    minutes_to_100 = minutes_between(first_break["time"], hit_100["time"])

    fifty_before_opp = bool(
        hit_50["hit"] and (not opposite["occurred"] or hit_50["pos"] <= opposite["pos"])
    )
    hundred_before_opp = bool(
        hit_100["hit"] and (not opposite["occurred"] or hit_100["pos"] <= opposite["pos"])
    )

    efficiency = safe_divide(ib_range, day_range)
    expansion = safe_divide(day_range, ib_range)
    close_loc = close_location(day_close, ib_high, ib_low)
    trend_day = bool(expansion >= 2.0) if not pd.isna(expansion) else None
    rotational_day = bool(efficiency >= 0.767) if not pd.isna(efficiency) else None

    if pd.isna(expansion):
        day_type = None
    elif expansion >= 3:
        day_type = "TREND_DAY"
    elif expansion >= 2:
        day_type = "NORMAL_VARIATION"
    else:
        day_type = "NORMAL_OR_ROTATIONAL"

    mfe_pct = safe_divide(mfe["mfe_points"], first_break["level"]) * 100 if first_break["level"] else np.nan

    row.update(
        {
            "ib_high": ib_high,
            "ib_low": ib_low,
            "ib_mid": ib_mid,
            "ib_range": ib_range,
            "ib_range_pct": safe_divide(ib_range, day_open) * 100,
            "ib_efficiency_ratio": efficiency,
            "expansion_factor": expansion,
            "broke_ib_high": broke_high,
            "broke_ib_low": broke_low,
            "extension_type": extension_type(broke_high, broke_low),
            "first_break_direction": first_break["direction"],
            "first_break_time": first_break["time"],
            "first_break_hour": to_hour(first_break["time"]),
            "minutes_to_first_break": minutes_to_first,
            "first_break_price": first_break["price"],
            "opposite_break": opposite["occurred"],
            "opposite_break_time": opposite["time"],
            "opposite_break_hour": to_hour(opposite["time"]),
            "minutes_from_first_to_opposite": first_to_opp,
            "mfe_after_first_break_points": mfe["mfe_points"],
            "mfe_after_first_break_pct": mfe_pct,
            "mae_after_first_break_points": mfe["mae_points"],
            "mfe_after_first_break_ib": safe_divide(mfe["mfe_points"], ib_range),
            "time_to_mfe_after_first_break": mfe["time_to_mfe"],
            "hit_50_after_first_break": hit_50["hit"],
            "minutes_to_50_after_first_break": minutes_to_50,
            "speed_to_50_after_first_break": safe_divide(50, max(minutes_to_50, 1)) if hit_50["hit"] else np.nan,
            "hit_100_after_first_break": hit_100["hit"],
            "minutes_to_100_after_first_break": minutes_to_100,
            "speed_to_100_after_first_break": safe_divide(100, max(minutes_to_100, 1)) if hit_100["hit"] else np.nan,
            "returned_inside_ib": acceptance["returned_inside_ib"],
            "crossed_ib_mid_after_break": acceptance["crossed_ib_mid_after_break"],
            "minutes_outside_after_break": acceptance["minutes_outside_after_break"],
            "close_location_vs_ib": close_loc,
            "closed_inside_ib": close_loc == "INSIDE_IB",
            "trend_day_flag": trend_day,
            "rotational_day_flag": rotational_day,
            "day_type_rule": day_type,
            "label_50_before_opposite": fifty_before_opp,
            "label_100_before_opposite": hundred_before_opp,
            "label_opposite_break": opposite["occurred"],
            "label_gap_fill": row["gap_filled"],
            "label_gap_sustain": row["gap_sustain_until_close"],
            "label_trend_day": trend_day,
        }
    )

    aux = {
        "first_break": first_break,
        "opposite": opposite,
        "mfe": mfe,
        "hit_50": hit_50,
        "hit_100": hit_100,
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_mid": ib_mid,
        "ib_range": ib_range,
    }
    return row, aux


def _empty_ib_daily(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ib_high": np.nan,
        "ib_low": np.nan,
        "ib_mid": np.nan,
        "ib_range": np.nan,
        "ib_range_pct": np.nan,
        "ib_efficiency_ratio": np.nan,
        "expansion_factor": np.nan,
        "broke_ib_high": False,
        "broke_ib_low": False,
        "extension_type": "NONE",
        "first_break_direction": None,
        "first_break_time": pd.NaT,
        "first_break_hour": np.nan,
        "minutes_to_first_break": np.nan,
        "first_break_price": np.nan,
        "opposite_break": False,
        "opposite_break_time": pd.NaT,
        "opposite_break_hour": np.nan,
        "minutes_from_first_to_opposite": np.nan,
        "mfe_after_first_break_points": np.nan,
        "mfe_after_first_break_pct": np.nan,
        "mae_after_first_break_points": np.nan,
        "mfe_after_first_break_ib": np.nan,
        "time_to_mfe_after_first_break": np.nan,
        "hit_50_after_first_break": False,
        "minutes_to_50_after_first_break": np.nan,
        "speed_to_50_after_first_break": np.nan,
        "hit_100_after_first_break": False,
        "minutes_to_100_after_first_break": np.nan,
        "speed_to_100_after_first_break": np.nan,
        "returned_inside_ib": False,
        "crossed_ib_mid_after_break": False,
        "minutes_outside_after_break": 0,
        "close_location_vs_ib": None,
        "closed_inside_ib": None,
        "trend_day_flag": None,
        "rotational_day_flag": None,
        "day_type_rule": None,
        "label_50_before_opposite": False,
        "label_100_before_opposite": False,
        "label_opposite_break": False,
        "label_gap_fill": row.get("gap_filled"),
        "label_gap_sustain": row.get("gap_sustain_until_close"),
        "label_trend_day": None,
    }
