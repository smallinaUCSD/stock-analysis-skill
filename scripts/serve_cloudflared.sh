#!/usr/bin/env bash
# Run the PUBLIC stock board on your Mac and expose it with a Cloudflare Tunnel.
#
# Use this if ngrok is blocked on your network (TLS handshake fails). Cloudflare
# tunnels are outbound-only to Cloudflare's edge, so ISPs/firewalls rarely block
# them. The "quick tunnel" needs NO account and NO token.
#
# One-time setup:
#   1. cp .env.example .env   and paste your keys (from the Render dashboard)
#   2. brew install cloudflared
#
# Then just:  ./scripts/serve_cloudflared.sh        (uses port 8787)
# Or pick a port:  PORT=8899 ./scripts/serve_cloudflared.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8787}"

if [ -f .env ]; then
  set -a; . ./.env; set +a
else
  echo "!! No .env found. Copy .env.example to .env and add your keys first."
  echo "   (Without keys it still runs, using yfinance for data.)"
fi

if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "!! Port ${PORT} is already in use:"
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN
  echo "   Stop that process, or run on another port:  PORT=8899 $0"
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "!! cloudflared is not installed.  Install it with:  brew install cloudflared"
  exit 1
fi

export STOCKSKILL_PUBLIC=1
export STOCKSKILL_TICKERS="${STOCKSKILL_TICKERS:-data/tickers.csv}"
export STOCKSKILL_CACHE_DIR="${STOCKSKILL_CACHE_DIR:-data/cache}"
export STOCKSKILL_PERIOD="${STOCKSKILL_PERIOD:-5y}"
export STOCKSKILL_CACHE_TTL="${STOCKSKILL_CACHE_TTL:-2592000}"
export STOCKSKILL_ADDED_FILE="${STOCKSKILL_ADDED_FILE:-data/added.json}"

# Bring the data snapshot up to today (fast, yfinance) unless told to skip.
if [ -z "${SKIP_REFRESH:-}" ]; then
  ./scripts/refresh_data.sh || echo "!! data refresh failed; using the existing snapshot"
fi

echo ">> Starting the board on http://127.0.0.1:${PORT} ..."
uv run gunicorn -w 1 -k gthread --threads 8 -t 120 \
  -b "127.0.0.1:${PORT}" 'stockskill.server:create_app()' &
SERVER_PID=$!

cleanup() {
  echo; echo ">> Stopping server..."
  pkill -P "$SERVER_PID" 2>/dev/null || true
  kill "$SERVER_PID" 2>/dev/null || true
  lsof -nP -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
  if curl -fsS -m 2 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then break; fi
  sleep 1
done

echo ">> Opening a Cloudflare quick tunnel. Share the https://<name>.trycloudflare.com"
echo "   URL it prints below. (Press Ctrl-C to stop both the tunnel and the server.)"
cloudflared tunnel --url "http://localhost:${PORT}"
