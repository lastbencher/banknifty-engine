#!/usr/bin/env python3
"""
Definedge auth setup — login once and persist credentials to .env.

Usage:
  ./venv/bin/python scripts/setup_definedge_auth.py
  ./venv/bin/python scripts/setup_definedge_auth.py --otp 123456
  ./venv/bin/python scripts/setup_definedge_auth.py --totp-secret YOUR_BASE32_SECRET
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, set_key

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from update_pipeline import AUTH_PENDING_PATH, ENV_PATH, complete_login_with_otp, connect_definedge  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Setup Definedge API authentication")
    parser.add_argument("--otp", help="One-time 6-digit OTP/TOTP from SMS or Authenticator")
    parser.add_argument(
        "--totp-secret",
        help="Base32 External TOTP secret — saved to .env for unattended cron/live sessions",
    )
    parser.add_argument("--test-only", action="store_true", help="Test login only, do not update data")
    return parser.parse_args()


def prompt_otp() -> str:
    try:
        otp = input("Enter Definedge 6-digit OTP/TOTP: ").strip()
    except EOFError:
        raise SystemExit(
            "No OTP provided. Run:\n"
            "  ./venv/bin/python scripts/setup_definedge_auth.py --otp 123456\n"
            "Or add TOTP_SECRET to .env for automation."
        ) from None
    if len(otp) != 6 or not otp.isdigit():
        raise SystemExit("OTP must be 6 digits.")
    return otp


def main() -> int:
    args = parse_args()
    load_dotenv(ENV_PATH)

    if not os.getenv("API_TOKEN") or not os.getenv("API_SECRET"):
        print("Missing API_TOKEN or API_SECRET in .env", file=sys.stderr)
        return 1

    if args.totp_secret:
        if not ENV_PATH.exists():
            ENV_PATH.touch()
        set_key(ENV_PATH, "TOTP_SECRET", args.totp_secret.strip().replace(" ", ""))
        print("Saved TOTP_SECRET to .env")

    if args.otp:
        os.environ["DEFINEDGE_TOTP"] = args.otp.strip()
    elif not os.getenv("TOTP_SECRET") and not os.getenv("INTEGRATE_API_SESSION_KEY"):
        os.environ["DEFINEDGE_TOTP"] = prompt_otp()

    try:
        if args.otp and AUTH_PENDING_PATH.exists():
            conn = complete_login_with_otp(args.otp.strip())
        else:
            conn = connect_definedge()
        uid, actid, _, _ = conn.get_session_keys()
        print(f"Login OK — uid={uid} actid={actid}")
        print("Session keys saved to .env (valid ~24 hours)")
    except Exception as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1

    if args.test_only:
        return 0

    print("\nRunning data update...")
    from update_pipeline import main as update_main

    sys.argv = ["update_pipeline.py"]
    return update_main()


if __name__ == "__main__":
    raise SystemExit(main())
