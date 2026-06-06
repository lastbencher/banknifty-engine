"""Telegram notifications for Bank Nifty pipeline."""
from __future__ import annotations

import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _credentials() -> tuple[str, str] | None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return None
    return token, chat_id


def send_message(text: str, *, parse_mode: str | None = None) -> bool:
    creds = _credentials()
    if not creds:
        logger.debug("Telegram not configured — skip notify")
        return False

    token, chat_id = creds
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4096]}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("Telegram send failed")
        return False


def is_authorized_chat(chat_id: int | str) -> bool:
    creds = _credentials()
    if not creds:
        return False
    return str(chat_id) == creds[1]
