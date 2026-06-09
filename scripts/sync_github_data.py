"""Pull latest data snapshots from GitHub data branch into /app."""
from __future__ import annotations

import gzip
import os
import urllib.error
import urllib.request
from pathlib import Path

APP = Path("/app")
SYNC_FILES = [
    "banknifty_10y_clean.csv.gz",
    "banknifty_master.csv.gz",
    "banknifty_180d.csv.gz",
    "features/daily_features.csv.gz",
    "features/checkpoint_features.csv.gz",
    "features/event_features.csv.gz",
    "research/outputs/latest_signals.csv",
]


def main(force: bool = False) -> None:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        print("GITHUB_TOKEN not set — skip GitHub data sync")
        return

    repo = os.getenv("GITHUB_REPO", "lastbencher/banknifty-engine")
    branch = os.getenv("GITHUB_DATA_BRANCH", "data")
    base = f"https://raw.githubusercontent.com/{repo}/{branch}/latest"

    for name in SYNC_FILES:
        dest = APP / name.replace(".gz", "")
        if not force and dest.exists() and dest.stat().st_size > 0:
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{base}/{name}"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read()
            if name.endswith(".gz"):
                dest.write_bytes(gzip.decompress(raw))
            else:
                dest.write_bytes(raw)
            print(f"synced {dest.relative_to(APP)} ({dest.stat().st_size // 1024 // 1024}MB)")
        except urllib.error.HTTPError as exc:
            print(f"skip {name}: HTTP {exc.code}")
        except Exception as exc:
            print(f"skip {name}: {exc}")


if __name__ == "__main__":
    import sys

    main(force="--force" in sys.argv)
