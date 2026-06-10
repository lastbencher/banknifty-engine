# Research studies

## IB (Initial Balance) — not used in reports or new studies

IB-based metrics misclassified large BNF days and do not match how we trade
(profile VAH/VAL/POC + Weis springs). **Reports and new simulators ignore IB.**

| Study | Status | Reference levels |
|-------|--------|------------------|
| `day_regime_move_research.py` | **Active** | Regime taxonomy, moves, traps |
| `phase4_trade_simulator.py` | Deprecated | IB breaks (legacy signal engine) |
| `run_profile_levels.py` | **Active** | Index-priced MP, open/close day type |

The production feature pipeline (`bnf_research/`, `signal_engine/`) still
computes IB columns for historical rules — that is unchanged until signal
rules are migrated off IB.
