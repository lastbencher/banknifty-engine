# Phase 2B Signal Validation

Inputs: canonical `daily_features` and `checkpoint_features` only.
Signals use checkpoint-known features. Future labels are used only for validation.

## Base Rates

Sessions per checkpoint: 13,200
50 before opposite break: 74.39%
100 before opposite break: 56.52%
Opposite break: 23.64%

## Best Overall Signals

| rule_id | checkpoint_minute | sessions | rule | edge_score | pct_50_before_opposite | pct_100_before_opposite | pct_opposite_break | median_minutes_to_50 | median_minutes_to_100 | era_coverage | era_min_100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1644 | 15 | 60 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH | 100.70 | 93.33 | 81.67 | 8.33 | 9.50 | 40.00 | 0 |  |
| S0695 | 5 | 153 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH | 98.45 | 89.54 | 77.78 | 11.11 | 8.00 | 28.00 | 4 | 70.89 |
| S1096 | 15 | 69 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & gap_direction=DOWN | 95.26 | 89.86 | 78.26 | 8.70 | 6.00 | 19.00 | 1 | 75.00 |
| S0679 | 3 | 152 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH | 92.12 | 89.47 | 75.66 | 12.50 | 8.00 | 29.50 | 4 | 68.42 |
| S1019 | 3 | 61 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW & gap_direction=DOWN | 91.86 | 90.16 | 78.69 | 11.48 | 4.00 | 32.50 | 1 | 77.14 |
| S1404 | 15 | 152 | gap_direction=DOWN & opening_direction=DOWN & range_speed_bucket=Q4_HIGH | 91.42 | 90.13 | 76.32 | 14.47 | 8.00 | 29.50 | 3 | 76.19 |
| S0711 | 10 | 163 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH | 88.94 | 87.73 | 74.85 | 12.88 | 8.00 | 28.00 | 4 | 69.05 |
| S1183 | 5 | 88 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q3 & opening_direction=DOWN | 88.93 | 89.77 | 78.41 | 17.05 | 3.50 | 18.00 | 2 | 77.27 |
| S0235 | 3 | 221 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH | 88.31 | 83.71 | 74.21 | 9.95 | 9.00 | 29.50 | 4 | 70.00 |
| S0743 | 30 | 175 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH | 87.29 | 88.57 | 73.14 | 13.14 | 8.00 | 28.00 | 4 | 70.00 |
| S1122 | 30 | 77 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & gap_direction=DOWN | 87.21 | 90.91 | 72.73 | 6.49 | 7.50 | 26.50 | 1 | 70.00 |
| S1239 | 15 | 74 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & opening_direction=DOWN | 87.15 | 91.89 | 78.38 | 17.57 | 6.00 | 21.00 | 1 | 82.50 |
| S1155 | 3 | 124 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & opening_direction=DOWN | 86.64 | 84.68 | 75.00 | 11.29 | 12.00 | 38.00 | 4 | 65.52 |
| S0727 | 15 | 160 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH | 86.05 | 89.38 | 72.50 | 13.12 | 9.00 | 28.00 | 4 | 67.53 |
| S1388 | 10 | 145 | gap_direction=DOWN & opening_direction=DOWN & range_speed_bucket=Q4_HIGH | 85.98 | 88.28 | 75.17 | 15.86 | 7.00 | 25.00 | 3 | 75.86 |

## Best 50-Point Signals

