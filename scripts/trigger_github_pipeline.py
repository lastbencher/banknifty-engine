"""Trigger the cloud-pipeline GitHub Actions workflow (RAM-heavy rebuild on GHA runners)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

WORKFLOW_FILE = "cloud-pipeline.yml"


def trigger_pipeline(*, ref: str = "main") -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPO", "lastbencher/banknifty-engine").strip()
    if not token:
        return "GITHUB_TOKEN not set — skipped pipeline trigger"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # repository_dispatch works with classic PAT `repo` scope (no workflow scope).
    dispatch_url = f"https://api.github.com/repos/{repo}/dispatches"
    body = json.dumps({"event_type": "rebuild-data", "client_payload": {"ref": ref}}).encode()
    req = urllib.request.Request(dispatch_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in {200, 204}:
                return f"GitHub Actions: rebuild queued ({WORKFLOW_FILE})"
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            detail = exc.read().decode(errors="ignore")[:300]
            return f"GitHub dispatch failed HTTP {exc.code}: {detail}"

    # Fallback: workflow_dispatch (needs PAT with workflow scope).
    wf_url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    body = json.dumps({"ref": ref}).encode()
    req = urllib.request.Request(wf_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30):
            return f"GitHub Actions: workflow_dispatch queued ({WORKFLOW_FILE})"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="ignore")[:300]
        return f"GitHub pipeline trigger failed HTTP {exc.code}: {detail}"


if __name__ == "__main__":
    print(trigger_pipeline())
