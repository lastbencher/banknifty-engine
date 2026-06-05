# Phase 2B Feature Audit

This report audits the generated feature datasets for coverage, basic consistency, label balance, event mix, and leakage watchlist columns.

## Daily Table

| Metric | Value |
| --- | --- |
| Rows | 2,773 |
| Date range | 2015-01-09 to 2026-05-25 |
| Duplicate dates | 0 |
| Incomplete sessions | 13 |
| Median IB range | 226.85 |
| Median day range | 407.25 |

## Daily Labels

| Label | Positive rate | Missing |
| --- | --- | --- |
| label_50_before_opposite | 70.83% | 0.00% |
| label_100_before_opposite | 53.80% | 0.00% |
| label_opposite_break | 22.50% | 0.00% |
| label_gap_fill | 68.01% | 0.04% |
| label_gap_sustain | 31.95% | 0.04% |
| label_trend_day | 35.30% | 0.00% |

## High Missingness Columns

| Column | Missing |
| --- | --- |
| opposite_break_time | 77.50% |
| opposite_break_hour | 77.50% |
| minutes_from_first_to_opposite | 77.50% |
| minutes_to_100_after_first_break | 45.08% |
| speed_to_100_after_first_break | 45.08% |
| first_100_hit_time | 45.08% |
| first_100_hit_hour | 45.08% |
| gap_fill_time | 31.99% |
| minutes_to_gap_fill | 31.99% |
| minutes_to_50_after_first_break | 27.59% |
| speed_to_50_after_first_break | 27.59% |
| first_50_hit_time | 27.59% |
| first_50_hit_hour | 27.59% |

## Incomplete Sessions

| date | bars_count | session_start | session_end |
| --- | --- | --- | --- |
| 2015-11-11 | 72 | 2015-11-11 17:30:00 | 2015-11-11 18:44:01 |
| 2017-10-19 | 60 | 2017-10-19 18:30:00 | 2017-10-19 19:29:00 |
| 2018-11-07 | 60 | 2018-11-07 17:30:00 | 2018-11-07 18:29:00 |
| 2019-10-27 | 60 | 2019-10-27 18:15:00 | 2019-10-27 19:14:00 |
| 2020-11-14 | 60 | 2020-11-14 18:15:00 | 2020-11-14 19:14:00 |
| 2021-02-24 | 129 | 2021-02-24 09:15:00 | 2021-02-24 16:59:00 |
| 2021-11-04 | 60 | 2021-11-04 18:15:00 | 2021-11-04 19:14:00 |
| 2022-10-24 | 60 | 2022-10-24 18:15:00 | 2022-10-24 19:14:00 |
| 2023-11-12 | 60 | 2023-11-12 18:15:00 | 2023-11-12 19:14:00 |
| 2024-03-02 | 105 | 2024-03-02 09:15:00 | 2024-03-02 12:29:00 |
| 2024-05-18 | 105 | 2024-05-18 09:15:00 | 2024-05-18 12:29:00 |
| 2024-11-01 | 60 | 2024-11-01 18:00:00 | 2024-11-01 18:59:00 |
| 2025-10-21 | 60 | 2025-10-21 13:45:00 | 2025-10-21 14:44:00 |

## Leakage Watchlist

Columns below may be useful labels or post-event analysis fields, but should not be used as pre-open or early-checkpoint predictors.
| Column |
| --- |
| day_high |
| day_low |
| day_close |
| opposite_break |
| opposite_break_time |
| opposite_break_hour |
| minutes_from_first_to_opposite |
| mfe_after_first_break_points |
| mae_after_first_break_points |
| mfe_after_first_break_ib |
| time_to_mfe_after_first_break |
| hit_50_after_first_break |
| minutes_to_50_after_first_break |
| speed_to_50_after_first_break |
| hit_100_after_first_break |
| minutes_to_100_after_first_break |
| speed_to_100_after_first_break |
| trend_day_flag |
| rolling_20d_opposite_break_rate |
| rolling_20d_trend_day_rate |

## Checkpoint Table

| Metric | Value |
| --- | --- |
| Rows | 13,865 |
| Checkpoint minutes | 3, 5, 10, 15, 30 |
| Expected rows | 13,865 |
| Invalid checkpoints | 0 |
| Duplicate keys | 0 |

## Checkpoint Profiles

| Minute | Median range | Median abs speed | Gap filled rate |
| --- | --- | --- | --- |
| 3 | 115.50 | 17.95 | 31.12% |
| 5 | 125.65 | 11.87 | 34.04% |
| 10 | 148.00 | 7.18 | 38.87% |
| 15 | 162.35 | 4.88 | 41.40% |
| 30 | 191.05 | 2.78 | 47.06% |

## Event Table

| Metric | Value |
| --- | --- |
| Rows | 49,314 |
| Duplicate event ids | 0 |
| Rows without daily match | 0 |
| Median events per day | 16.0 |

## Event Mix

| Event type | Rows | Share |
| --- | --- | --- |
| TRAP | 28728 | 58.26% |
| POINT_MOVE | 11778 | 23.88% |
| GAP | 5544 | 11.24% |
| FIRST_BREAK | 2640 | 5.35% |
| OPPOSITE_BREAK | 624 | 1.27% |

## Top Event Subtypes

| Subtype | Rows | Share |
| --- | --- | --- |
| FAILED_HIGH_BREAK | 14676 | 29.76% |
| FAILED_LOW_BREAK | 14052 | 28.49% |
| FROM_OPEN_50 | 4498 | 9.12% |
| FROM_OPEN_100 | 3749 | 7.60% |
| GAP_OPEN | 2772 | 5.62% |
| IB_FIRST_BREAK | 2640 | 5.35% |
| FROM_FIRST_BREAK_50 | 2008 | 4.07% |
| GAP_FILL | 1886 | 3.82% |
| FROM_FIRST_BREAK_100 | 1523 | 3.09% |
| GAP_SUSTAIN_CLOSE | 886 | 1.80% |
| IB_OPPOSITE_BREAK | 624 | 1.27% |

## Audit Warnings

- Daily table has 13 incomplete sessions.
