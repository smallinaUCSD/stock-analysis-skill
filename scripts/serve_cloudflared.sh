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
# Then just:  ./scripts/serve_cloudflared.sh        (uses port 8787; opens Safari when live)
# Or pick a port:  PORT=8899 ./scripts/serve_cloudflared.sh
# Don't open a browser:  NO_OPEN=1 ./scripts/serve_cloudflared.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8787}"

if [ -f .env ]; then
  set -a; . ./.env; set +a
else
  echo "!! No .env found. Copy .env.example to .env and add your keys first."
  echo "   (Without keys it still runs, using yfinance for data.)"
fi

# Free the port if a PREVIOUS board instance is still on it (a run that didn't
# exit through its cleanup - closed terminal, sleep). Only ever kills our own
# gunicorn; a different app (e.g. a node server) makes us stop and warn instead.
if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  own=$(for p in $(lsof -nP -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null); do
          ps -p "$p" -o command= 2>/dev/null | grep -q "stockskill.server:create_app" && echo "$p"
        done)
  if [ -n "$own" ]; then
    echo ">> Port ${PORT} held by a previous board; stopping it..."
    echo "$own" | xargs kill 2>/dev/null || true; sleep 1
    lsof -nP -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null || true
  fi
fi
if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "!! Port ${PORT} is in use by another process:"
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN
  echo "   Stop it, or run on another port:  PORT=8899 $0"
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

# Keep the terminal quiet: server and tunnel logs go to files (.cache is gitignored).
LOGDIR=".cache/serve"; mkdir -p "$LOGDIR"
BOARD_LOG="$LOGDIR/board.log"; TUNNEL_LOG="$LOGDIR/tunnel.log"
: > "$BOARD_LOG"; : > "$TUNNEL_LOG"

echo ">> Starting the board on http://127.0.0.1:${PORT} ..."
uv run gunicorn -w 1 -k gthread --threads 8 -t 120 \
  -b "127.0.0.1:${PORT}" 'stockskill.server:create_app()' >>"$BOARD_LOG" 2>&1 &
SERVER_PID=$!
TUNNEL_PID=""

cleanup() {
  echo; echo ">> Stopping tunnel and server..."
  [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null || true
  pkill -P "$SERVER_PID" 2>/dev/null || true
  kill "$SERVER_PID" 2>/dev/null || true
  lsof -nP -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
  if curl -fsS -m 2 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! curl -fsS -m 2 "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
  echo "!! The board didn't start. Last lines of $BOARD_LOG:"; tail -20 "$BOARD_LOG"; exit 1
fi
echo "   Board is up locally: http://127.0.0.1:${PORT}"

echo ">> Opening a Cloudflare tunnel (this takes a few seconds)..."
cloudflared tunnel --url "http://localhost:${PORT}" >>"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

URL=""
for _ in $(seq 1 30); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | grep -v '://api\.' | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "!! Cloudflare didn't hand out a URL. Last lines of $TUNNEL_LOG:"; tail -20 "$TUNNEL_LOG"; exit 1
fi
HOST="${URL#https://}"

# A new quick-tunnel name takes a little while to exist in DNS. If anyone (Safari,
# or this script) looks it up too early, macOS caches "not found" and the link
# keeps failing ("Safari can't find the server") until that cache expires. So:
# ask Cloudflare's DNS directly (dig bypasses the Mac's cache) and test the tunnel
# pinned to that IP, and only print the link once it actually answers.
echo "   Waiting for the link to go live (don't open it yet)..."
READY=""
for _ in $(seq 1 60); do
  IP=$(dig +short @1.1.1.1 "$HOST" A 2>/dev/null | grep -E '^[0-9.]+$' | head -1 || true)
  if [ -n "$IP" ] && [ "$(curl -s -m 8 -o /dev/null -w '%{http_code}' --resolve "$HOST:443:$IP" "$URL/healthz")" = "200" ]; then
    READY=1; break
  fi
  sleep 2
done

echo
if [ -n "$READY" ]; then
  echo "  ============================================================"
  echo "   Your board is live. Share this link:"
  echo
  echo "     $URL"
  echo
  echo "  ============================================================"
  # Open it in Safari now that it answers (opening earlier is what made macOS
  # cache "not found"). Skip with NO_OPEN=1.
  if [ -z "${NO_OPEN:-}" ] && [ "$(uname)" = "Darwin" ]; then
    open -a Safari "$URL" 2>/dev/null || open "$URL" 2>/dev/null || true
  fi
else
  echo "!! The link hasn't come up yet (Cloudflare can be slow). It may still work in a"
  echo "   minute: $URL"
fi
echo "   It changes every time you restart this script. Press Ctrl-C to stop."
echo "   Logs: $BOARD_LOG, $TUNNEL_LOG"
echo "   If Safari says it can't find the server, clear the Mac's DNS cache:"
echo "     sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder"
wait "$TUNNEL_PID"
