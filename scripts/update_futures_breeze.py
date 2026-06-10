#!/usr/bin/env python3
"""Fetch Bank Nifty futures from ICICI Breeze → merge into banknifty_futures_master.csv."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from bnf_research.breeze_data import fetch_breeze_futures_range
from bnf_research.futures_data import FUTURES_TAIL_PATH, load_futures_master, merge_futures, normalize_futures
from update_pipeline import setup_logging

ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_LOOKBACK = 180


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Breeze futures backfill")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(verbose=args.verbose)
    load_dotenv(ENV_PATH)

    logging.info("Breeze futures fetch started (lookback=%s days)", args.lookback_days)
    try:
        tail = fetch_breeze_futures_range(lookback_days=args.lookback_days)
    except Exception:
        logging.exception("Breeze fetch failed — run scripts/setup_breeze_auth.py first")
        return 1

    if tail.empty:
        logging.error("Breeze returned no data")
        return 1

    tail.to_csv(FUTURES_TAIL_PATH, index=False)
    master = merge_futures(load_futures_master(), tail)
    master.to_csv(PROJECT_ROOT / "banknifty_futures_master.csv", index=False)

    logging.info(
        "Breeze merge OK: %s rows, %s → %s, %s sessions",
        len(master),
        master["datetime"].min(),
        master["datetime"].max(),
        master["datetime"].dt.date.nunique(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
