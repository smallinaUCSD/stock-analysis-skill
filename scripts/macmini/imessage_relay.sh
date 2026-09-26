#!/bin/zsh
# Sends the site's text messages as iMessages from this Mac.
#
# The website runs as a background service, and macOS doesn't let background
# services control Messages, so the site drops each message into a shared
# folder and this relay (a LaunchAgent in the logged-in user's session, the
# one signed in to Messages) sends it. Installed by imessage_setup.sh.
#
# Each message is one file, <spool>/outbox/<id>.msg: the number on line 1, the
# text after it. Sent files are deleted (no copies of messages are kept);
# failures go to <spool>/failed/ with the error, and are removed after 7 days.
# The relay touches <spool>/heartbeat so the site knows it's running.
#   imessage_relay.sh [--once]
set -u
SPOOL="${STOCKSKILL_IMESSAGE_DIR:-/Users/Shared/smi-imessage}"
OSA="${OSASCRIPT:-/usr/bin/osascript}"
HERE="${0:A:h}"
SCRIPT="${IMESSAGE_APPLESCRIPT:-$HERE/imessage_send.applescript}"
mkdir -p "$SPOOL/outbox" "$SPOOL/failed" 2>/dev/null

run_once() {
  touch "$SPOOL/heartbeat"
  local f num body err
  for f in "$SPOOL"/outbox/*.msg(N); do
    num="$(head -n 1 "$f")"
    body="$(tail -n +2 "$f")"
    if [[ ! "$num" =~ '^\+[1-9][0-9]{7,14}$' ]]; then
      mv "$f" "$SPOOL/failed/" && print "bad number" > "$SPOOL/failed/${f:t}.err"
      continue
    fi
    if err="$("$OSA" "$SCRIPT" "$num" "$body" 2>&1)"; then
      rm -f "$f"
    else
      mv "$f" "$SPOOL/failed/" && print -r -- "$err" > "$SPOOL/failed/${f:t}.err"
    fi
  done
  find "$SPOOL/failed" -type f -mtime +7 -delete 2>/dev/null
}

if [[ "${1:-}" == "--once" ]]; then
  run_once
  exit 0
fi
while true; do
  run_once
  sleep 2
done
