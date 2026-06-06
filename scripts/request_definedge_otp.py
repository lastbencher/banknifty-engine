#!/usr/bin/env python3
"""Step 1: Trigger Definedge SMS OTP. Step 2: complete with setup_definedge_auth.py --otp CODE."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PENDING_PATH = PROJECT_ROOT / "live" / "auth_pending.json"


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    import os

    api_token = os.getenv("API_TOKEN", "").strip()
    api_secret = os.getenv("API_SECRET", "").strip()
    if not api_token or not api_secret:
        print("Missing API_TOKEN or API_SECRET in .env", file=sys.stderr)
        return 1

    from integrate import ConnectToIntegrate

    conn = ConnectToIntegrate()
    print("Requesting OTP from Definedge (check your registered mobile)...")

    try:
        resp = conn.send_request(
            route_prefix=conn.login_url,
            route=f"login/{api_token}",
            method="GET",
            extra_headers={"api_secret": api_secret},
        )
    except Exception as exc:
        print(f"Failed to request OTP: {exc}", file=sys.stderr)
        return 1

    otp_token = resp.get("otp_token")
    if not otp_token:
        print(f"No otp_token in response: {resp}", file=sys.stderr)
        return 1

    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(
        json.dumps(
            {
                "otp_token": otp_token,
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    print("OTP requested — check SMS on your Definedge-registered mobile.")
    print("Paste the 6-digit code here or run:")
    print("  ./venv/bin/python scripts/setup_definedge_auth.py --otp XXXXXX")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