| rule_id | checkpoint_minute | sessions | rule | edge_score | pct_50_before_opposite | pct_100_before_opposite | pct_opposite_break | median_minutes_to_50 | median_minutes_to_100 | era_coverage | era_min_100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1232 | 15 | 80 | range_speed_bucket=Q3 & directional_efficiency_bucket=Q2 & opening_direction=UP | 78.39 | 93.75 | 72.50 | 15.00 | 10.00 | 43.50 | 1 | 78.12 |
| S1644 | 15 | 60 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH | 100.70 | 93.33 | 81.67 | 8.33 | 9.50 | 40.00 | 0 |  |
| S1334 | 15 | 79 | range_speed_bucket=Q4_HIGH & opening_pressure=MIDDLE_THIRD & opening_direction=DOWN | 76.24 | 92.41 | 72.15 | 18.99 | 5.00 | 17.00 | 2 | 69.23 |
| S1180 | 5 | 64 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW & opening_direction=UP | 58.94 | 92.19 | 70.31 | 26.56 | 4.00 | 31.00 | 1 | 70.59 |
| S1239 | 15 | 74 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & opening_direction=DOWN | 87.15 | 91.89 | 78.38 | 17.57 | 6.00 | 21.00 | 1 | 82.50 |
| S1046 | 5 | 72 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW & gap_direction=DOWN | 72.74 | 91.67 | 73.61 | 20.83 | 4.00 | 29.00 | 1 | 81.82 |
| S0248 | 5 | 125 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW | 70.73 | 91.20 | 72.00 | 23.20 | 5.50 | 30.00 | 3 | 62.50 |
| S1122 | 30 | 77 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & gap_direction=DOWN | 87.21 | 90.91 | 72.73 | 6.49 | 7.50 | 26.50 | 1 | 70.00 |
| S1269 | 30 | 75 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & opening_direction=DOWN | 65.87 | 90.67 | 72.00 | 22.67 | 6.49 | 30.00 | 1 | 72.22 |
| S1019 | 3 | 61 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW & gap_direction=DOWN | 91.86 | 90.16 | 78.69 | 11.48 | 4.00 | 32.50 | 1 | 77.14 |
| S1179 | 5 | 61 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW & opening_direction=DOWN | 72.53 | 90.16 | 73.77 | 19.67 | 6.00 | 30.00 | 1 | 80.00 |
| S1268 | 30 | 71 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW & opening_direction=DOWN | 73.75 | 90.14 | 70.42 | 15.49 | 6.50 | 12.00 | 2 | 66.67 |
| S1404 | 15 | 152 | gap_direction=DOWN & opening_direction=DOWN & range_speed_bucket=Q4_HIGH | 91.42 | 90.13 | 76.32 | 14.47 | 8.00 | 29.50 | 3 | 76.19 |
| S1096 | 15 | 69 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & gap_direction=DOWN | 95.26 | 89.86 | 78.26 | 8.70 | 6.00 | 19.00 | 1 | 75.00 |
| S1420 | 30 | 147 | gap_direction=DOWN & opening_direction=DOWN & range_speed_bucket=Q4_HIGH | 85.67 | 89.80 | 74.15 | 13.61 | 7.00 | 29.50 | 3 | 68.85 |

## Best 100-Point Signals

| rule_id | checkpoint_minute | sessions | rule | edge_score | pct_50_before_opposite | pct_100_before_opposite | pct_opposite_break | median_minutes_to_50 | median_minutes_to_100 | era_coverage | era_min_100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1644 | 15 | 60 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH | 100.70 | 93.33 | 81.67 | 8.33 | 9.50 | 40.00 | 0 |  |
| S1121 | 30 | 62 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW & gap_direction=UP | 85.58 | 87.10 | 79.03 | 16.13 | 5.00 | 14.50 | 1 | 80.65 |
| S1019 | 3 | 61 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q1_LOW & gap_direction=DOWN | 91.86 | 90.16 | 78.69 | 11.48 | 4.00 | 32.50 | 1 | 77.14 |
| S1183 | 5 | 88 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q3 & opening_direction=DOWN | 88.93 | 89.77 | 78.41 | 17.05 | 3.50 | 18.00 | 2 | 77.27 |
| S1239 | 15 | 74 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & opening_direction=DOWN | 87.15 | 91.89 | 78.38 | 17.57 | 6.00 | 21.00 | 1 | 82.50 |
| S1013 | 3 | 60 | range_speed_bucket=Q3 & directional_efficiency_bucket=Q2 & gap_direction=DOWN | 77.95 | 86.67 | 78.33 | 20.00 | 7.00 | 27.00 | 1 | 79.17 |
| S1096 | 15 | 69 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & gap_direction=DOWN | 95.26 | 89.86 | 78.26 | 8.70 | 6.00 | 19.00 | 1 | 75.00 |
| S0695 | 5 | 153 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH | 98.45 | 89.54 | 77.78 | 11.11 | 8.00 | 28.00 | 4 | 70.89 |
| S1144 | 3 | 90 | range_speed_bucket=Q3 & directional_efficiency_bucket=Q1_LOW & opening_direction=UP | 81.58 | 88.89 | 77.78 | 20.00 | 9.00 | 43.00 | 2 | 78.57 |
| S1260 | 30 | 80 | range_speed_bucket=Q3 & directional_efficiency_bucket=Q1_LOW & opening_direction=DOWN | 68.06 | 87.50 | 77.50 | 27.50 | 7.00 | 48.00 | 2 | 66.67 |
| S1208 | 10 | 61 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & opening_direction=DOWN | 78.59 | 86.89 | 77.05 | 18.03 | 8.50 | 20.50 | 1 | 80.65 |
| S1319 | 10 | 64 | range_speed_bucket=Q4_HIGH & opening_pressure=MIDDLE_THIRD & opening_direction=UP | 79.14 | 87.50 | 76.56 | 17.19 | 8.00 | 18.00 | 1 | 71.79 |
| S1404 | 15 | 152 | gap_direction=DOWN & opening_direction=DOWN & range_speed_bucket=Q4_HIGH | 91.42 | 90.13 | 76.32 | 14.47 | 8.00 | 29.50 | 3 | 76.19 |
| S1050 | 5 | 80 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q3 & gap_direction=UP | 75.13 | 86.25 | 76.25 | 22.50 | 3.00 | 16.00 | 2 | 78.26 |
| S1012 | 3 | 87 | range_speed_bucket=Q3 & directional_efficiency_bucket=Q1_LOW & gap_direction=UP | 70.10 | 85.06 | 75.86 | 22.99 | 10.50 | 41.00 | 2 | 75.00 |

