#!/usr/bin/env bash
# Install all daily schedulers: live session @ 09:10, EOD archive @ 16:00 IST.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/install_live_scheduler.sh"
"$SCRIPT_DIR/install_daily_scheduler.sh"

echo ""
echo "All schedulers installed. Current crontab:"
crontab -l | grep banknifty_engine || true
