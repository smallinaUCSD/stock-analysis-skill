#!/usr/bin/env bash
# Started by launchd (see install.sh), not by hand. Runs one copy of the app in
# the foreground so launchd can restart it if it ever exits.
#
#   run.sh public    the shared site (no Holdings/Alerts), port 8787
#   run.sh private   your own copy (Holdings + Alerts), port 8788, never exposed
#   run.sh refresh   bring the price snapshot up to date, then exit
set -euo pipefail
cd "$(dirname "$0")/../.."

# launchd starts with a bare environment: find uv (Homebrew or the uv installer)
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
. scripts/load_env.sh
[ -f .env ] && load_env

export STOCKSKILL_TICKERS="${STOCKSKILL_TICKERS:-data/tickers.csv}"
export STOCKSKILL_CACHE_DIR="${STOCKSKILL_CACHE_DIR:-data/cache}"
export STOCKSKILL_PERIOD="${STOCKSKILL_PERIOD:-5y}"
export STOCKSKILL_CACHE_TTL="${STOCKSKILL_CACHE_TTL:-2592000}"
export STOCKSKILL_ADDED_FILE="${STOCKSKILL_ADDED_FILE:-data/added.json}"
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES     # gunicorn + macOS fork safety

case "${1:-}" in
  public)
    export STOCKSKILL_PUBLIC=1 STOCKSKILL_AUTH=1 STOCKSKILL_ALERTS=0 FINNHUB_PER_MIN=35 PORT=8787 ;;
  private)
    export STOCKSKILL_PUBLIC=0 STOCKSKILL_ALERTS=1 FINNHUB_PER_MIN=20 PORT=8788 ;;
  refresh)
    # keep each log to its last 5,000 lines (rewritten in place: the servers
    # still hold these files open)
    for f in logs/*.log; do
      if [ -f "$f" ] && [ "$(wc -l < "$f")" -gt 5000 ]; then
        tail -n 5000 "$f" > "$f.tmp"; cat "$f.tmp" > "$f"; rm -f "$f.tmp"
      fi
    done
    echo "$(date '+%F %T') refresh start"
    REFRESH_TTL="${REFRESH_TTL:-3600}" ./scripts/refresh_data.sh
    echo "$(date '+%F %T') refresh done"
    exit 0 ;;
  *) echo "usage: $0 public|private|refresh" >&2; exit 2 ;;
esac

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "$(date '+%F %T') port $PORT is already in use; retrying shortly:"
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN
  sleep 30; exit 1
fi
# gunicorn lives in the "deploy" dependency group (a plain `uv sync` removes it)
uv sync --frozen --group deploy -q 2>/dev/null || uv sync --group deploy -q
echo "$(date '+%F %T') starting $1 on 127.0.0.1:$PORT"
# 127.0.0.1 only: nothing on your network reaches it directly; Tailscale does
exec uv run gunicorn -w 1 -k gthread --threads 8 -t 120 --graceful-timeout 20 \
  -b "127.0.0.1:$PORT" 'stockskill.server:create_app()'
