#!/usr/bin/env bash
# Pull the latest code from GitHub and restart:   sudo ./scripts/macmini/update.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo $0"; exit 1; }
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
APP_USER="$(stat -f %Su "$REPO")"
as_app() { sudo -u "$APP_USER" -H bash -lc "cd '$REPO' && export PATH=\$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:\$PATH && $1"; }
echo ">> Pulling as $APP_USER ..."
# the local price cache (daily refresh, market crawl) must not block the pull
as_app "bash scripts/macmini/pull.sh"
as_app "uv sync --frozen --group deploy -q || uv sync --group deploy -q"
echo ">> Restarting ..."
for s in public private; do launchctl kickstart -k "system/com.stockskill.$s"; done
launchctl kickstart "system/com.stockskill.refresh" || true
sleep 5
"$(dirname "$0")/status.sh"
