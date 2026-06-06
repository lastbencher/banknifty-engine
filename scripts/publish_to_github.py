"""Publish data snapshots to GitHub (data branch) for cloud / off-Mac access."""
from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")

load_dotenv(PROJECT_ROOT / ".env")

PUBLISH_FILES = [
    "banknifty_10y_clean.csv",
    "banknifty_180d.csv",
    "banknifty_master.csv",
    "features/daily_features.csv",
    "features/checkpoint_features.csv",
    "features/event_features.csv",
    "research/outputs/latest_signals.csv",
]

GZIP_THRESHOLD = 1_000_000  # 1 MB — keep under GitHub limits


def _git_env() -> dict[str, str]:
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "bnf-bot",
        "GIT_AUTHOR_EMAIL": "bot@local",
        "GIT_COMMITTER_NAME": "bnf-bot",
        "GIT_COMMITTER_EMAIL": "bot@local",
        "GIT_HTTP_MAX_REQUEST_BUFFER": "100M",
    }


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd, cwd=cwd, env=_git_env(), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git failed: {' '.join(cmd)}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def _prepare_repo(repo_dir: Path, branch: str, clone_url: str, work: Path) -> None:
    """Clone existing data branch or create a fresh orphan branch with data only."""
    shallow_data = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, clone_url, str(repo_dir)],
        cwd=work,
        capture_output=True,
        text=True,
    )
    if shallow_data.returncode == 0:
        return

    _run(["git", "clone", "--depth", "1", clone_url, str(repo_dir)], cwd=work)
    try:
        _run(["git", "fetch", "origin", f"{branch}:{branch}"], cwd=repo_dir)
        _run(["git", "checkout", branch], cwd=repo_dir)
        return
    except RuntimeError:
        pass

    _run(["git", "checkout", "--orphan", branch], cwd=repo_dir)
    for path in repo_dir.iterdir():
        if path.name == ".git":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def publish_data_branch() -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPO", "lastbencher/banknifty-engine").strip()
    if not token:
        return "GITHUB_TOKEN not set — skipped GitHub publish"

    branch = os.getenv("GITHUB_DATA_BRANCH", "data")
    stamp = datetime.now(IST).strftime("%Y-%m-%d_%H%M")
    work = Path(tempfile.mkdtemp(prefix="bnf_publish_"))
    repo_dir = work / "repo"
    clone_url = f"https://x-access-token:{token}@github.com/{repo}.git"

    try:
        _prepare_repo(repo_dir, branch, clone_url, work)

        snap_dir = repo_dir / "snapshots" / stamp
        snap_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        for rel in PUBLISH_FILES:
            src = PROJECT_ROOT / rel
            if not src.exists():
                continue
            if src.stat().st_size > GZIP_THRESHOLD:
                dest = snap_dir / f"{src.name}.gz"
                with open(src, "rb") as fin, gzip.open(dest, "wb") as fout:
                    shutil.copyfileobj(fin, fout)
            else:
                shutil.copy2(src, snap_dir / src.name)
            copied += 1

        latest = repo_dir / "latest"
        if latest.exists():
            shutil.rmtree(latest)
        shutil.copytree(snap_dir, latest)
        (repo_dir / "LATEST.txt").write_text(f"{stamp}\n", encoding="utf-8")
        (repo_dir / "README.txt").write_text(
            "Bank Nifty data snapshots for cloud bot. See latest/ for current files.\n",
            encoding="utf-8",
        )

        _run(["git", "add", "-A"], cwd=repo_dir)
        try:
            _run(["git", "commit", "-m", f"data snapshot {stamp}"], cwd=repo_dir)
        except RuntimeError as exc:
            if "nothing to commit" in str(exc):
                return "GitHub: no changes to publish"
            raise

        _run(["git", "config", "http.postBuffer", "524288000"], cwd=repo_dir)
        _run(["git", "push", "-u", "origin", f"HEAD:{branch}"], cwd=repo_dir)
        return f"GitHub: published {stamp} ({copied} files) → {repo}#{branch}"
    except RuntimeError as exc:
        return f"GitHub publish failed:\n{exc}"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def export_latest_signals() -> Path:
    from signal_engine.engine import SignalEngine

    out = PROJECT_ROOT / "research/outputs/latest_signals.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    engine = SignalEngine(bucket_mode="walkforward")
    end = datetime.now(IST).date()
    start = end - timedelta(days=5)
    signals = engine.scan_history(start_date=start, end_date=end)

    import pandas as pd

    rows = [
        {
            "date": s.date,
            "checkpoint_clock": s.checkpoint_clock,
            "rule_id": s.rule_id,
            "side": s.side,
            "confidence": s.confidence,
            "entry_price": s.entry_price,
            "target_50": s.target_50,
            "target_100": s.target_100,
            "required_break_direction": s.required_break_direction,
        }
        for s in signals
    ]
    pd.DataFrame(rows).to_csv(out, index=False)
    return out


def format_signals_telegram(max_rows: int = 8) -> str:
    path = PROJECT_ROOT / "research/outputs/latest_signals.csv"
    if not path.exists():
        return "No signals file yet."

    import pandas as pd

    df = pd.read_csv(path)
    if df.empty:
        return "No signals in last 5 sessions."

    df = df.sort_values(["date", "checkpoint_clock"], ascending=False).head(max_rows)
    lines = ["📡 Recent signals"]
    for _, row in df.iterrows():
        lines.append(
            f"{row['date']} {row['checkpoint_clock']} | {row['rule_id']} | "
            f"{row['side']} break {row['required_break_direction']} | conf {float(row['confidence']):.3f}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(publish_data_branch())
