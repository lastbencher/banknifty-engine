"""Definedge WebSocket tick feed — updates the forming 1-min bar from live ticks."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

TickHandler = Callable[[float, datetime], None]


def lookup_token(conn, exchange: str, trading_symbol: str) -> str:
    for symbol in conn.symbols:
        if symbol.get("segment") == exchange and symbol.get("trading_symbol") == trading_symbol:
            return str(symbol["token"])
    raise RuntimeError(f"Token not found for {exchange}/{trading_symbol}")


def parse_tick_ltp(tick: dict) -> float | None:
    for key in ("lp", "ltp", "LTP", "c", "last_price", "last_traded_price"):
        value = tick.get(key)
        if value is not None and value != "":
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def parse_tick_time(tick: dict) -> datetime:
    for key in ("ft", "datetime", "ts", "time"):
        raw = tick.get(key)
        if not raw:
            continue
        for fmt in ("%d%m%Y%H%M%S", "%Y-%m-%d %H:%M:%S", "%H:%M:%S"):
            try:
                parsed = datetime.strptime(str(raw), fmt)
                if parsed.year == 1900:
                    today = datetime.now(IST).date()
                    parsed = parsed.replace(year=today.year, month=today.month, day=today.day)
                return parsed.replace(tzinfo=None)
            except ValueError:
                continue
    return datetime.now(IST).replace(tzinfo=None)


class TickFeed:
    """Background Definedge tick stream for one symbol."""

    def __init__(self, conn, exchange: str, trading_symbol: str, on_tick: TickHandler) -> None:
        self.conn = conn
        self.exchange = exchange
        self.trading_symbol = trading_symbol
        self.on_tick = on_tick
        self._thread: threading.Thread | None = None
        self._token: str | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._token = lookup_token(self.conn, self.exchange, self.trading_symbol)
        self._thread = threading.Thread(target=self._run, name="definedge-tick-feed", daemon=True)
        self._thread.start()
        logging.info(
            "WebSocket tick feed starting — %s/%s token=%s",
            self.exchange,
            self.trading_symbol,
            self._token,
        )

    def _run(self) -> None:
        from integrate import IntegrateWebSocket

        ws = IntegrateWebSocket(self.conn)
        token = self._token
        assert token is not None

        def on_login(iws) -> None:
            logging.info("WebSocket logged in — subscribing ticks")
            iws.subscribe(
                iws.c2i.SUBSCRIPTION_TYPE_TICK,
                [(self.exchange, token)],
            )

        def on_tick_update(_iws, tick: dict) -> None:
            ltp = parse_tick_ltp(tick)
            if ltp is None:
                logging.debug("Tick without LTP: %s", tick)
                return
            self.on_tick(ltp, parse_tick_time(tick))

        def on_exception(_iws, exc: Exception) -> None:
            logging.error("WebSocket error: %s", exc)

        ws.on_login = on_login
        ws.on_tick_update = on_tick_update
        ws.on_exception = on_exception

        try:
            ws.connect()
        except Exception:
            logging.exception("WebSocket feed stopped")
