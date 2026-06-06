#!/usr/bin/env python3
"""
Telegram bot — remote OTP login, data update, signals, GitHub sync.

LOCAL (Mac must be on):
  ./scripts/install_telegram_bot.sh

CLOUD (Mac can be off — recommended):
  Deploy cloud/Dockerfile to Railway / Render / Fly.io / Oracle free tier.
  Set env: API_TOKEN, API_SECRET, TELEGRAM_*, GITHUB_TOKEN, GITHUB_REPO
  Whitelist the cloud server IP in Definedge → API Config.

From Telegram:
  /otp 482913  — login + update + signals + GitHub publish
  /signals     — recent signals
  /status      — data freshness
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from telegram_notify import is_authorized_chat, send_message

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = Path(os.getenv("BNF_PYTHON", sys.executable))
SETUP_SCRIPT = PROJECT_ROOT / "scripts" / "setup_definedge_auth.py"
UPDATE_SCRIPT = PROJECT_ROOT / "update_pipeline.py"
LIVE_SCRIPT = PROJECT_ROOT / "live_session.py"
LOG_DIR = PROJECT_ROOT / "live"
IST = __import__("zoneinfo").ZoneInfo("Asia/Kolkata")

OTP_RE = re.compile(r"^\d{6}$")


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "telegram_bot.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def bot_token() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing in .env")
    return token


def data_status() -> str:
    master = PROJECT_ROOT / "banknifty_master.csv"
    if not master.exists():
        return "No banknifty_master.csv yet."

    df = pd.read_csv(master, parse_dates=["datetime"], usecols=["datetime"])
    last = df["datetime"].max()
    today = pd.Timestamp.now(tz=IST).date()
    lag = (today - last.date()).days

    load_dotenv(PROJECT_ROOT / ".env")
    session = "yes" if os.getenv("INTEGRATE_API_SESSION_KEY", "").strip() else "no"

    return (
        f"Last bar: {last}\n"
        f"Lag: {lag} calendar day(s) vs today ({today})\n"
        f"Cached session: {session}"
    )


def run_script(script: Path, *args: str, timeout: int = 900) -> tuple[int, str]:
    proc = subprocess.run(
        [str(PYTHON), str(script), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ},
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output[-2000:]


def post_update_tasks() -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        from publish_to_github import export_latest_signals, format_signals_telegram, publish_data_branch

        export_latest_signals()
        send_message(format_signals_telegram())
        gh_msg = publish_data_branch()
        if "skipped" not in gh_msg.lower():
            send_message(f"📦 {gh_msg}")
    except Exception:
        logging.exception("Post-update tasks failed")
        send_message("⚠️ Post-update (signals/GitHub) failed — check logs")


def handle_otp(otp: str) -> str:
    if not OTP_RE.match(otp):
        return "OTP must be exactly 6 digits."

    send_message("Received OTP — login + update starting (~5 min)…")
    logging.info("OTP update started")

    code, output = run_script(SETUP_SCRIPT, "--otp", otp)
    status = data_status()

    if code == 0:
        msg = f"✅ Update complete\n\n{status}"
        send_message(msg)
        post_update_tasks()
        logging.info("Update OK")
    else:
        msg = f"❌ Update failed (exit {code})\n\n{output[-800:]}\n\n{status}"
        send_message(msg)
        logging.error("Update failed")

    return msg


def handle_update_cached() -> str:
    send_message("Running update with cached session…")
    code, output = run_script(UPDATE_SCRIPT)
    status = data_status()
    if code == 0:
        msg = f"✅ Update complete (cached session)\n\n{status}"
    else:
        msg = f"❌ Update failed — session may be expired.\nSend OTP: /otp 123456\n\n{output[-800:]}\n\n{status}"
    send_message(msg)
    return msg


def handle_status() -> str:
    msg = f"📊 Status\n\n{data_status()}"
    send_message(msg)
    return msg


def handle_signals() -> str:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from publish_to_github import export_latest_signals, format_signals_telegram

    export_latest_signals()
    msg = format_signals_telegram()
    send_message(msg)
    return msg


def handle_help() -> str:
    msg = (
        "Bank Nifty remote control\n\n"
        "/otp 482913 — SMS OTP → update + signals + GitHub\n"
        "482913 — same (6 digits)\n"
        "/signals — recent trade signals\n"
        "/update — cached session update\n"
        "/status — data freshness\n"
        "/help — this message\n\n"
        "Mac off? Deploy cloud/Dockerfile to Railway/Render."
    )
    send_message(msg)
    return msg


def dispatch(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None

    if text.startswith("/start") or text.startswith("/help"):
        return handle_help()
    if text.startswith("/signals"):
        return handle_signals()
    if text.startswith("/status"):
        return handle_status()
    if text.startswith("/update"):
        return handle_update_cached()
    if text.startswith("/otp"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /otp 482913"
        return handle_otp(parts[1].strip())
    if OTP_RE.match(text):
        return handle_otp(text)

    return "Unknown command. Send /help or a 6-digit OTP."


def poll_loop(offset: int = 0) -> None:
    token = bot_token()
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    logging.info("Telegram bot polling started")

    while True:
        try:
            resp = requests.get(
                url,
                params={"offset": offset, "timeout": 50},
                timeout=60,
            )
            resp.raise_for_status()
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue

                chat_id = message["chat"]["id"]
                text = message.get("text", "")

                if not is_authorized_chat(chat_id):
                    logging.warning("Ignored message from unauthorized chat %s", chat_id)
                    continue

                logging.info("Message: %s", text[:20])
                reply = dispatch(text)
                if reply and not reply.startswith("✅") and not reply.startswith("❌"):
                    send_message(reply)

        except Exception:
            logging.exception("Poll error")
            time.sleep(5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bank Nifty Telegram bot")
    parser.add_argument("--once", action="store_true", help="Process pending and exit (for testing)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging()
    load_dotenv(PROJECT_ROOT / ".env")

    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env", file=sys.stderr)
        return 1

    send_message("🟢 Bank Nifty bot started")
    poll_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
