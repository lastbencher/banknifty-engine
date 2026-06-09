"""Post-update tasks for cloud bot — publish data branch and optional GHA rebuild."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def skip_features_mode() -> bool:
    return os.getenv("BNF_SKIP_FEATURES", "").strip().lower() in {"1", "true", "yes"}


def run_post_update() -> list[str]:
    """Return status lines for Telegram (empty on total skip)."""
    from publish_to_github import export_latest_signals, format_signals_telegram, publish_data_branch
    from trigger_github_pipeline import trigger_pipeline

    lines: list[str] = []
    if skip_features_mode():
        gh_msg = publish_data_branch()
        if gh_msg:
            lines.append(gh_msg)
        lines.append(trigger_pipeline())
        lines.append("Features + signals rebuilding on GitHub (~10–15 min). Send /sync later.")
        return lines

    try:
        export_latest_signals()
        lines.append(format_signals_telegram())
    except Exception as exc:
        lines.append(f"Signal export failed: {exc}")

    gh_msg = publish_data_branch()
    if gh_msg and "skipped" not in gh_msg.lower():
        lines.append(gh_msg)
    return lines


if __name__ == "__main__":
    for line in run_post_update():
        print(line)
