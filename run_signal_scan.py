#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from signal_engine.engine import SignalEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan historical Bank Nifty checkpoints for Phase 2B trade signals."
    )
    parser.add_argument("--feature-dir", type=Path, default=None)
    parser.add_argument("--rules", type=Path, default=None, help="Path to signal_rules.json")
    parser.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--last", type=int, default=20, help="Print last N signals")
    parser.add_argument(
        "--walkforward",
        action="store_true",
        help="Use walk-forward quartile buckets (no look-ahead; required for backtests)",
    )
    parser.add_argument(
        "--walkforward-window",
        type=int,
        default=252,
        help="Trailing sessions for walk-forward bucket reference",
    )
    parser.add_argument("--all-matches", action="store_true", help="Emit all rule matches per checkpoint")
    parser.add_argument("--output", type=Path, default=None, help="Optional CSV output path")
    return parser.parse_args()


def signals_to_frame(signals: list) -> pd.DataFrame:
    rows = []
    for signal in signals:
        rows.append(
            {
                "date": signal.date,
                "checkpoint_minute": signal.checkpoint_minute,
                "checkpoint_clock": signal.checkpoint_clock,
                "checkpoint_time": signal.checkpoint_time,
                "rule_id": signal.rule_id,
                "source_rule_id": signal.source_rule_id,
                "stable_id": signal.stable_id,
                "timeframe": signal.timeframe,
                "side": signal.side,
                "direction": signal.direction,
                "confidence": signal.confidence,
                "entry_price": signal.entry_price,
                "entry_trigger": signal.entry_trigger,
                "required_break_direction": signal.required_break_direction,
                "target_50": signal.target_50,
                "target_100": signal.target_100,
                "stop_price": signal.stop_price,
                "stop_reason": signal.stop_reason,
                "ib_high": signal.ib_high,
                "ib_low": signal.ib_low,
                "pct_100_before_opposite": signal.stats.get("pct_100_before_opposite"),
                "pct_opposite_break": signal.stats.get("pct_opposite_break"),
                "edge_score": signal.stats.get("edge_score"),
                "rule": signal.rule,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()

    engine_kwargs: dict = {
        "bucket_mode": "walkforward" if args.walkforward else "full",
        "walkforward_window": args.walkforward_window,
    }
    if args.feature_dir is not None:
        engine_kwargs["feature_dir"] = args.feature_dir
    if args.rules is not None:
        engine_kwargs["rules_path"] = args.rules

    engine = SignalEngine(**engine_kwargs)
    signals = engine.scan_history(
        start_date=args.start,
        end_date=args.end,
        best_only=not args.all_matches,
    )

    mode = "walkforward" if args.walkforward else "full-history"
    print(f"Bucket mode: {mode}")
    print(f"Loaded {len(engine.rules)} rules")
    print(f"Matched {len(signals)} checkpoint signals")

    if not signals:
        return

    frame = signals_to_frame(signals)
    display = frame.tail(args.last)

    print("\nLatest signals:")
    print(
        display[
            [
                "date",
                "checkpoint_minute",
                "checkpoint_clock",
                "rule_id",
                "source_rule_id",
                "timeframe",
                "side",
                "required_break_direction",
                "confidence",
                "entry_price",
                "target_50",
                "stop_price",
            ]
        ].to_string(index=False)
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"\nWrote {len(frame)} rows to {args.output}")


if __name__ == "__main__":
    main()
