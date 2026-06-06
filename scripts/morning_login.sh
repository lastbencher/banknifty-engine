#!/usr/bin/env bash
# Login with SMS OTP (no External TOTP needed). Session keys last ~24 hours.
#
# Usage:
#   ./scripts/morning_login.sh              # prompts for 6-digit code
#   ./scripts/morning_login.sh 482913       # pass OTP directly
#
# After login, same-day cron jobs (09:10 live, 16:00 update) use cached session keys.
# Re-run this each morning until External TOTP is enabled on Definedge.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$PROJECT_ROOT/venv/bin/python"

if [[ $# -ge 1 ]]; then
  exec "$PYTHON" "$PROJECT_ROOT/scripts/setup_definedge_auth.py" --otp "$1" --test-only
fi

echo "Request OTP on your Definedge-registered mobile, then enter the 6-digit code."
read -r -p "SMS OTP: " OTP
exec "$PYTHON" "$PROJECT_ROOT/scripts/setup_definedge_auth.py" --otp "$OTP" --test-only
