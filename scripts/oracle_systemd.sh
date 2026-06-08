#!/usr/bin/env bash
# Optional: install systemd unit so bot starts on VM reboot.
# Run once on Oracle VM after oracle_vm_bootstrap.sh
set -euo pipefail

INSTALL_DIR="${BNF_INSTALL_DIR:-$HOME/banknifty-engine}"
USER_NAME="$(whoami)"

sudo tee /etc/systemd/system/bnf-bot.service >/dev/null <<EOF
[Unit]
Description=Bank Nifty Telegram Bot (Docker Compose)
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=${USER_NAME}
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose -f cloud/docker-compose.yml up -d
ExecStop=/usr/bin/docker compose -f cloud/docker-compose.yml down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable bnf-bot.service
sudo systemctl start bnf-bot.service
echo "systemd unit bnf-bot.service enabled"