## Lowest Opposite-Break Risk Signals

| rule_id | checkpoint_minute | sessions | rule | edge_score | pct_50_before_opposite | pct_100_before_opposite | pct_opposite_break | median_minutes_to_50 | median_minutes_to_100 | era_coverage | era_min_100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1126 | 30 | 92 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & gap_direction=DOWN | 72.38 | 82.61 | 68.48 | 5.43 | 9.00 | 42.00 | 3 | 54.17 |
| S1122 | 30 | 77 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & gap_direction=DOWN | 87.21 | 90.91 | 72.73 | 6.49 | 7.50 | 26.50 | 1 | 70.00 |
| S1265 | 30 | 74 | range_speed_bucket=Q3 & directional_efficiency_bucket=Q3 & opening_direction=UP | 41.53 | 74.32 | 58.11 | 6.76 | 12.50 | 38.00 | 2 | 56.52 |
| S1534 | 3 | 108 | range_vs_recent_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & opening_direction=UP | 50.42 | 75.00 | 62.96 | 7.41 | 20.00 | 40.00 | 2 | 51.11 |
| S1274 | 30 | 93 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & opening_direction=UP | 70.64 | 82.80 | 67.74 | 7.53 | 8.00 | 26.00 | 2 | 65.96 |
| S1633 | 30 | 167 | range_vs_recent_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & opening_direction=DOWN | 51.62 | 74.85 | 62.28 | 7.78 | 15.00 | 42.00 | 3 | 55.56 |
| S0635 | 30 | 287 | range_vs_recent_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH | 51.90 | 75.61 | 60.98 | 8.01 | 18.00 | 47.00 | 4 | 54.86 |
| S1156 | 3 | 97 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & opening_direction=UP | 81.11 | 82.47 | 73.20 | 8.25 | 7.50 | 23.00 | 2 | 73.47 |
| S1644 | 15 | 60 | recent_opposite_rate_bucket=Q1_LOW & range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH | 100.70 | 93.33 | 81.67 | 8.33 | 9.50 | 40.00 | 0 |  |
| S1634 | 30 | 120 | range_vs_recent_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & opening_direction=UP | 42.70 | 76.67 | 59.17 | 8.33 | 20.50 | 49.00 | 2 | 49.09 |
| S1607 | 15 | 84 | range_vs_recent_bucket=Q4_HIGH & directional_efficiency_bucket=Q3 & opening_direction=UP | 30.68 | 72.62 | 55.95 | 8.33 | 14.50 | 65.00 | 2 | 50.00 |
| S1096 | 15 | 69 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q2 & gap_direction=DOWN | 95.26 | 89.86 | 78.26 | 8.70 | 6.00 | 19.00 | 1 | 75.00 |
| S0299 | 30 | 214 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH | 79.45 | 83.18 | 70.56 | 8.88 | 7.50 | 31.00 | 4 | 60.87 |
| S1559 | 5 | 122 | range_vs_recent_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & opening_direction=UP | 32.12 | 71.31 | 55.74 | 9.02 | 19.00 | 32.00 | 3 | 45.28 |
| S1186 | 5 | 109 | range_speed_bucket=Q4_HIGH & directional_efficiency_bucket=Q4_HIGH & opening_direction=UP | 61.58 | 80.73 | 65.14 | 9.17 | 6.00 | 25.00 | 3 | 52.38 |
