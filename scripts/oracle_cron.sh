#!/usr/bin/env bash
# Install cron on Oracle VM for unattended EOD updates (Mon–Fri 16:05 IST).
# Run once after oracle_vm_bootstrap.sh on the VM host (not inside container).
set -euo pipefail

INSTALL_DIR="${BNF_INSTALL_DIR:-$HOME/banknifty-engine}"
CONTAINER="${BNF_CONTAINER:-bnf-telegram-bot}"
CRON_LINE="5 16 * * 1-5 cd ${INSTALL_DIR} && /usr/bin/docker exec ${CONTAINER} python update_pipeline.py --skip-features >> ${INSTALL_DIR}/live/cron_update.log 2>&1"

( crontab -l 2>/dev/null | grep -v "update_pipeline.py --skip-features" || true
  echo "${CRON_LINE}"
) | crontab -

echo "Cron installed (16:05 IST Mon–Fri):"
crontab -l | grep update_pipeline || true
echo ""
echo "After each run the bot publishes master to GitHub and triggers Actions rebuild."
echo "Send /sync on Telegram ~15 min later to pull fresh features."
