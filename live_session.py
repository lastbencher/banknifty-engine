#!/usr/bin/env python3
"""
Live Bank Nifty session — intraday data flow during market hours.

  09:10 IST (cron)  →  auto-start, wait for open
  09:15–15:30 IST   →  WebSocket ticks update the forming 1-min bar (sub-minute)
                      + Definedge minute poll every ~60s for completed bars
  At each 3/5-min checkpoint  →  live features, views, and signals

    ./venv/bin/python live_session.py
    ./venv/bin/python live_session.py --once
    ./scripts/install_live_scheduler.sh   # Mon–Fri 09:10 IST
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from bnf_research.checkpoint_builder import build_checkpoint_rows
from bnf_research.config import ALL_CHECKPOINT_MINUTES, clock_label
from bnf_research.ib import ib_levels
from bnf_research.session import build_session_meta, compute_median_session_bars
from bnf_research.utils import classify_era
from live_tick_feed import TickFeed
from signal_engine.engine import SignalEngine
from signal_engine.features import (
    QUANTILE_SPECS,
    assign_quantile_bucket,
    count_bucket,
    direction,
    gap_state,
    pressure_bucket,
)
from signal_engine.models import TradeSignal
from update_pipeline import connect_definedge, normalize_ohlc
from view_engine import ViewEngine

PROJECT_ROOT = Path(__file__).resolve().parent
FEATURE_DIR = PROJECT_ROOT / "features"
LIVE_DIR = PROJECT_ROOT / "live"
IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)
PRE_OPEN = dt_time(9, 10)
DEFAULT_POLL_SECONDS = 60
SYMBOL = "Nifty Bank"
EXCHANGE = "NSE"


def setup_logging(verbose: bool = False) -> None:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LIVE_DIR / "live_session.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def now_ist() -> datetime:
    return datetime.now(IST)


def is_trading_day(day: date | None = None) -> bool:
    day = day or now_ist().date()
    return day.weekday() < 5


def is_market_hours(moment: datetime | None = None) -> bool:
    moment = moment or now_ist()
    if not is_trading_day(moment.date()):
        return False
    t = moment.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def minutes_from_session_open(moment: datetime, session_start: pd.Timestamp) -> int:
    m = moment.replace(tzinfo=None)
    s = pd.Timestamp(session_start).to_pydatetime().replace(tzinfo=None)
    return max(0, int((m - s).total_seconds() // 60))


def session_open_today(day: date) -> datetime:
    return datetime.combine(day, MARKET_OPEN, tzinfo=IST)


def wait_for_market_open() -> None:
    while is_trading_day() and now_ist().time() < MARKET_OPEN:
        logging.info("Waiting for market open (09:15 IST)...")
        time.sleep(5)


class LiveSessionEngine:
    def __init__(
        self,
        *,
        feature_dir: Path = FEATURE_DIR,
        bucket_mode: str = "walkforward",
        poll_seconds: int = DEFAULT_POLL_SECONDS,
        use_websocket: bool = True,
    ) -> None:
        self.feature_dir = feature_dir
        self.poll_seconds = poll_seconds
        self.use_websocket = use_websocket
        self.signal_engine = SignalEngine(
            feature_dir=feature_dir,
            bucket_mode=bucket_mode,  # type: ignore[arg-type]
        )
        self.view_engine = ViewEngine(feature_dir)
        self._daily: pd.DataFrame | None = None
        self._hist_checkpoints: pd.DataFrame | None = None
        self._median_bars: float = 375.0
        self._today_bars: pd.DataFrame = pd.DataFrame()
        self._forming: dict[str, Any] | None = None
        self._forming_minute: datetime | None = None
        self._last_tick_ltp: float | None = None
        self._last_tick_time: datetime | None = None
        self._tick_count: int = 0
        self._session_date: date | None = None
        self._emitted: set[int] = set()
        self._conn = None
        self._tick_feed: TickFeed | None = None

    def load_context(self) -> None:
        daily_path = self.feature_dir / "daily_features.csv"
        cp_path = self.feature_dir / "checkpoint_features.csv"
        if not daily_path.exists() or not cp_path.exists():
            raise FileNotFoundError(
                f"Run feature_factory.py or update_pipeline.py first — missing {self.feature_dir}"
            )

        self._daily = pd.read_csv(daily_path, parse_dates=["date"])
        self._hist_checkpoints = pd.read_csv(
            cp_path,
            parse_dates=["date", "checkpoint_time"],
            low_memory=False,
        )
        self._hist_checkpoints = self._hist_checkpoints.merge(
            self._daily[
                [
                    "date",
                    "rolling_20d_opposite_break_rate",
                    "rolling_20d_trend_day_rate",
                    "ib_bucket",
                ]
            ],
            on="date",
            how="left",
        )
        master_path = PROJECT_ROOT / "banknifty_master.csv"
        if master_path.exists():
            master = pd.read_csv(master_path, parse_dates=["datetime"])
            master["date"] = master["datetime"].dt.date
            self._median_bars = compute_median_session_bars(master)
        logging.info(
            "Context loaded — %s historical sessions, bucket reference ready",
            len(self._daily),
        )

    @property
    def daily(self) -> pd.DataFrame:
        if self._daily is None:
            self.load_context()
        assert self._daily is not None
        return self._daily

    @property
    def hist_checkpoints(self) -> pd.DataFrame:
        if self._hist_checkpoints is None:
            self.load_context()
        assert self._hist_checkpoints is not None
        return self._hist_checkpoints

    def start_tick_feed(self) -> None:
        if not self.use_websocket:
            return
        if self._conn is None:
            self._conn = connect_definedge()
        if self._tick_feed is None:
            self._tick_feed = TickFeed(
                self._conn,
                EXCHANGE,
                SYMBOL,
                on_tick=self.apply_tick,
            )
            self._tick_feed.start()

    def apply_tick(self, ltp: float, tick_time: datetime) -> None:
        self._last_tick_ltp = ltp
        self._last_tick_time = tick_time
        self._tick_count += 1

        minute_dt = tick_time.replace(second=0, microsecond=0)
        if self._forming_minute is None or minute_dt != self._forming_minute:
            self._forming_minute = minute_dt
            if not self._today_bars.empty and pd.Timestamp(self._today_bars.iloc[-1]["datetime"]) == minute_dt:
                last = self._today_bars.iloc[-1]
                self._forming = {
                    "datetime": minute_dt,
                    "open": float(last["open"]),
                    "high": max(float(last["high"]), ltp),
                    "low": min(float(last["low"]), ltp),
                    "close": ltp,
                }
            else:
                open_px = float(self._today_bars.iloc[-1]["close"]) if not self._today_bars.empty else ltp
                self._forming = {
                    "datetime": minute_dt,
                    "open": open_px,
                    "high": max(open_px, ltp),
                    "low": min(open_px, ltp),
                    "close": ltp,
                }
        else:
            assert self._forming is not None
            self._forming["high"] = max(float(self._forming["high"]), ltp)
            self._forming["low"] = min(float(self._forming["low"]), ltp)
            self._forming["close"] = ltp

        if self._tick_count % 50 == 0:
            logging.debug(
                "Tick #%s — %s LTP=%.2f (forming close=%.2f)",
                self._tick_count,
                minute_dt.strftime("%H:%M"),
                ltp,
                self._forming["close"],
            )

    def bars_with_forming(self) -> pd.DataFrame:
        if self._today_bars.empty and self._forming is None:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close"])

        bars = self._today_bars.copy()
        if self._forming is None:
            return bars

        forming_dt = pd.Timestamp(self._forming["datetime"])
        if bars.empty or pd.Timestamp(bars.iloc[-1]["datetime"]) < forming_dt:
            return pd.concat([bars, pd.DataFrame([self._forming])], ignore_index=True)

        if pd.Timestamp(bars.iloc[-1]["datetime"]) == forming_dt:
            bars = bars.copy()
            for col in ("open", "high", "low", "close"):
                bars.at[bars.index[-1], col] = self._forming[col]
        return bars

    def _fetch_today_bars(self, day: date) -> pd.DataFrame:
        from integrate import IntegrateData

        if self._conn is None:
            self._conn = connect_definedge()

        start = session_open_today(day).replace(tzinfo=None)
        end = min(now_ist(), datetime.combine(day, MARKET_CLOSE, tzinfo=IST)).replace(tzinfo=None)

        data = IntegrateData(self._conn)
        candles = list(
            data.historical_data(
                exchange=EXCHANGE,
                trading_symbol=SYMBOL,
                timeframe="minute",
                start=start,
                end=end,
            )
        )
        if not candles:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close"])

        df = normalize_ohlc(pd.DataFrame(candles))
        return df[df["datetime"].dt.date == day].copy()

    def refresh(self, day: date | None = None) -> pd.DataFrame:
        day = day or now_ist().date()
        self._session_date = day
        bars = self._fetch_today_bars(day)
        self._today_bars = bars

        if self._forming and not bars.empty:
            forming_dt = pd.Timestamp(self._forming["datetime"])
            if pd.Timestamp(bars.iloc[-1]["datetime"]) >= forming_dt:
                self._forming = None
                self._forming_minute = None

        merged = self.bars_with_forming()
        if not merged.empty:
            out_path = LIVE_DIR / f"today_{day.isoformat()}.csv"
            merged.to_csv(out_path, index=False)
            last = merged.iloc[-1]
            forming = " [forming]" if self._forming else ""
            logging.info(
                "Refreshed %s — %s bars%s, last %s @ %.2f",
                day,
                len(merged),
                forming,
                last["datetime"],
                last["close"],
            )
        else:
            logging.warning("No bars yet for %s", day)

        return merged

    def _live_daily_row(self, day: date, bars: pd.DataFrame) -> dict[str, Any]:
        prev = self.daily.sort_values("date").iloc[-1]
        session_open = float(bars.iloc[0]["open"])
        prev_close = float(prev["day_close"])
        gap = session_open - prev_close
        gap_dir = "UP" if gap > 0 else "DOWN" if gap < 0 else "FLAT"

        return {
            "date": day,
            "era": classify_era(day),
            "prev_high": float(prev["day_high"]),
            "prev_low": float(prev["day_low"]),
            "prev_close": prev_close,
            "gap_points": gap,
            "gap_pct": (gap / prev_close * 100) if prev_close else None,
            "gap_direction": gap_dir,
            "rolling_20d_opposite_break_rate": prev.get("rolling_20d_opposite_break_rate"),
            "rolling_20d_trend_day_rate": prev.get("rolling_20d_trend_day_rate"),
            "ib_bucket": prev.get("ib_bucket"),
        }

    def _build_checkpoint_row(self, minute: int) -> pd.Series | None:
        bars = self.bars_with_forming()
        if bars.empty or self._session_date is None:
            return None

        bars = bars.copy()
        bars["date"] = bars["datetime"].dt.date
        day = self._session_date
        meta = build_session_meta(day, bars, self._median_bars)
        daily_row = self._live_daily_row(day, bars)
        cp_rows = build_checkpoint_rows(meta, daily_row)
        match = [r for r in cp_rows if r["checkpoint_minute"] == minute]
        if not match or not match[0].get("is_valid_checkpoint"):
            return None

        row = pd.Series(match[0])
        ib = ib_levels(meta)
        row["ib_high"] = ib["ib_high"]
        row["ib_low"] = ib["ib_low"]
        row["ib_range"] = ib["ib_range"]

        hist = self.hist_checkpoints
        hist_minute = hist[hist["checkpoint_minute"] == minute].sort_values("date")
        for source, bucket in QUANTILE_SPECS:
            if source in row.index and source in hist_minute.columns:
                ref = hist_minute[source].dropna().tail(252)
                row[bucket] = assign_quantile_bucket(row.get(source), ref)

        row["opening_direction"] = direction(row.get("return_from_open_points"))
        row["opening_pressure"] = pressure_bucket(row.get("close_position_in_range_so_far"))
        row["trap_count_bucket"] = count_bucket(row.get("failed_break_count"))
        row["gap_state"] = gap_state(row)
        row["gap_direction"] = row.get("gap_direction") or daily_row.get("gap_direction") or "NONE"
        row["recent_opposite_rate_bucket"] = assign_quantile_bucket(
            daily_row.get("rolling_20d_opposite_break_rate"),
            hist_minute["rolling_20d_opposite_break_rate"].dropna().tail(252)
            if "rolling_20d_opposite_break_rate" in hist_minute.columns
            else pd.Series(dtype=float),
        )
        row["recent_trend_rate_bucket"] = assign_quantile_bucket(
            daily_row.get("rolling_20d_trend_day_rate"),
            hist_minute["rolling_20d_trend_day_rate"].dropna().tail(252)
            if "rolling_20d_trend_day_rate" in hist_minute.columns
            else pd.Series(dtype=float),
        )
        return row

    def due_checkpoints(self, moment: datetime | None = None) -> list[int]:
        moment = moment or now_ist()
        bars = self.bars_with_forming()
        if bars.empty:
            return []

        session_start = pd.Timestamp(bars.iloc[0]["datetime"])
        elapsed = minutes_from_session_open(moment, session_start)
        return [m for m in ALL_CHECKPOINT_MINUTES if m <= elapsed]

    def evaluate_minute(self, minute: int) -> tuple[pd.Series | None, list[TradeSignal]]:
        row = self._build_checkpoint_row(minute)
        if row is None:
            return None, []
        signals = self.signal_engine.evaluate_checkpoint(row, best_only=True)
        return row, signals

    def snapshot(self) -> dict[str, Any]:
        moment = now_ist()
        due = self.due_checkpoints(moment)
        latest_minute = due[-1] if due else None
        row, signals = self.evaluate_minute(latest_minute) if latest_minute else (None, [])

        views = []
        if self._session_date and not self.bars_with_forming().empty:
            try:
                views = self.view_engine.view_for_date(self._session_date)
            except Exception:
                logging.exception("View engine failed")

        bars = self.bars_with_forming()
        return {
            "time": moment,
            "bars": len(bars),
            "last_bar": bars.iloc[-1].to_dict() if not bars.empty else None,
            "forming_bar": self._forming,
            "last_tick_ltp": self._last_tick_ltp,
            "last_tick_time": self._last_tick_time,
            "tick_count": self._tick_count,
            "checkpoints_due": due,
            "latest_checkpoint": latest_minute,
            "latest_clock": clock_label(latest_minute) if latest_minute else None,
            "checkpoint_row": row.to_dict() if row is not None else None,
            "signals": signals,
            "views": views,
        }

    def process_new_checkpoints(self) -> list[tuple[int, list[TradeSignal]]]:
        fired: list[tuple[int, list[TradeSignal]]] = []
        for minute in self.due_checkpoints():
            if minute in self._emitted:
                continue
            row, signals = self.evaluate_minute(minute)
            if row is None:
                continue
            self._emitted.add(minute)
            fired.append((minute, signals))
            clock = clock_label(minute)
            tag = " (forming)" if self._forming else ""
            if signals:
                for sig in signals:
                    logging.info(
                        "SIGNAL %s @ %s (%sm)%s %s %s conf=%.3f",
                        sig.rule_id,
                        clock,
                        minute,
                        tag,
                        sig.side,
                        sig.required_break_direction,
                        sig.confidence,
                    )
            else:
                logging.info("Checkpoint %s (%sm)%s — no rule match", clock, minute, tag)
        return fired

    def run(self, *, continuous: bool = True) -> None:
        self.load_context()
        wait_for_market_open()

        if self.use_websocket:
            self.start_tick_feed()

        logging.info(
            "Live session started — WS=%s, poll=%ss",
            self.use_websocket,
            self.poll_seconds,
        )

        while True:
            if not is_trading_day():
                logging.info("Not a trading day — exiting")
                break

            if is_market_hours() or self.bars_with_forming().empty:
                try:
                    self.refresh()
                    self.process_new_checkpoints()
                except Exception:
                    logging.exception("Live refresh failed")
            elif not continuous:
                break

            if not continuous:
                break

            if not is_market_hours() and continuous and now_ist().time() > MARKET_CLOSE:
                logging.info("Session ended — update_pipeline.py archives at 16:00")
                break

            time.sleep(self.poll_seconds)


def print_snapshot(snap: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print(f"Live snapshot @ {snap['time'].strftime('%H:%M:%S IST')}")
    print("=" * 60)
    if snap["last_bar"]:
        bar = snap["last_bar"]
        print(f"Bars today : {snap['bars']}")
        print(f"Last bar   : {bar['datetime']} close={bar['close']:.2f}")
    else:
        print("No bars yet today")

    if snap.get("forming_bar"):
        fb = snap["forming_bar"]
        print(
            f"Forming    : {fb['datetime']} O={fb['open']:.2f} H={fb['high']:.2f} "
            f"L={fb['low']:.2f} C={fb['close']:.2f}"
        )
    if snap.get("last_tick_ltp") is not None:
        print(f"Last tick  : {snap['last_tick_ltp']:.2f} @ {snap.get('last_tick_time')}")

    if snap["latest_checkpoint"]:
        print(f"Checkpoint : {snap['latest_clock']} (+{snap['latest_checkpoint']}m)")

    if snap["signals"]:
        print("\nActive signals:")
        for sig in snap["signals"]:
            print(
                f"  {sig.rule_id} | {sig.side} | break {sig.required_break_direction} "
                f"| entry {sig.entry_price:.2f} | conf {sig.confidence:.3f}"
            )
    else:
        print("\nNo signals at latest checkpoint")

    if snap["views"]:
        latest_view = snap["views"][-1]
        print(
            f"\nView ({latest_view.layer} @ {latest_view.checkpoint_clock}): "
            f"{latest_view.bias} | trend {latest_view.trend_probability:.1%}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live Bank Nifty session feed")
    parser.add_argument("--once", action="store_true", help="Single refresh + snapshot, then exit")
    parser.add_argument("--poll", type=int, default=DEFAULT_POLL_SECONDS, help="Minute-bar poll interval")
    parser.add_argument("--no-ws", action="store_true", help="Disable WebSocket tick feed")
    parser.add_argument("--feature-dir", type=Path, default=FEATURE_DIR)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(verbose=args.verbose)

    engine = LiveSessionEngine(
        feature_dir=args.feature_dir,
        poll_seconds=args.poll,
        use_websocket=not args.no_ws,
    )

    try:
        if args.once:
            engine.load_context()
            if not args.no_ws:
                engine.start_tick_feed()
                time.sleep(3)
            engine.refresh()
            snap = engine.snapshot()
            engine.process_new_checkpoints()
            print_snapshot(snap)
            return 0

        engine.run(continuous=True)
        return 0
    except KeyboardInterrupt:
        logging.info("Stopped by user")
        return 0
    except Exception:
        logging.exception("Live session failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
