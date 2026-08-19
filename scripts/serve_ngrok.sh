#!/usr/bin/env bash
# Run the PUBLIC stock board on your own Mac and expose it with ngrok.
#
# Full CPU + your home IP (Yahoo is not blocked) = none of the free-tier crashes.
# The site is up only while this script runs and your Mac is awake.
#
# One-time setup:
#   1. cp .env.example .env   and paste your keys (from the Render dashboard)
#   2. brew install ngrok
#   3. sign up at ngrok.com (free), then:  ngrok config add-authtoken <your-token>
#
# Then just:  ./scripts/serve_ngrok.sh          (uses port 8787)
# Or pick a port:  PORT=8899 ./scripts/serve_ngrok.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8787}"

# Load .env (API keys) if present.
if [ -f .env ]; then
  set -a; . ./.env; set +a
else
  echo "!! No .env found. Copy .env.example to .env and add your keys first."
  echo "   (Without keys it still runs, using yfinance for data.)"
fi

# Refuse to start on a busy port (otherwise gunicorn spams "Address already in
# use"). Show what's on it so the fix is obvious.
if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "!! Port ${PORT} is already in use:"
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN
  echo "   Stop that process, or run on another port:  PORT=8899 $0"
  exit 1
fi

# Public mode + the committed data snapshot, matching the hosted config. Added
# tickers persist to a local JSON file (your disk is durable, no Upstash needed).
export STOCKSKILL_PUBLIC=1
export STOCKSKILL_TICKERS="${STOCKSKILL_TICKERS:-data/tickers.csv}"
export STOCKSKILL_CACHE_DIR="${STOCKSKILL_CACHE_DIR:-data/cache}"
export STOCKSKILL_PERIOD="${STOCKSKILL_PERIOD:-5y}"
export STOCKSKILL_CACHE_TTL="${STOCKSKILL_CACHE_TTL:-2592000}"
export STOCKSKILL_ADDED_FILE="${STOCKSKILL_ADDED_FILE:-data/added.json}"

echo ">> Starting the board on http://127.0.0.1:${PORT} ..."
uv run gunicorn -w 1 -k gthread --threads 8 -t 120 \
  -b "127.0.0.1:${PORT}" 'stockskill.server:create_app()' &
SERVER_PID=$!

# Clean shutdown: kill uv, its gunicorn children, and anything still holding the
# port (belt-and-suspenders, since we know the port was ours). Runs on Ctrl-C too.
cleanup() {
  echo; echo ">> Stopping server..."
  pkill -P "$SERVER_PID" 2>/dev/null || true
  kill "$SERVER_PID" 2>/dev/null || true
  lsof -nP -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Wait for it to answer before opening the tunnel.
for _ in $(seq 1 30); do
  if curl -fsS -m 2 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then break; fi
  sleep 1
done

if command -v ngrok >/dev/null 2>&1; then
  echo ">> Opening public ngrok tunnel. Share the https URL it prints below."
  echo "   (Press Ctrl-C to stop both the tunnel and the server.)"
  ngrok http "${PORT}"
else
  echo
  echo "!! ngrok is not installed. The board is live locally at:"
  echo "     http://127.0.0.1:${PORT}"
  echo "   To share it publicly:  brew install ngrok  &&  ngrok http ${PORT}"
  echo "   (Leave this running; press Ctrl-C to stop.)"
  wait "$SERVER_PID"
fi
