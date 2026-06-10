# Phase 4 Trade Simulator Report

**Setup:** 2 lots × 15 qty | lot1 @ +50 pts, lot2 @ +100 pts | stop = opposite IB
**Entry:** first IB break after signal checkpoint, matching required direction
**Mode:** walk-forward buckets (252-session trailing, no look-ahead)

## Overall P&L

| Metric | Value |
|--------|-------|
| trades | 3965 |
| signals_with_entry | 3965 |
| win_rate | 70.54 |
| hit_50_rate | 76.29 |
| hit_100_rate | 61.01 |
| stop_rate | 10.14 |
| total_points | 1,937.61 |
| total_rupees | 29,064.17 |
| avg_points | 0.49 |
| avg_rupees | 7.33 |
| median_rupees | 2,250.00 |
| avg_win_pts | 137.97 |
| avg_loss_pts | -328.73 |
| profit_factor | 1.01 |
| median_risk_pts | 343.10 |
| avg_rr_realized | 0.35 |

## Best entry time windows (30-min buckets)

| window | trades | win_rate_pct | hit_100_pct | avg_rupees | total_rupees | median_entry_min_from_open |
| --- | --- | --- | --- | --- | --- | --- |
| 15:30 | 3 | 100.00 | 100.00 | 2,250.00 | 6,750.00 | 390.00 |
| 13:00 | 189 | 73.54 | 62.96 | 1,118.17 | 211,333.50 | 240.00 |
| 11:30 | 344 | 78.20 | 64.83 | 976.90 | 336,053.25 | 146.00 |
| 11:00 | 398 | 66.58 | 62.06 | 560.77 | 223,186.50 | 119.00 |
| 13:30 | 184 | 66.85 | 61.41 | 483.71 | 89,002.50 | 270.00 |
| 10:30 | 750 | 76.53 | 66.67 | 262.86 | 197,147.06 | 86.00 |
| 15:00 | 73 | 45.21 | 26.03 | 185.59 | 13,548.00 | 362.00 |
| 12:00 | 196 | 69.90 | 54.08 | -102.01 | -19,993.50 | 176.00 |
| 14:30 | 91 | 64.84 | 37.36 | -111.21 | -10,119.75 | 326.00 |
| 12:30 | 225 | 65.78 | 52.44 | -363.51 | -81,789.75 | 206.00 |
| 10:00 | 1408 | 70.53 | 64.91 | -577.17 | -812,659.09 | 63.00 |
| 14:00 | 104 | 51.92 | 22.12 | -1,186.49 | -123,394.55 | 298.00 |

## By signal checkpoint clock

| checkpoint_clock | trades | win_rate_pct | hit_100_pct | avg_rupees | total_rupees |
| --- | --- | --- | --- | --- | --- |
| 09:42 | 352 | 72.73 | 63.07 | 106.55 | 37,506.77 |
| 09:30 | 411 | 70.56 | 61.56 | 84.98 | 34,926.75 |
| 09:27 | 336 | 72.02 | 61.90 | 51.67 | 17,360.23 |
| 09:21 | 324 | 69.44 | 59.88 | 49.06 | 15,894.80 |
| 09:18 | 317 | 69.09 | 60.88 | 48.96 | 15,520.48 |
| 09:36 | 354 | 70.62 | 59.89 | 24.42 | 8,646.02 |
| 09:39 | 348 | 70.11 | 61.78 | -5.86 | -2,038.48 |
| 09:45 | 466 | 71.89 | 62.45 | -12.03 | -5,603.98 |
| 09:25 | 177 | 70.06 | 61.02 | -70.81 | -12,533.23 |
| 09:33 | 354 | 69.49 | 58.76 | -47.56 | -16,835.27 |
| 09:24 | 326 | 70.55 | 60.43 | -87.64 | -28,571.95 |
| 09:20 | 200 | 68.00 | 59.00 | -176.04 | -35,207.98 |

## Suggested entry-time filter

Most 100-pt winners enter **10:00–12:00 IST** (right after IB completes ~10:15).

**Recommended rule:** take IB-break entries only **10:30–12:30 IST**.

| Best 30-min bucket | 13:00 |
| Trades | 189 |
| Win rate | 73.5% |
| Hit 100 (lot 2) | 63.0% |
| Avg ₹/trade (2×15 qty) | 1,118 |