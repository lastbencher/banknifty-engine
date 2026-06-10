#!/usr/bin/env python3
"""
Daily Bank Nifty data pipeline — Definedge fetch, master merge, feature rebuild.

Steps:
  1. Pull ~180 days of 1-min Nifty Bank bars from Definedge Integrate API
  2. Merge Kaggle history + Definedge tail → banknifty_master.csv
  3. Rebuild features/daily_features.csv, checkpoint_features.csv, event_features.csv

Schedule (macOS): ./scripts/install_daily_scheduler.sh  → 16:00 Asia/Kolkata daily
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv, set_key

from bnf_research.build import build_features, load_master

PROJECT_ROOT = Path(__file__).resolve().parent
OHLC_COLUMNS = ["datetime", "open", "high", "low", "close"]

KAGGLE_PATH = PROJECT_ROOT / "banknifty_10y_clean.csv"
DEFINEDGE_PATH = PROJECT_ROOT / "banknifty_180d.csv"
DEFINEDGE_MIRROR = PROJECT_ROOT / "banknifty.csv"
MASTER_PATH = PROJECT_ROOT / "banknifty_master.csv"
FEATURE_DIR = PROJECT_ROOT / "features"
LOG_DIR = PROJECT_ROOT / "logs"
ENV_PATH = PROJECT_ROOT / ".env"
AUTH_PENDING_PATH = PROJECT_ROOT / "live" / "auth_pending.json"

DEFAULT_LOOKBACK_DAYS = 180


def setup_logging(verbose: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "daily_update.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    out = df[OHLC_COLUMNS].copy()
    out["datetime"] = pd.to_datetime(out["datetime"])
    if out["datetime"].dt.tz is not None:
        out["datetime"] = out["datetime"].dt.tz_localize(None)
    out = (
        out.sort_values("datetime")
        .drop_duplicates(subset=["datetime"], keep="last")
        .reset_index(drop=True)
    )
    return out


def get_definedge_totp() -> str | None:
    """Resolve 2FA code for Definedge login. Returns None if session reuse is preferred."""
    secret = os.getenv("TOTP_SECRET", "").strip()
    if secret:
        try:
            import pyotp
        except ImportError as exc:
            raise RuntimeError(
                "TOTP_SECRET is set but pyotp is not installed. Run: pip install pyotp"
            ) from exc
        return pyotp.TOTP(secret.replace(" ", "")).now()

    totp = os.getenv("DEFINEDGE_TOTP", "").strip()
    if totp:
        return totp

    if sys.stdin.isatty():
        try:
            entered = input("Enter Definedge OTP/TOTP (6 digits): ").strip()
            if entered:
                return entered
        except (EOFError, KeyboardInterrupt):
            pass

    return None


def _save_session_keys(conn) -> None:
    uid, actid, api_key, ws_key = conn.get_session_keys()
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    set_key(ENV_PATH, "INTEGRATE_UID", uid)
    set_key(ENV_PATH, "INTEGRATE_ACTID", actid)
    set_key(ENV_PATH, "INTEGRATE_API_SESSION_KEY", api_key)
    set_key(ENV_PATH, "INTEGRATE_WS_SESSION_KEY", ws_key)
    logging.info("Definedge session keys saved to .env (valid ~24 hours)")


def complete_login_with_otp(otp: str) -> "ConnectToIntegrate":
    """Finish login using otp_token from scripts/request_definedge_otp.py."""
    import json
    from hashlib import sha256

    from integrate import ConnectToIntegrate

    load_dotenv(ENV_PATH)
    api_token = os.getenv("API_TOKEN", "").strip()
    api_secret = os.getenv("API_SECRET", "").strip()
    if not AUTH_PENDING_PATH.exists():
        raise RuntimeError("No pending OTP — run scripts/request_definedge_otp.py first")

    pending = json.loads(AUTH_PENDING_PATH.read_text(encoding="utf-8"))
    otp_token = pending["otp_token"]
    ac = sha256(f"{otp_token}{otp}{api_secret}".encode("utf-8")).hexdigest()

    conn = ConnectToIntegrate()
    resp = conn.send_request(
        route_prefix=conn.login_url,
        route="token",
        method="POST",
        json_params={"otp_token": otp_token, "otp": otp, "ac": ac},
    )
    conn.set_session_keys(resp["uid"], resp["actid"], resp["api_session_key"], resp["susertoken"])
    _save_session_keys(conn)
    AUTH_PENDING_PATH.unlink(missing_ok=True)
    next(conn.symbols)
    logging.info("Definedge login complete (pending OTP flow)")
    return conn


def connect_definedge():
    """Connect using cached session keys, or login with external TOTP."""
    load_dotenv(ENV_PATH)

    api_token = os.getenv("API_TOKEN")
    api_secret = os.getenv("API_SECRET")
    if not api_token or not api_secret:
        raise RuntimeError(
            "Missing API_TOKEN or API_SECRET in .env — required for Definedge fetch."
        )

    from integrate import ConnectToIntegrate

    conn = ConnectToIntegrate()
    uid = os.getenv("INTEGRATE_UID", "").strip()
    actid = os.getenv("INTEGRATE_ACTID", "").strip()
    api_key = os.getenv("INTEGRATE_API_SESSION_KEY", "").strip()
    ws_key = os.getenv("INTEGRATE_WS_SESSION_KEY", "").strip()

    if uid and actid and api_key and ws_key:
        logging.info("Trying cached Definedge session keys")
        conn.set_session_keys(uid, actid, api_key, ws_key)
        # Ensure allmaster.csv is downloaded (required for symbol token lookup)
        try:
            next(conn.symbols)
        except StopIteration:
            pass
        return conn

    totp = get_definedge_totp()
    if not totp:
        raise RuntimeError(
            "Definedge login required. Either:\n"
            "  1. Set TOTP_SECRET in .env (External TOTP — best for daily cron), or\n"
            "  2. Run once with DEFINEDGE_TOTP=123456 to cache session keys for ~24h"
        )

    logging.info("Logging in to Definedge with external TOTP")
    conn.login(api_token=api_token, api_secret=api_secret, totp=totp)
    _save_session_keys(conn)
    return conn


def fetch_definedge(*, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> pd.DataFrame:
    from integrate import IntegrateData

    conn = connect_definedge()
    data = IntegrateData(conn)

    start = datetime.now() - timedelta(days=lookback_days)
    end = datetime.now()

    logging.info("Fetching Definedge NSE Nifty Bank minute bars %s → %s", start.date(), end.date())
    try:
        candles = list(
            data.historical_data(
                exchange="NSE",
                trading_symbol="Nifty Bank",
                timeframe="minute",
                start=start,
                end=end,
            )
        )
    except Exception as exc:
        if "Session Expired" not in str(exc):
            raise
        logging.warning("Definedge session expired — re-login")
        totp = get_definedge_totp()
        if not totp:
            raise RuntimeError(
                "Session expired. Set TOTP_SECRET for automatic re-login."
            ) from exc
        conn.login(
            api_token=os.getenv("API_TOKEN"),
            api_secret=os.getenv("API_SECRET"),
            totp=totp,
        )
        _save_session_keys(conn)
        data = IntegrateData(conn)
        candles = list(
            data.historical_data(
                exchange="NSE",
                trading_symbol="Nifty Bank",
                timeframe="minute",
                start=start,
                end=end,
            )
        )

    if not candles:
        raise RuntimeError("Definedge returned no candles.")

    df = normalize_ohlc(pd.DataFrame(candles))
    logging.info(
        "Definedge fetch complete: %s rows, %s → %s",
        len(df),
        df["datetime"].min(),
        df["datetime"].max(),
    )
    return df


def merge_master(kaggle_path: Path, definedge: pd.DataFrame) -> pd.DataFrame:
    if not kaggle_path.exists():
        raise FileNotFoundError(f"Kaggle base file not found: {kaggle_path}")

    kg = normalize_ohlc(pd.read_csv(kaggle_path))
    dd = normalize_ohlc(definedge)

    logging.info("Kaggle  : %s rows, ends %s", len(kg), kg["datetime"].max())
    logging.info("Definedge tail: %s rows, %s → %s", len(dd), dd["datetime"].min(), dd["datetime"].max())

    master = pd.concat([kg, dd], ignore_index=True)
    master = normalize_ohlc(master)

    logging.info(
        "Master merged: %s rows, %s → %s, %s sessions",
        len(master),
        master["datetime"].min(),
        master["datetime"].max(),
        master["datetime"].dt.date.nunique(),
    )
    return master


def rebuild_features(master_path: Path, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    logging.info("Rebuilding features from %s", master_path)
    master = load_master(master_path)
    daily, checkpoints, events = build_features(master)

    output_dir.mkdir(parents=True, exist_ok=True)
    daily.to_csv(output_dir / "daily_features.csv", index=False)
    checkpoints.to_csv(output_dir / "checkpoint_features.csv", index=False)
    events.to_csv(output_dir / "event_features.csv", index=False)

    logging.info(
        "Features saved → daily=%s checkpoint=%s event=%s",
        len(daily),
        len(checkpoints),
        len(events),
    )
    return daily, checkpoints, events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Bank Nifty data and rebuild features.")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Definedge fetch window (default: 180)",
    )
    parser.add_argument("--skip-fetch", action="store_true", help="Merge/rebuild only (use existing Definedge CSV)")
    parser.add_argument("--skip-features", action="store_true", help="Update master CSV only")
    parser.add_argument(
        "--skip-futures",
        action="store_true",
        help="Skip NFO futures fetch (volume/OI master)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(verbose=args.verbose)

    logging.info("=" * 60)
    logging.info("Bank Nifty daily update started")

    try:
        if args.skip_fetch:
            if not DEFINEDGE_PATH.exists():
                raise FileNotFoundError(f"No Definedge file at {DEFINEDGE_PATH}; run without --skip-fetch")
            definedge = normalize_ohlc(pd.read_csv(DEFINEDGE_PATH))
            logging.info("Skipped fetch; using %s", DEFINEDGE_PATH)
        else:
            definedge = fetch_definedge(lookback_days=args.lookback_days)
            definedge.to_csv(DEFINEDGE_PATH, index=False)
            definedge.to_csv(DEFINEDGE_MIRROR, index=False)
            logging.info("Saved %s and %s", DEFINEDGE_PATH.name, DEFINEDGE_MIRROR.name)

        master = merge_master(KAGGLE_PATH, definedge)
        master.to_csv(MASTER_PATH, index=False)
        logging.info("Saved %s", MASTER_PATH.name)

        if not args.skip_futures:
            try:
                from bnf_research.futures_data import update_futures_master

                fut = update_futures_master(
                    lookback_days=args.lookback_days,
                    skip_fetch=args.skip_fetch,
                )
                logging.info("Futures master updated — last bar %s", fut["datetime"].max())
            except Exception as fut_exc:
                logging.warning("Futures update failed (index update OK): %s", fut_exc)

        if not args.skip_features:
            rebuild_features(MASTER_PATH, FEATURE_DIR)

        logging.info("Daily update finished OK — last bar %s", master["datetime"].max())
        try:
            from telegram_notify import send_message

            send_message(f"✅ EOD update OK\nLast bar: {master['datetime'].max()}")
            if args.skip_features:
                scripts = PROJECT_ROOT / "scripts"
                if str(scripts) not in sys.path:
                    sys.path.insert(0, str(scripts))
                from cloud_post_update import run_post_update

                for line in run_post_update():
                    if line.strip():
                        send_message(line)
        except Exception:
            pass
        return 0

    except Exception as exc:
        logging.exception("Daily update failed")
        try:
            from telegram_notify import send_message

            send_message(f"❌ EOD update failed\n{type(exc).__name__}: {exc}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
