"""Bank Nifty futures OHLCV+OI — fetch, normalize, merge."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FUTURES_COLUMNS = ["datetime", "open", "high", "low", "close", "volume", "oi"]
FUTURES_MASTER_PATH = PROJECT_ROOT / "banknifty_futures_master.csv"
FUTURES_TAIL_PATH = PROJECT_ROOT / "banknifty_futures_180d.csv"
SEED_10D_PATH = PROJECT_ROOT / "banknifty_10d.csv"

DEFAULT_LOOKBACK_DAYS = 180
DEFAULT_EXCHANGE = "NFO"


def normalize_futures(df: pd.DataFrame) -> pd.DataFrame:
    """Keep OHLCV+OI; coerce types and dedupe by datetime."""
    missing = [c for c in FUTURES_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Futures frame missing columns: {missing}")

    out = df[FUTURES_COLUMNS].copy()
    out["datetime"] = pd.to_datetime(out["datetime"])
    if out["datetime"].dt.tz is not None:
        out["datetime"] = out["datetime"].dt.tz_localize(None)

    for col in ("open", "high", "low", "close"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype("int64")
    out["oi"] = pd.to_numeric(out["oi"], errors="coerce").fillna(0).astype("int64")

    out = (
        out.dropna(subset=["open", "high", "low", "close"])
        .sort_values("datetime")
        .drop_duplicates(subset=["datetime"], keep="last")
        .reset_index(drop=True)
    )
    return out


def load_futures_master(path: Path | None = None) -> pd.DataFrame:
    path = path or FUTURES_MASTER_PATH
    if not path.exists():
        return pd.DataFrame(columns=FUTURES_COLUMNS)
    return normalize_futures(pd.read_csv(path))


def merge_futures(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return normalize_futures(incoming)
    combined = pd.concat([existing, incoming], ignore_index=True)
    return normalize_futures(combined)


def seed_from_10d() -> pd.DataFrame:
    if not SEED_10D_PATH.exists():
        return pd.DataFrame(columns=FUTURES_COLUMNS)
    logging.info("Seeding futures master from %s", SEED_10D_PATH.name)
    return normalize_futures(pd.read_csv(SEED_10D_PATH))


def parse_contract_expiry(expiry_str: str) -> datetime:
    return datetime.strptime(str(expiry_str).strip(), "%d%m%Y")


def list_banknifty_futures_contracts(conn) -> list[dict[str, Any]]:
    """Active NFO BANKNIFTY index futures from Definedge allmaster."""
    contracts: list[dict[str, Any]] = []
    for symbol in conn.symbols:
        if (
            symbol.get("segment") == DEFAULT_EXCHANGE
            and symbol.get("symbol") == "BANKNIFTY"
            and symbol.get("instrument_type") == "FUTIDX"
        ):
            contracts.append(
                {
                    "trading_symbol": symbol["trading_symbol"],
                    "expiry": parse_contract_expiry(symbol["expiry"]),
                    "token": symbol.get("token"),
                }
            )
    return sorted(contracts, key=lambda c: c["expiry"])


def _pick_front_month(rows: pd.DataFrame) -> pd.DataFrame:
    """Keep front-month contract bar when multiple contracts overlap."""
    if rows.empty or "_expiry" not in rows.columns:
        return rows

    work = rows.copy()
    work["_bar_date"] = work["datetime"].dt.date
    work = work.sort_values(["datetime", "_expiry"])
    # Front month = nearest expiry on or after bar date
    work["_expiry_date"] = work["_expiry"].dt.date
    valid = work[work["_expiry_date"] >= work["_bar_date"]]
    if valid.empty:
        valid = work
    picked = valid.drop_duplicates(subset=["datetime"], keep="first")
    return picked[FUTURES_COLUMNS]


def fetch_definedge_futures(
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    exchange: str = DEFAULT_EXCHANGE,
) -> pd.DataFrame:
    """Pull minute bars with volume/OI; stitch active monthly contracts."""
    from integrate import IntegrateData

    from update_pipeline import _save_session_keys, connect_definedge, get_definedge_totp

    conn = connect_definedge()
    contracts = list_banknifty_futures_contracts(conn)
    if not contracts:
        raise RuntimeError("No NFO BANKNIFTY FUTIDX contracts found in Definedge allmaster.")

    data = IntegrateData(conn)
    start = datetime.now() - timedelta(days=lookback_days)
    end = datetime.now()

    logging.info(
        "Fetching Definedge NFO BANKNIFTY futures %s → %s (%s contracts)",
        start.date(),
        end.date(),
        len(contracts),
    )

    def _pull_contract(trading_symbol: str) -> list:
        return list(
            data.historical_data(
                exchange=exchange,
                trading_symbol=trading_symbol,
                timeframe="minute",
                start=start,
                end=end,
            )
        )

    def _fetch_all() -> pd.DataFrame:
        chunks: list[pd.DataFrame] = []
        for contract in contracts:
            sym = contract["trading_symbol"]
            try:
                candles = _pull_contract(sym)
            except Exception as exc:
                logging.warning("Contract %s fetch failed: %s", sym, exc)
                continue
            if not candles:
                logging.info("Contract %s: no rows", sym)
                continue
            chunk = pd.DataFrame(candles)
            chunk["_expiry"] = contract["expiry"]
            chunk["_symbol"] = sym
            chunks.append(chunk)
            logging.info(
                "Contract %s: %s rows, %s → %s",
                sym,
                len(chunk),
                chunk["datetime"].min(),
                chunk["datetime"].max(),
            )

        if not chunks:
            return pd.DataFrame(columns=FUTURES_COLUMNS)

        combined = pd.concat(chunks, ignore_index=True)
        combined["datetime"] = pd.to_datetime(combined["datetime"])
        picked = _pick_front_month(combined)
        return normalize_futures(picked)

    try:
        df = _fetch_all()
    except Exception as exc:
        if "Session Expired" not in str(exc):
            raise
        logging.warning("Definedge session expired — re-login for futures fetch")
        totp = get_definedge_totp()
        if not totp:
            raise RuntimeError("Session expired. Set TOTP_SECRET for automatic re-login.") from exc
        import os

        conn.login(
            api_token=os.getenv("API_TOKEN"),
            api_secret=os.getenv("API_SECRET"),
            totp=totp,
        )
        _save_session_keys(conn)
        contracts = list_banknifty_futures_contracts(conn)
        data = IntegrateData(conn)
        df = _fetch_all()

    if df.empty:
        raise RuntimeError("Definedge futures fetch returned no candles.")

    logging.info(
        "Futures fetch complete: %s rows, %s → %s, vol>0=%s",
        len(df),
        df["datetime"].min(),
        df["datetime"].max(),
        (df["volume"] > 0).sum(),
    )
    return df


def update_futures_master(
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    skip_fetch: bool = False,
    master_path: Path | None = None,
) -> pd.DataFrame:
    """Fetch tail, merge with existing master (seed from 10d if empty), save."""
    master_path = master_path or FUTURES_MASTER_PATH

    if skip_fetch:
        if not FUTURES_TAIL_PATH.exists():
            raise FileNotFoundError(f"No futures tail at {FUTURES_TAIL_PATH}; run without --skip-fetch")
        tail = normalize_futures(pd.read_csv(FUTURES_TAIL_PATH))
        logging.info("Skipped futures fetch; using %s", FUTURES_TAIL_PATH.name)
    else:
        tail = fetch_definedge_futures(lookback_days=lookback_days)
        tail.to_csv(FUTURES_TAIL_PATH, index=False)
        logging.info("Saved %s", FUTURES_TAIL_PATH.name)

    existing = load_futures_master(master_path)
    if existing.empty:
        existing = seed_from_10d()

    master = merge_futures(existing, tail)
    master.to_csv(master_path, index=False)
    logging.info(
        "Futures master saved: %s rows, %s → %s, %s sessions",
        len(master),
        master["datetime"].min(),
        master["datetime"].max(),
        master["datetime"].dt.date.nunique(),
    )
    return master
