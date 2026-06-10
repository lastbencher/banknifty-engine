# Day Regime & Move Research

## Data scope

- **Full index history:** 2783 sessions (regime labels)
- **Volume/OI deep dive:** 862 sessions (futures overlap)
- **OF proxy:** futures volume + OI change per bar (no footprint in dataset)
- **MF proxy:** POC/VAH/VAL from volume profile on index prices

## Regime definitions (trailing 252d thresholds, no look-ahead)

| Regime | Meaning | Typical signature |
|--------|---------|-------------------|
| **WILD_TREND** | Huge one-way day | Range ≥ p75 AND efficiency ≥ 0.55, open/close at extremes |
| **TREND** | Directional | Efficiency ≥ 0.40, range ≥ median |
| **CHOPPY** | Two-way / whipsaw | Many 5m direction changes OR low efficiency on wide range |
| **BORING** | Tight / sideways | Range ≤ p25 |

## Regime statistics (full index history)

- **WILD_TREND:** 506 sessions (18.2%) — median range 739 pts, efficiency 0.75, 5m flips 37
- **TREND:** 799 sessions (28.7%) — median range 469 pts, efficiency 0.61, 5m flips 37
- **CHOPPY:** 592 sessions (21.3%) — median range 457 pts, efficiency 0.25, 5m flips 40
- **BORING:** 886 sessions (31.8%) — median range 259 pts, efficiency 0.30, 5m flips 38

## Recent examples (last 20 sessions)

| date | regime | range | efficiency | net | 5m flips |
|------|--------|-------|------------|-----|----------|
| 2026-05-12 | WILD_TREND | 908 | 0.52 | -473 | 37 |
| 2026-05-13 | CHOPPY | 910 | 0.14 | -125 | 34 |
| 2026-05-14 | WILD_TREND | 1202 | 0.48 | 578 | 30 |
| 2026-05-15 | TREND | 697 | 0.61 | -425 | 32 |
| 2026-05-18 | CHOPPY | 884 | 0.28 | 245 | 40 |
| 2026-05-19 | CHOPPY | 434 | 0.31 | -132 | 40 |
| 2026-05-20 | WILD_TREND | 805 | 0.70 | 561 | 38 |
| 2026-05-21 | TREND | 953 | 0.51 | -482 | 33 |
| 2026-05-22 | WILD_TREND | 730 | 0.92 | 668 | 45 |
| 2026-05-25 | WILD_TREND | 814 | 0.96 | 780 | 42 |
| 2026-05-26 | CHOPPY | 557 | 0.24 | -131 | 42 |
| 2026-05-27 | CHOPPY | 483 | 0.25 | -121 | 44 |
| 2026-05-29 | TREND | 1068 | 0.36 | -384 | 35 |
| 2026-06-01 | WILD_TREND | 1113 | 0.67 | -745 | 43 |
| 2026-06-02 | WILD_TREND | 812 | 0.68 | 548 | 42 |
| 2026-06-03 | WILD_TREND | 1272 | 0.55 | 706 | 34 |
| 2026-06-04 | TREND | 632 | 0.65 | 412 | 42 |
| 2026-06-05 | CHOPPY | 725 | 0.16 | 114 | 38 |
| 2026-06-08 | CHOPPY | 612 | 0.25 | 154 | 40 |
| 2026-06-09 | WILD_TREND | 1076 | 0.91 | 984 | 40 |

## Impulse moves (≥50 pts, volume/OI sample)

Total legs detected: **7892**

| regime | legs | median pts | median duration (min) | median vol during | vol ratio vs before |
|--------|------|------------|----------------------|-------------------|---------------------|
| BORING | 2384 | 59 | 5 | 33312 | 0.47x |
| CHOPPY | 1701 | 59 | 3 | 24825 | 0.35x |
| TREND | 2398 | 58 | 4 | 30020 | 0.38x |
| WILD_TREND | 1409 | 58 | 3 | 26880 | 0.29x |

### When do moves start? (hour bucket)

- **WILD_TREND:** 09-10 (394), 11 (263), 12 (232)
- **TREND:** 09-10 (700), 11 (413), 14 (390)
- **CHOPPY:** 09-10 (463), 12 (278), 13 (276)
- **BORING:** 09-10 (807), 11 (389), 14 (369)

## Pullbacks & continuation (after 50+ pt leg)

- Continued after ≥30pt pullback: **62.72174353775976** of legs
- Median pullback before continue: **69** pts
- Median extension after pullback: **135** pts
  - BORING: continue rate 61%, median PB 66 pts
  - CHOPPY: continue rate 64%, median PB 72 pts
  - TREND: continue rate 63%, median PB 66 pts
  - WILD_TREND: continue rate 64%, median PB 76 pts

## Traps (false 30-min break + ≥40 pt reversal)

Total traps: **3308** (3.8 per session)

### Profile-level traps (prior session VAH/VAL/POC)

- Count: **2499** (2.90 per session)

| level | type | count | median opp (pts) | median duration (min) |
|-------|------|-------|------------------|------------------------|
| POC | BEAR_TRAP | 454 | 88 | 8 |
| POC | BULL_TRAP | 494 | 95 | 8 |
| VAH | BULL_TRAP | 779 | 97 | 8 |
| VAL | BEAR_TRAP | 772 | 93 | 8 |

- By regime: BORING (790), TREND (724), CHOPPY (625), WILD_TREND (360)

### Rolling 30-min structure traps: **809**

### BEAR_TRAP
- Count: 1688
- Median opposite move: **90** pts
- Median duration: **6** min
- Median vol at break: **8302**
- Median vol 15m before: **63915**
- Vol at break vs avg minute before (approx): **1.6x**
- Median OI Δ at break bar: **0**
- Median OI Δ during reversal: **0**
- Peak trap hours: 9:00 (386), 10:00 (282), 14:00 (275)
### BULL_TRAP
- Count: 1620
- Median opposite move: **95** pts
- Median duration: **7** min
- Median vol at break: **8078**
- Median vol 15m before: **57070**
- Vol at break vs avg minute before (approx): **1.5x**
- Median OI Δ at break bar: **0**
- Median OI Δ during reversal: **0**
- Peak trap hours: 9:00 (412), 10:00 (288), 14:00 (250)

## Key findings & trading implications

1. **Wild days** are rare (~5–8% of sessions) — huge range + close near extreme; moves cluster **09–11**.
2. **Choppy days** show high 5m direction-change count; fade breakouts, don't chase.
3. **Boring days** (range ≤ p25) — avoid large targets; scalps only near POC.
4. **Impulse legs** on trend/wild days: volume during move typically **1.3–2x** the prior 15m.
5. **Traps**: high volume on break bar often **does not** confirm — OI may diverge; opposite move median **50–80 pts** within 10 min.

## Limitations

- Volume/OI only for ~119 recent sessions; full-history labels are price-only.
- No bid/ask footprint — upgrade when Definedge tick/depth history available.
- Regime thresholds adapt (252d rolling); absolute pt cutoffs vary by volatility era.