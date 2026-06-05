# Phase 2 Fast Move Research

Source inputs: canonical `daily_features`, `checkpoint_features`, and `event_features` only.
No raw minute-bar reprocessing is used in this study.

## Priority Rates

All sessions: 2,773
First-break sessions: 2,640

50 points before opposite break: 74.39%
100 points before opposite break: 56.52%
Opposite break rate: 23.64%
Gap fill rate: 68.70%
Trend day rate: 37.08%

## Era Summary

| era | sessions | pct_50_before_opposite | pct_100_before_opposite | pct_opposite_break | pct_gap_fill | pct_trend_day | median_minutes_to_50 | median_minutes_to_100 | median_speed_to_50 | median_speed_to_100 | median_ib_range | median_trap_severity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| covid | 430 | 86.51 | 72.56 | 23.49 | 67.21 | 40.70 | 8.50 | 32.00 | 5.90 | 3.12 | 299.75 | 9.50 |
| recent | 553 | 82.46 | 66.91 | 21.16 | 71.43 | 27.67 | 7.00 | 28.00 | 7.14 | 3.57 | 341.70 | 11.00 |
| post_covid | 466 | 78.54 | 61.59 | 23.39 | 64.59 | 37.77 | 17.00 | 50.00 | 2.94 | 2.00 | 258.83 | 11.00 |
| pre_covid | 1191 | 64.65 | 43.91 | 24.94 | 69.58 | 39.88 | 40.00 | 103.00 | 1.25 | 0.97 | 145.50 | 11.00 |

## First Break Direction Summary

| first_break_direction | sessions | pct_50_before_opposite | pct_100_before_opposite | pct_opposite_break | pct_gap_fill | pct_trend_day | median_minutes_to_50 | median_minutes_to_100 | median_speed_to_50 | median_speed_to_100 | median_ib_range | median_trap_severity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LOW | 1296 | 75.93 | 58.56 | 22.61 | 73.28 | 37.58 | 17.00 | 50.00 | 2.94 | 2.00 | 227.40 | 10.50 |
| HIGH | 1344 | 72.92 | 54.54 | 24.63 | 64.29 | 36.61 | 19.00 | 60.50 | 2.63 | 1.65 | 220.90 | 11.00 |

## Top Checkpoint Candidate Slices

| checkpoint_minute | range_speed_bucket | directional_efficiency_bucket | gap_direction | era | sessions | pct_50_before_opposite | pct_100_before_opposite | pct_opposite_break | pct_gap_fill | pct_trend_day | median_minutes_to_50 | median_minutes_to_100 | median_speed_to_50 | median_speed_to_100 | median_ib_range | median_trap_severity | lift_50_vs_checkpoint_base | lift_100_vs_checkpoint_base |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | Q3 | Q2 | UP | recent | 40 | 95.00 | 80.00 | 27.50 | 80.00 | 37.50 | 8.00 | 40.00 | 6.25 | 2.50 | 282.32 | 0.00 | 1.28 | 1.42 |
| 3 | Q4_HIGH | Q4_HIGH | UP | covid | 43 | 90.70 | 79.07 | 16.28 | 79.07 | 20.93 | 8.00 | 28.50 | 6.25 | 3.52 | 416.45 | 0.00 | 1.22 | 1.40 |
| 30 | Q4_HIGH | Q4_HIGH | UP | covid | 42 | 90.48 | 66.67 | 16.67 | 73.81 | 28.57 | 4.00 | 33.00 | 12.50 | 3.10 | 418.63 | 0.00 | 1.22 | 1.18 |
| 30 | Q4_HIGH | Q2 | DOWN | recent | 40 | 90.00 | 70.00 | 7.50 | 57.50 | 22.50 | 6.00 | 21.50 | 8.33 | 4.65 | 381.77 | 0.00 | 1.21 | 1.24 |
| 3 | Q3 | Q1_LOW | UP | recent | 47 | 89.36 | 78.72 | 23.40 | 78.72 | 40.43 | 12.50 | 43.50 | 4.01 | 2.31 | 278.45 | 0.00 | 1.20 | 1.39 |
| 15 | Q4_HIGH | Q4_HIGH | UP | covid | 44 | 88.64 | 77.27 | 20.45 | 70.45 | 34.09 | 9.00 | 20.00 | 5.56 | 5.01 | 415.20 | 0.00 | 1.19 | 1.37 |
| 10 | Q4_HIGH | Q4_HIGH | UP | covid | 44 | 88.64 | 72.73 | 18.18 | 79.55 | 27.27 | 5.00 | 17.50 | 10.00 | 5.76 | 407.33 | 0.00 | 1.19 | 1.29 |
| 5 | Q4_HIGH | Q3 | UP | recent | 42 | 88.10 | 78.57 | 16.67 | 66.67 | 28.57 | 3.00 | 12.00 | 16.67 | 8.33 | 393.15 | 0.00 | 1.18 | 1.39 |
| 5 | Q4_HIGH | Q4_HIGH | UP | covid | 46 | 86.96 | 69.57 | 15.22 | 76.09 | 19.57 | 7.50 | 15.50 | 6.70 | 6.80 | 421.10 | 0.00 | 1.17 | 1.23 |
| 30 | Q4_HIGH | Q3 | DOWN | recent | 43 | 86.05 | 69.77 | 20.93 | 69.77 | 25.58 | 4.00 | 22.00 | 12.50 | 4.58 | 468.85 | 0.00 | 1.16 | 1.23 |

## Point Move Speed Summary

| event_subtype | event_direction | events | median_event_minute | median_minutes_from_anchor | median_speed_points_per_min | median_speed_ib_per_min | pct_before_opposite | median_trap_count_before_move | median_trap_severity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FROM_FIRST_BREAK_100 | HIGH | 746 | 196.00 | 60.50 | 1.65 | 0.01 | 98.26 | 3.00 | 3.00 |
| FROM_FIRST_BREAK_100 | LOW | 777 | 179.00 | 50.00 | 2.00 | 0.01 | 97.68 | 3.00 | 3.00 |
| FROM_FIRST_BREAK_50 | HIGH | 999 | 145.00 | 19.00 | 2.63 | 0.01 | 98.10 | 2.00 | 2.00 |
| FROM_FIRST_BREAK_50 | LOW | 1009 | 135.00 | 17.00 | 2.94 | 0.01 | 97.52 | 2.00 | 2.00 |
| FROM_OPEN_100 | HIGH | 1782 | 16.00 | 16.00 | 6.25 | 0.03 | 92.93 | 0.00 | 0.00 |
| FROM_OPEN_100 | LOW | 1967 | 8.00 | 8.00 | 12.50 | 0.05 | 94.00 | 0.00 | 0.00 |
| FROM_OPEN_50 | HIGH | 2165 | 2.00 | 2.00 | 25.00 | 0.08 | 95.94 | 0.00 | 0.00 |
| FROM_OPEN_50 | LOW | 2333 | 0.00 | 0.00 | 50.00 | 0.13 | 97.34 | 0.00 | 0.00 |

## Output Files

- `checkpoint_candidate_slices.csv`
- `checkpoint_summary.csv`
- `checkpoint_univariate_summary.csv`
- `era_direction_summary.csv`
- `era_summary.csv`
- `event_speed_summary.csv`
- `first_break_direction_summary.csv`
- `first_break_hour_summary.csv`
- `gap_summary.csv`
- `ib_bucket_summary.csv`
- `overall_summary.csv`
- `trap_event_summary.csv`
- `trap_summary.csv`