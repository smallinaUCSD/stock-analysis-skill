#!/usr/bin/env bash
# Is everything running?   sudo ./scripts/macmini/status.sh
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
for s in public private refresh; do
  if out=$(launchctl print "system/com.stockskill.$s" 2>/dev/null); then
    state=$(echo "$out" | awk -F'= ' '/^\tstate =/{print $2; exit}')
    runs=$(echo "$out" | awk -F'= ' '/^\truns =/{print $2; exit}')
    code=$(echo "$out" | awk -F'= ' '/last exit code =/{print $2; exit}')
    printf "  %-8s %-12s runs=%-4s last exit=%s\n" "$s" "${state:-?}" "${runs:-0}" "${code:-n/a}"
  else
    printf "  %-8s NOT INSTALLED\n" "$s"
  fi
done
for port in 8787 8788; do
  if curl -fsS -m 3 "http://127.0.0.1:$port/healthz" >/dev/null 2>&1; then echo "  :$port answering"; else echo "  :$port NOT answering"; fi
done
TS="$(command -v tailscale || echo /opt/homebrew/bin/tailscale)"
if [ -x "$TS" ]; then echo; "$TS" serve status 2>/dev/null || echo "  tailscale: not connected"; fi
for s in public private refresh; do
  f="$REPO/logs/$s.log"
  [ -f "$f" ] && { echo; echo "  Last lines of $s.log:"; tail -4 "$f" | sed 's/^/    /'; }
done
echo "  Logs: $REPO/logs/"
