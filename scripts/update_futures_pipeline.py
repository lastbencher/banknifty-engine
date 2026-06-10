#!/usr/bin/env python3
"""Update Bank Nifty futures master (volume + OI) from Definedge NFO."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bnf_research.futures_data import DEFAULT_LOOKBACK_DAYS, update_futures_master
from update_pipeline import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch NFO BANKNIFTY minute bars with volume/OI.")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--skip-fetch", action="store_true", help="Merge from existing banknifty_futures_180d.csv")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(verbose=args.verbose)

    logging.info("=" * 60)
    logging.info("Bank Nifty futures update started")

    try:
        master = update_futures_master(
            lookback_days=args.lookback_days,
            skip_fetch=args.skip_fetch,
        )
        logging.info("Futures update OK — last bar %s", master["datetime"].max())
        return 0
    except Exception:
        logging.exception("Futures update failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
