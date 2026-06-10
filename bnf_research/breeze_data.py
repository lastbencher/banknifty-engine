"""ICICI Direct Breeze API — session + Bank Nifty futures history."""
from __future__ import annotations

import logging
import os
import re
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from bnf_research.futures_data import FUTURES_COLUMNS, normalize_futures

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"

BREEZE_STOCK_CODE = "CNXBAN"
BREEZE_EXCHANGE = "NFO"
LOGIN_BASE = "https://api.icicidirect.com/apiuser/login"


def _clean_credential(value: str) -> str:
    """Strip whitespace and optional quotes from .env values."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def breeze_credentials() -> tuple[str, str]:
    api_key = _clean_credential(os.getenv("BREEZE_API_KEY", ""))
    api_secret = _clean_credential(os.getenv("BREEZE_API_SECRET", ""))
    if not api_key or not api_secret:
        raise RuntimeError("BREEZE_API_KEY and BREEZE_API_SECRET required in .env")
    return api_key, api_secret


def login_url(api_key: str | None = None) -> str:
    """
    Breeze login URL with URL-encoded api_key.

    ICICI keys often contain @, %, +, etc. — must encode for the query string.
    See: https://www.icicidirect.com/futures-and-options/articles/what-is-a-session-key
    """
    key = _clean_credential(api_key or breeze_credentials()[0])
    # quote (not plus) keeps @ as %40; safe='' encodes all special chars
    encoded = urllib.parse.quote(key, safe="")
    return f"{LOGIN_BASE}?api_key={encoded}"


def parse_session_token(value: str) -> str:
    """Accept raw token or full redirect URL with apisession= / API_Session."""
    value = value.strip()
    if "apisession=" in value.lower() or "api_session=" in value.lower():
        qs = urllib.parse.urlparse(value).query
        params = urllib.parse.parse_qs(qs)
        for key in ("apisession", "API_Session", "api_session", "session_token"):
            if key in params:
                return params[key][0]
        # case-insensitive
        for k, v in params.items():
            if k.lower() in {"apisession", "api_session", "session_token"} and v:
                return v[0]
    return value


def _ensure_ssl_certs() -> None:
    try:
        import certifi

        bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
    except ImportError:
        pass


def connect_breeze(session_token: str | None = None):
    """Return authenticated BreezeConnect client."""
    _ensure_ssl_certs()
    from breeze_connect import BreezeConnect

    api_key, api_secret = breeze_credentials()
    token = (session_token or os.getenv("BREEZE_SESSION_TOKEN", "")).strip()
    if not token:
        raise RuntimeError(
            "No Breeze session. Run: ./venv/bin/python scripts/setup_breeze_auth.py"
        )

    breeze = BreezeConnect(api_key=api_key)
    breeze.generate_session(api_secret=api_secret, session_token=token)
    return breeze


def _market_time_iso(dt: datetime) -> str:
    """Breeze from/to dates use IST wall time with a Z suffix (not UTC)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _expiry_to_breeze_iso(exp: date) -> str:
    """Breeze F&O expiry param — use 07:00 UTC on expiry calendar date (ICICI docs)."""
    return f"{exp.isoformat()}T07:00:00.000Z"


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Last occurrence of weekday (Mon=0 … Thu=3 … Tue=1) in month."""
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    cursor = nxt - timedelta(days=1)
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    return cursor


def _bnf_monthly_expiry(year: int, month: int) -> date:
    """
    Bank Nifty monthly futures expiry.

    NSE moved BANKNIFTY to last Tuesday from the Sep-2025 expiry cycle onward;
    earlier months use last Thursday.
    """
    if (year, month) >= (2025, 9):
        return _last_weekday_of_month(year, month, 1)  # Tuesday
    return _last_weekday_of_month(year, month, 3)  # Thursday


def _monthly_expiries(start: date, end: date) -> list[date]:
    expiries: list[date] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        exp = _bnf_monthly_expiry(cursor.year, cursor.month)
        if start - timedelta(days=60) <= exp <= end + timedelta(days=60):
            expiries.append(exp)
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return expiries


def _iter_trading_days(from_date: datetime, to_date: datetime):
    cursor = from_date.date()
    end = to_date.date()
    while cursor <= end:
        if cursor.weekday() < 5:
            yield cursor
        cursor += timedelta(days=1)


def _candles_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=FUTURES_COLUMNS)

    out = pd.DataFrame(rows)
    out["datetime"] = pd.to_datetime(out["datetime"])
    out = out.rename(columns={"open_interest": "oi"})
    for col in ("open", "high", "low", "close", "volume", "oi"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return normalize_futures(out[FUTURES_COLUMNS])


def fetch_historical_futures(
    breeze,
    *,
    from_date: datetime,
    to_date: datetime,
    expiry: date,
) -> pd.DataFrame:
    """One contract expiry, 1-minute bars (day-chunked — Breeze caps ~1000 bars/call)."""
    expiry_iso = _expiry_to_breeze_iso(expiry)
    chunks: list[pd.DataFrame] = []

    for day in _iter_trading_days(from_date, to_date):
        day_start = datetime.combine(day, datetime.min.time()).replace(hour=9, minute=15)
        day_end = datetime.combine(day, datetime.min.time()).replace(hour=15, minute=30)
        if day_start < from_date:
            day_start = from_date
        if day_end > to_date:
            day_end = to_date
        if day_start >= day_end:
            continue

        payload = breeze.get_historical_data_v2(
            interval="1minute",
            from_date=_market_time_iso(day_start),
            to_date=_market_time_iso(day_end),
            stock_code=BREEZE_STOCK_CODE,
            exchange_code=BREEZE_EXCHANGE,
            product_type="futures",
            expiry_date=expiry_iso,
            right="others",
            strike_price="0",
        )
        if not isinstance(payload, dict):
            continue
        if payload.get("Error"):
            logging.warning("Breeze error expiry %s %s: %s", expiry, day, payload["Error"])
            continue
        df = _candles_to_df(payload.get("Success") or [])
        if not df.empty:
            chunks.append(df)

    if not chunks:
        return pd.DataFrame(columns=FUTURES_COLUMNS)
    return normalize_futures(pd.concat(chunks, ignore_index=True))


def fetch_breeze_futures_range(
    *,
    lookback_days: int = 180,
    session_token: str | None = None,
) -> pd.DataFrame:
    """Stitch monthly Bank Nifty futures from Breeze across lookback window."""
    breeze = connect_breeze(session_token)
    end = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
    start = end - timedelta(days=lookback_days)

    expiries = _monthly_expiries(start.date(), end.date())
    chunks: list[pd.DataFrame] = []

    for exp in expiries:
        # contract active ~2 months before expiry
        contract_start = max(start, datetime.combine(exp - timedelta(days=45), datetime.min.time()))
        contract_end = min(
            end,
            datetime.combine(exp, datetime.min.time()).replace(hour=15, minute=30),
        )
        if contract_start >= contract_end:
            continue

        logging.info("Breeze fetch CNXBAN exp %s: %s → %s", exp, contract_start.date(), contract_end.date())
        try:
            df = fetch_historical_futures(
                breeze,
                from_date=contract_start.replace(hour=9, minute=15),
                to_date=contract_end,
                expiry=exp,
            )
        except Exception as exc:
            logging.warning("Breeze contract %s failed: %s", exp, exc)
            continue

        if not df.empty:
            df["_expiry"] = exp
            chunks.append(df)
            logging.info("  → %s rows", len(df))

    if not chunks:
        return pd.DataFrame(columns=FUTURES_COLUMNS)

    combined = pd.concat(chunks, ignore_index=True)
    combined = combined.sort_values(["datetime", "_expiry"])
    combined = combined.drop_duplicates(subset=["datetime"], keep="first")
    return normalize_futures(combined[FUTURES_COLUMNS])
