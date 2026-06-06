#!/usr/bin/env bash
set -euo pipefail
cd /app

# Historical Kaggle base — download from GitHub data branch if missing.
if [[ ! -f banknifty_10y_clean.csv ]]; then
  echo "Fetching banknifty_10y_clean.csv from GitHub data branch..."
  TOKEN="${GITHUB_TOKEN:-}"
  REPO="${GITHUB_REPO:-lastbencher/banknifty-engine}"
  BRANCH="${GITHUB_DATA_BRANCH:-data}"
  if [[ -n "$TOKEN" ]]; then
    curl -fsSL -H "Authorization: token ${TOKEN}" \
      "https://raw.githubusercontent.com/${REPO}/${BRANCH}/latest/banknifty_10y_clean.csv.gz" \
      -o /tmp/base.csv.gz 2>/dev/null && gzip -dc /tmp/base.csv.gz > banknifty_10y_clean.csv || true
  fi
  if [[ ! -f banknifty_10y_clean.csv ]]; then
    echo "WARN: banknifty_10y_clean.csv missing — upload to data branch latest/ before first run"
  fi
fi

mkdir -p features live research/outputs logs
exec python telegram_bot.py
