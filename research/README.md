# Bank Nifty Research

Quantitative research imported from Codex (2026-05-27 session: *you-are-now-my-quantitative-research*).

## Layout

```
research/
├── studies/          # Runnable analysis scripts
└── outputs/          # Generated reports and CSVs
    ├── phase2_fast_moves/
    ├── phase2b_signal_validation/
    └── phase_2b_feature_audit.md
```

## Prerequisites

Feature datasets must exist in `features/` (built by `feature_factory.py`):

- `daily_features.csv`
- `checkpoint_features.csv`
- `event_features.csv`

## Running studies

From the project root:

```bash
python research/studies/phase2_fast_move_research.py
python research/studies/phase2b_signal_validation.py
```

Both scripts read from `features/` and write reports/CSVs into `research/outputs/`.

## Phase summary

| Phase | Script | Key question |
|-------|--------|--------------|
| 2 | `phase2_fast_move_research.py` | How often do 50/100 pt moves happen before an opposite IB break? |
| 2B | `phase2b_signal_validation.py` | Which early-checkpoint feature rules predict fast moves with low trap risk? |
| 3 | `run_signal_scan.py` | Which validated rules fire on each historical session? |

## Phase 3 — Signal Engine

Curated Phase 2B rules live in `config/signal_rules.json`. The engine evaluates checkpoint features and emits trade setups:

```bash
python run_signal_scan.py --last 20
python run_signal_scan.py --walkforward --last 20   # honest buckets (no look-ahead)
python run_signal_scan.py --start 2025-01-01 --output research/outputs/signal_scan_history.csv
```

Each signal includes side, confidence, 50/100 pt targets, opposite-IB stop, and `required_break_direction` (HIGH for LONG, LOW for SHORT — the live runner must confirm the first IB break matches before entry).

**Bucket modes:** Default `full` matches Phase 2B research (in-sample quartiles). Use `--walkforward` for backtests — quartiles are computed from trailing 252 sessions only.

## Key findings (2,773 sessions, 2015–2026)

- **74.4%** hit 50 pts before opposite break; **56.5%** hit 100 pts
- **23.6%** opposite-break (trap) rate
- Best signals combine high `range_speed` + directional efficiency at checkpoints 3/5/15/30 min
- See `outputs/phase2b_signal_validation/phase2b_signal_validation_report.md` for ranked rules

## Source

Original Codex export: `~/Documents/Codex/2026-05-27/you-are-now-my-quantitative-research/`
