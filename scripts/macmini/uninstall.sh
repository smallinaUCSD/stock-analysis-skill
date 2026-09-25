#!/usr/bin/env bash
# Stop and remove the always-on services:   sudo ./scripts/macmini/uninstall.sh
# (Leaves the repo, your data and Tailscale itself in place.)
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo $0"; exit 1; }
for s in public private refresh; do
  launchctl bootout "system/com.stockskill.$s" 2>/dev/null && echo "  stopped $s"
  rm -f "/Library/LaunchDaemons/com.stockskill.$s.plist"
done
TS="$(command -v tailscale || echo /opt/homebrew/bin/tailscale)"
if [ -x "$TS" ]; then "$TS" funnel --https=443 off 2>/dev/null; "$TS" serve --https=8443 off 2>/dev/null; echo "  unpublished from Tailscale"; fi
