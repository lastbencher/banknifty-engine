#!/usr/bin/env bash
# Start live_session.py at 09:10 IST on weekdays (before 09:15 open).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$PROJECT_ROOT/venv/bin/python"
LIVE_SCRIPT="$PROJECT_ROOT/live_session.py"
LOG_DIR="$PROJECT_ROOT/live"

mkdir -p "$LOG_DIR"

CRON_MARKER="banknifty_engine/live_session.py"
# Mon–Fri 09:10 IST; live_session.py exits after 15:30
CRON_LINE="10 9 * * 1-5 TZ=Asia/Kolkata cd $PROJECT_ROOT && $PYTHON $LIVE_SCRIPT >> $LOG_DIR/cron.log 2>&1 # $CRON_MARKER"

EXISTING="$(crontab -l 2>/dev/null | grep -vF "$CRON_MARKER" || true)"
{ echo "$EXISTING"; echo "$CRON_LINE"; } | sed '/^$/d' | crontab -

echo "Live session cron installed — starts 09:10 IST Mon–Fri"
echo "  $CRON_LINE"
echo ""
echo "Manual: $PYTHON $LIVE_SCRIPT"
echo "Snapshot: $PYTHON $LIVE_SCRIPT --once"
