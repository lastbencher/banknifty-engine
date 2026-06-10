#!/usr/bin/env python3
"""Print the Breeze login URL (run locally, then paste URL in browser)."""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from bnf_research.breeze_data import breeze_credentials, login_url

if __name__ == "__main__":
    try:
        key, _ = breeze_credentials()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    url = login_url(key)
    print(url)
    print("\nPaste the entire line above into your browser address bar.", file=sys.stderr)
    print("Do NOT open https://api.icicidirect.com/apiuser/login without ?api_key=…", file=sys.stderr)
