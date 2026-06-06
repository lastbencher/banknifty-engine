#!/usr/bin/env bash
# Keep Telegram bot running (launchd) for remote OTP + notifications.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$PROJECT_ROOT/venv/bin/python"
BOT="$PROJECT_ROOT/telegram_bot.py"
LOG_DIR="$PROJECT_ROOT/live"
PLIST_LABEL="com.banknifty.telegram-bot"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

mkdir -p "$LOG_DIR"

cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${BOT}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/telegram_bot.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/telegram_bot.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"

echo "Telegram bot installed (KeepAlive)"
echo "  $PLIST_DEST"
echo ""
echo "Add to .env:"
echo "  TELEGRAM_BOT_TOKEN=...   (from @BotFather)"
echo "  TELEGRAM_CHAT_ID=...     (from @userinfobot)"
echo ""
echo "Then from Telegram: /otp 482913"
echo "Logs: $LOG_DIR/telegram_bot.log"
