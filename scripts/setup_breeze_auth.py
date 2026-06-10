#!/usr/bin/env python3
"""ICICI Breeze login — save session token to .env for API access."""
from __future__ import annotations

import argparse
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Event

from dotenv import load_dotenv, set_key

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

ENV_PATH = PROJECT_ROOT / ".env"

# ICICI sends session via POST form field API_Session (or GET apisession=)
_TOKEN_KEYS = (
    "API_Session",
    "apisession",
    "api_session",
    "session_token",
    "APISession",
)


def _token_from_params(params: dict[str, list[str]]) -> str:
    for key in _TOKEN_KEYS:
        if key in params and params[key][0].strip():
            return params[key][0].strip()
    # case-insensitive fallback
    lower = {k.lower(): v for k, v in params.items()}
    for key in ("api_session", "apisession", "session_token"):
        if key in lower and lower[key][0].strip():
            return lower[key][0].strip()
    return ""


class _CallbackHandler(BaseHTTPRequestHandler):
    token_event: Event = Event()
    captured_token: str = ""

    def _capture_token(self) -> str:
        qs = urllib.parse.urlparse(self.path).query
        token = _token_from_params(urllib.parse.parse_qs(qs))
        if token:
            return token

        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > 0:
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            token = _token_from_params(urllib.parse.parse_qs(body))
            if token:
                return token
            # sometimes single value without standard parsing
            for part in body.split("&"):
                if "=" in part:
                    k, _, v = part.partition("=")
                    if k.strip().lower() in {"api_session", "apisession"} and v.strip():
                        return urllib.parse.unquote_plus(v.strip())
        return ""

    def _respond(self, token: str) -> None:
        if not token and _CallbackHandler.captured_token:
            token = _CallbackHandler.captured_token

        if token:
            _CallbackHandler.captured_token = token
            _CallbackHandler.token_event.set()
            body = b"<html><body><h2>Breeze login OK</h2><p>Session saved. You can close this tab.</p></body></html>"
            self.send_response(200)
        else:
            body = (
                b"<html><body><h2>No session token found</h2>"
                b"<p>Check browser DevTools Network tab for API_Session, then run:<br>"
                b"<code>setup_breeze_auth.py --session TOKEN</code></p></body></html>"
            )
            self.send_response(400)

        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._respond(self._capture_token())

    def do_POST(self) -> None:
        self._respond(self._capture_token())

    def do_HEAD(self) -> None:
        token = self._capture_token() or _CallbackHandler.captured_token
        self.send_response(200 if token else 400)
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Breeze API session setup")
    parser.add_argument(
        "--session",
        help="Session token or full redirect URL (skip browser flow)",
    )
    parser.add_argument("--port", type=int, default=8765, help="Local callback port")
    parser.add_argument("--test", action="store_true", help="Verify session with a small API call")
    return parser.parse_args()


def save_token(token: str) -> None:
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    set_key(ENV_PATH, "BREEZE_SESSION_TOKEN", token)
    print(f"Saved BREEZE_SESSION_TOKEN to {ENV_PATH}")


def main() -> int:
    args = parse_args()
    load_dotenv(ENV_PATH)

    from bnf_research.breeze_data import _clean_credential, login_url, parse_session_token

    api_key = _clean_credential(__import__("os").getenv("BREEZE_API_KEY", ""))
    if not api_key:
        print("Missing BREEZE_API_KEY in .env", file=sys.stderr)
        print("Copy API Key from ICICI → View Apps → BankNiftyLegend (no quotes)", file=sys.stderr)
        return 1

    if args.session:
        token = parse_session_token(args.session)
        save_token(token)
    else:
        url = login_url(api_key)
        print("\n1. Copy the FULL URL below into your browser (must include api_key=…):\n", flush=True)
        print(url, flush=True)
        print(f"\n2. After login, ICICI redirects to http://127.0.0.1:{args.port}/callback — waiting…\n", flush=True)

        try:
            import subprocess

            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("(Opened login page in your default browser.)\n", flush=True)
        except Exception:
            pass

        server = HTTPServer(("127.0.0.1", args.port), _CallbackHandler)
        server.timeout = 1
        _CallbackHandler.token_event.clear()
        _CallbackHandler.captured_token = ""

        import time

        deadline = time.time() + 300
        while time.time() < deadline:
            server.handle_request()
            if _CallbackHandler.token_event.is_set():
                break

        if not _CallbackHandler.captured_token:
            print(
                "Timed out. In Chrome DevTools → Network → 127.0.0.1 → Payload → API_Session:\n"
                "  ./venv/bin/python scripts/setup_breeze_auth.py --session 'YOUR_API_SESSION'",
                file=sys.stderr,
            )
            return 1

        save_token(_CallbackHandler.captured_token)

    if args.test:
        load_dotenv(ENV_PATH, override=True)
        from bnf_research.breeze_data import connect_breeze

        breeze = connect_breeze()
        print("Session OK — Breeze client initialized")
        _ = breeze  # noqa: F841

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
