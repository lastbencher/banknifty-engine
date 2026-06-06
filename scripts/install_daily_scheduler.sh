#!/usr/bin/env bash
# Schedule update_pipeline.py daily at 16:00 Asia/Kolkata (after 15:30 market close).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON="$PROJECT_ROOT/venv/bin/python"
UPDATE_SCRIPT="$PROJECT_ROOT/update_pipeline.py"
LOG_DIR="$PROJECT_ROOT/logs"

if [[ ! -x "$PYTHON" ]]; then
  echo "error: venv python not found at $PYTHON" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"

CRON_MARKER="banknifty_engine/update_pipeline.py"
CRON_LINE="0 16 * * * TZ=Asia/Kolkata cd $PROJECT_ROOT && $PYTHON $UPDATE_SCRIPT >> $LOG_DIR/cron.log 2>&1 # $CRON_MARKER"

# Replace any previous entry for this pipeline
EXISTING="$(crontab -l 2>/dev/null | grep -vF "$CRON_MARKER" || true)"
{ echo "$EXISTING"; echo "$CRON_LINE"; } | sed '/^$/d' | crontab -

echo "Cron job installed (16:00 Asia/Kolkata daily)"
echo "  $CRON_LINE"
echo ""
echo "Logs : $LOG_DIR/daily_update.log  (+ $LOG_DIR/cron.log)"
echo "Now  : $PYTHON $UPDATE_SCRIPT"
echo "List : crontab -l | grep banknifty"
echo "Remove: crontab -l | grep -vF '$CRON_MARKER' | crontab -"
