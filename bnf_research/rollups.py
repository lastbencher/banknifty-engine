from __future__ import annotations

import pandas as pd


def add_daily_rollups(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.sort_values("date").reset_index(drop=True)

    valid_ib = daily["ib_range"]
    q25 = valid_ib.quantile(0.25)
    q75 = valid_ib.quantile(0.75)

    daily["ib_bucket"] = "NORMAL"
    daily.loc[daily["ib_range"] <= q25, "ib_bucket"] = "NARROW"
    daily.loc[daily["ib_range"] >= q75, "ib_bucket"] = "WIDE"
    daily.loc[daily["ib_range"].isna(), "ib_bucket"] = None

    daily["rolling_20d_ib_median"] = daily["ib_range"].shift(1).rolling(20, min_periods=5).median()
    daily["rolling_20d_day_range_median"] = (
        daily["day_range"].shift(1).rolling(20, min_periods=5).median()
    )
    daily["rolling_20d_opposite_break_rate"] = (
        daily["opposite_break"].astype(float).shift(1).rolling(20, min_periods=5).mean()
    )
    daily["rolling_20d_gap_fill_rate"] = (
        daily["gap_filled"].astype(float).shift(1).rolling(20, min_periods=5).mean()
    )
    daily["rolling_20d_trend_day_rate"] = (
        daily["trend_day_flag"].astype(float).shift(1).rolling(20, min_periods=5).mean()
    )
    daily["ib_vs_rolling_median"] = daily["ib_range"] / daily["rolling_20d_ib_median"]

    return daily


def add_checkpoint_rollups(checkpoints: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    if checkpoints.empty:
        return checkpoints

    context_cols = [
        "date",
        "rolling_20d_ib_median",
        "rolling_20d_day_range_median",
        "rolling_20d_opposite_break_rate",
        "rolling_20d_gap_fill_rate",
        "rolling_20d_trend_day_rate",
        "ib_bucket",
    ]
    checkpoints = checkpoints.merge(daily[context_cols], on="date", how="left")
    checkpoints = checkpoints.sort_values(["checkpoint_minute", "date"]).reset_index(drop=True)
    checkpoints["range_vs_20d_checkpoint_median"] = checkpoints.groupby("checkpoint_minute")[
        "range_so_far"
    ].transform(lambda s: s.shift(1).rolling(20, min_periods=5).median())
    checkpoints["range_so_far_vs_checkpoint_median"] = (
        checkpoints["range_so_far"] / checkpoints["range_vs_20d_checkpoint_median"]
    )
    return checkpoints.sort_values(["date", "checkpoint_minute"]).reset_index(drop=True)
