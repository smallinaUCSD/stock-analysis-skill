#!/bin/zsh
# Turn on text alerts sent as iMessages from this Mac mini (free; no Twilio).
#
# Run it WITHOUT sudo, in Terminal on the Mac mini (or over Screen Sharing),
# from the account that is logged in on the screen and signed in to Messages:
#   ~/stock-analysis-skill/scripts/macmini/imessage_setup.sh +15551234567
# (the number is optional: yours, to get a test message).
#
# It installs a small helper that runs whenever that account is logged in and
# sends the site's texts through Messages. The first message makes macOS ask
# whether it may control Messages: click OK.
set -eu
if [[ "$(id -u)" == 0 ]]; then
  print "Run this without sudo, as the user signed in to Messages."; exit 1
fi
HERE="${0:A:h}"
SPOOL="/Users/Shared/smi-imessage"
DEST="$HOME/Library/Application Support/SMInvestments"
AGENT="$HOME/Library/LaunchAgents/com.stockskill.imessage.plist"

print ">> Checking that Messages is signed in to iMessage ..."
if ! /usr/bin/osascript -e 'tell application "Messages" to get (1st account whose service type = iMessage)' >/dev/null 2>&1; then
  cat <<EOF
!! Messages isn't signed in to iMessage on this account (or macOS asked for
   permission and it wasn't given). Open Messages > Settings > iMessage, sign
   in (a separate Apple ID just for the site is best, so texts don't come from
   your personal number), then run this again.
EOF
  exit 1
fi

print ">> Shared folder the site drops messages into: $SPOOL"
mkdir -p "$SPOOL/outbox" "$SPOOL/failed"
chgrp -R staff "$SPOOL" 2>/dev/null || true
chmod 2770 "$SPOOL" "$SPOOL/outbox" "$SPOOL/failed"   # this user + the site's user (both in "staff")

print ">> Installing the helper in $DEST"
mkdir -p "$DEST" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cp "$HERE/imessage_relay.sh" "$HERE/imessage_send.applescript" "$DEST/"
chmod +x "$DEST/imessage_relay.sh"
cat > "$AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.stockskill.imessage</string>
  <key>ProgramArguments</key><array><string>/bin/zsh</string><string>$DEST/imessage_relay.sh</string></array>
  <key>EnvironmentVariables</key><dict>
    <key>STOCKSKILL_IMESSAGE_DIR</key><string>$SPOOL</string>
    <key>IMESSAGE_APPLESCRIPT</key><string>$DEST/imessage_send.applescript</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/smi-imessage.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/smi-imessage.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/com.stockskill.imessage" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$AGENT"
sleep 3
if [[ -f "$SPOOL/heartbeat" ]]; then print ">> Helper running."; else print "!! Helper didn't start: see ~/Library/Logs/smi-imessage.log"; fi

if [[ -n "${1:-}" ]]; then
  if [[ ! "$1" =~ '^\+[1-9][0-9]{7,14}$' ]]; then print "!! Give the number like +15551234567"; exit 1; fi
  print ">> Sending a test message to $1. If macOS asks to let it control Messages, click OK."
  f="$SPOOL/outbox/test-$(date +%s).msg"
  print -r -- "$1" > "$f.tmp" && print -r -- "SM Investments: iMessage alerts are working." >> "$f.tmp" && mv "$f.tmp" "$f"
  for i in {1..20}; do [[ -f "$f" ]] || break; sleep 1; done
  if [[ -f "$f" ]]; then print "!! Not sent yet: approve the Messages prompt on the screen, then check your phone.";
  elif ls "$SPOOL"/failed/test-*.err >/dev/null 2>&1; then print "!! It failed:"; cat "$SPOOL"/failed/test-*.err;
  else print ">> Sent. Check your phone."; fi
fi
cat <<EOF

Done. Texts from the site now go out as iMessages from this Mac, as long as
this account stays logged in: turn on System Settings > Users & Groups >
"Automatically log in as" this account so it survives a restart.
iMessages only reach iPhones, iPads and Macs.
EOF
