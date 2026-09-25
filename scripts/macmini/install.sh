#!/usr/bin/env bash
# Make the board always-on on a dedicated Mac mini.
#
# Run ONCE from your ADMIN account, inside the repo the app user cloned:
#   sudo /Users/stockskill/stock-analysis-skill/scripts/macmini/install.sh [app-user]
#
# It installs three launchd services that start at boot (nobody needs to log
# in), restart themselves if they crash, and run as the app user (not root):
#   com.stockskill.public    the shared site          127.0.0.1:8787
#   com.stockskill.private   Holdings + Alerts (you)  127.0.0.1:8788
#   com.stockskill.refresh   price snapshot, weekdays 7:00 and 16:10 (Mac's local time)
# then keeps the Mac awake and, if Tailscale is installed, publishes:
#   public  -> https://<mac-name>.<tailnet>.ts.net        (anyone, via Funnel)
#   private -> https://<mac-name>.<tailnet>.ts.net:8443   (only your Tailscale devices)
# Safe to re-run: it replaces what it installed before.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo from your admin account:  sudo $0 ${1:-}"; exit 1
fi
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
APP_USER="${1:-$(stat -f %Su "$REPO")}"
if [ "$APP_USER" = "root" ] || ! id "$APP_USER" >/dev/null 2>&1; then
  echo "!! Pass the app's user name, e.g.: sudo $0 stockskill"; exit 1
fi
APP_HOME="$(dscl . -read "/Users/$APP_USER" NFSHomeDirectory | awk '{print $2}')"
if id -Gn "$APP_USER" | tr ' ' '\n' | grep -qx admin; then
  echo "!! Note: $APP_USER is an administrator. A standard (non-admin) user is safer."
fi
echo ">> Repo: $REPO"
echo ">> App user: $APP_USER ($APP_HOME)"

# --- checks -------------------------------------------------------------------
[ -f "$REPO/.env" ] || echo "!! No $REPO/.env yet: copy it over from your laptop (API keys). Continuing."
if ! sudo -u "$APP_USER" -H bash -lc "export PATH=\$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:\$PATH; command -v uv" >/dev/null; then
  echo "!! uv not found for $APP_USER. Install it (brew install uv, or"
  echo "   curl -LsSf https://astral.sh/uv/install.sh | sh as $APP_USER) and re-run."; exit 1
fi
echo ">> Installing Python dependencies as $APP_USER ..."
sudo -u "$APP_USER" -H bash -lc "cd '$REPO' && export PATH=\$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:\$PATH && (uv sync --frozen --group deploy -q || uv sync --group deploy -q)"
sudo -u "$APP_USER" mkdir -p "$REPO/logs"
chmod +x "$REPO/scripts/macmini/"*.sh "$REPO/scripts/"*.sh

# --- launchd services ---------------------------------------------------------
plist() {  # name mode extra-xml
  local name="$1" mode="$2" extra="$3" f="/Library/LaunchDaemons/com.stockskill.$1.plist"
  cat > "$f" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.stockskill.$name</string>
  <key>UserName</key><string>$APP_USER</string>
  <key>GroupName</key><string>staff</string>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>$REPO/scripts/macmini/run.sh</string><string>$mode</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>HOME</key><string>$APP_HOME</string>
    <key>LANG</key><string>en_US.UTF-8</string>
  </dict>
  <key>StandardOutPath</key><string>$REPO/logs/$name.log</string>
  <key>StandardErrorPath</key><string>$REPO/logs/$name.log</string>
$extra
</dict></plist>
EOF
  chown root:wheel "$f"; chmod 644 "$f"
  launchctl bootout "system/com.stockskill.$name" 2>/dev/null || true
  launchctl bootstrap system "$f"
  echo "   installed com.stockskill.$name"
}
SERVER='  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>15</integer>'
TIMES=""
for wd in 1 2 3 4 5; do
  for hm in "7 0" "16 10"; do
    set -- $hm
    TIMES="$TIMES<dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>$1</integer><key>Minute</key><integer>$2</integer></dict>"
  done
done
REFRESH="  <key>StartCalendarInterval</key><array>$TIMES</array>"

echo ">> Installing services ..."
plist public public "$SERVER"
plist private private "$SERVER"
plist refresh refresh "$REFRESH"

# --- stay awake, come back after a power cut -----------------------------------
echo ">> Power: never sleep, restart after power failure, wake for network"
pmset -a sleep 0 disksleep 0 autorestart 1 womp 1 powernap 0 >/dev/null
pmset -a displaysleep 10 >/dev/null

# --- wait for the app -----------------------------------------------------------
echo ">> Waiting for the app to answer (first start can take a minute) ..."
for port in 8787 8788; do
  ok=""
  for _ in $(seq 1 90); do
    if curl -fsS -m 3 "http://127.0.0.1:$port/healthz" >/dev/null 2>&1; then ok=1; break; fi
    sleep 2
  done
  if [ -n "$ok" ]; then echo "   127.0.0.1:$port is up"
  else echo "!! 127.0.0.1:$port didn't answer yet. See: tail -50 $REPO/logs/*.log"; fi
done

# --- Tailscale ------------------------------------------------------------------
TS="$(command -v tailscale || true)"
[ -z "$TS" ] && [ -x /opt/homebrew/bin/tailscale ] && TS=/opt/homebrew/bin/tailscale
if [ -z "$TS" ]; then
  cat <<'EOF'

>> Tailscale is not installed, so the site is only on this Mac for now.
   From your admin account (no sudo):   brew install tailscale
   then re-run this script.
EOF
  exit 0
fi
TSD="$(dirname "$TS")/tailscaled"
if ! "$TS" status >/dev/null 2>&1 && ! launchctl print system/com.tailscale.tailscaled >/dev/null 2>&1; then
  echo ">> Starting Tailscale as a system service (runs at boot)"
  "$TSD" install-system-daemon
  sleep 3
fi
if ! "$TS" status >/dev/null 2>&1; then
  echo ">> Sign this Mac into Tailscale: open the link below on any device"
  "$TS" up
fi
echo ">> Publishing: public site on Funnel, private copy to your devices only"
"$TS" funnel --bg 8787
"$TS" serve --bg --https=8443 http://127.0.0.1:8788
NAME="$("$TS" status --json 2>/dev/null | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)"
cat <<EOF

  ============================================================
   Done. The board is always on.

   Public site (share it):   https://$NAME
   Your private copy:        https://$NAME:8443
      (Holdings + Alerts; opens only on devices signed into your
       Tailscale account, e.g. your laptop and phone)

   Check on it:   sudo $REPO/scripts/macmini/status.sh
   Update code:   sudo $REPO/scripts/macmini/update.sh
  ============================================================
EOF
