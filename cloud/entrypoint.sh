#!/usr/bin/env bash
set -euo pipefail
cd /app

mkdir -p features live research/outputs logs
python scripts/sync_github_data.py

exec python telegram_bot.py
