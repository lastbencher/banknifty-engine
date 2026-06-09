"""Download latest/ snapshots from the GitHub data branch into the workspace."""
from __future__ import annotations

import gzip
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "banknifty_10y_clean.csv.gz",
    "banknifty_master.csv.gz",
    "banknifty_180d.csv.gz",
]


def main() -> None:
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN", "")
    repo = os.getenv("GITHUB_REPO", "lastbencher/banknifty-engine")
    branch = os.getenv("GITHUB_DATA_BRANCH", "data")
    base = f"https://raw.githubusercontent.com/{repo}/{branch}/latest"

    for name in FILES:
        dest = ROOT / name.replace(".gz", "")
        url = f"{base}/{name}"
        headers = {"Authorization": f"token {token}"} if token else {}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read()
            dest.write_bytes(gzip.decompress(raw) if name.endswith(".gz") else raw)
            print(f"synced {dest.name} ({dest.stat().st_size // 1024 // 1024}MB)")
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Failed to fetch {name}: HTTP {exc.code}") from exc


if __name__ == "__main__":
    main()
