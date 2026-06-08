#!/usr/bin/env bash
# Bootstrap Bank Nifty Telegram bot on Oracle Cloud Always Free VM (Ubuntu ARM).
#
# BEFORE running this script — in Oracle Cloud Console:
#   1. Create account: https://cloud.oracle.com (card required for ID check; stay on Always Free)
#   2. Region: ap-mumbai-1 (Mumbai — closest to NSE / Definedge)
#   3. Compute → Instances → Create
#      - Name: bnf-bot
#      - Image: Ubuntu 22.04 or 24.04 (aarch64)
#      - Shape: VM.Standard.A1.Flex → 2 OCPU, 12 GB RAM (Always Free eligible)
#      - Assign public IPv4
#      - Download SSH private key (.pem)
#   4. Networking → Security List → Ingress: allow TCP 22 from your IP
#   5. SSH in:  ssh -i ~/Downloads/ssh-key-*.pem ubuntu@<PUBLIC_IP>
#   6. Run:     curl -fsSL ... | bash   OR clone repo and run this script
#
set -euo pipefail

REPO_URL="${BNF_REPO_URL:-https://github.com/lastbencher/banknifty-engine.git}"
INSTALL_DIR="${BNF_INSTALL_DIR:-$HOME/banknifty-engine}"

echo "==> Bank Nifty Oracle VM bootstrap"

if [[ $EUID -eq 0 ]]; then
  echo "Run as ubuntu user, not root (script uses sudo where needed)."
  exit 1
fi

echo "==> Install Docker"
sudo apt-get update -qq
sudo apt-get install -y -qq git curl ca-certificates
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  echo "Docker installed. You may need to log out/in for group membership."
fi

echo "==> Clone or update repo"
if [[ -d "$INSTALL_DIR/.git" ]]; then
  git -C "$INSTALL_DIR" pull --ff-only origin main
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

echo "==> Configure .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo ""
  echo "  Created $INSTALL_DIR/.env — edit it now with your secrets:"
  echo "    nano $INSTALL_DIR/.env"
  echo ""
  echo "  Required: API_TOKEN, API_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID"
  echo "  Recommended: GITHUB_TOKEN, GITHUB_REPO, GITHUB_DATA_BRANCH"
  echo ""
  read -r -p "Press Enter after you've saved .env ..." _
fi

if ! grep -qE '^TELEGRAM_BOT_TOKEN=.+$' .env 2>/dev/null; then
  echo "ERROR: TELEGRAM_BOT_TOKEN not set in .env"
  exit 1
fi

echo "==> Build and start bot container"
if groups | grep -q docker; then
  docker compose -f cloud/docker-compose.yml up -d --build
else
  sudo docker compose -f cloud/docker-compose.yml up -d --build
fi

PUBLIC_IP="$(curl -fsSL -4 ifconfig.me 2>/dev/null || curl -fsSL -4 icanhazip.com 2>/dev/null || true)"

echo ""
echo "============================================"
echo "  Bot is running on Oracle VM"
echo "============================================"
echo "  Install dir:  $INSTALL_DIR"
echo "  Public IP:    ${PUBLIC_IP:-unknown — check Oracle Console}"
echo ""
echo "  NEXT: Whitelist this IP on Definedge → API Config"
echo ""
echo "  Test on Telegram:  /help   /status"
echo ""
echo "  Logs:   docker compose -f cloud/docker-compose.yml logs -f"
echo "  Stop:   docker compose -f cloud/docker-compose.yml down"
echo "  Update: git pull && docker compose -f cloud/docker-compose.yml up -d --build"
echo "============================================"
