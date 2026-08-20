#!/usr/bin/env bash
# Refresh the local data snapshot (data/cache/*.pkl) to today's data via yfinance
# -- no FMP quota used, ~15s for the full list. The committed snapshot is built
# for the cloud (served with a long cache), so run this locally to bring the
# derived numbers (multi-day changes, 52w range, charts, valuation) up to date.
# Safe to run while the board is up: it reads the fresh pkls on its next rebuild.
set -euo pipefail
cd "$(dirname "$0")/.."

CACHE="${STOCKSKILL_CACHE_DIR:-data/cache}"
TICKERS="${STOCKSKILL_TICKERS:-data/tickers.csv}"
PERIOD="${STOCKSKILL_PERIOD:-5y}"

echo ">> Refreshing ${CACHE} from ${TICKERS} via yfinance ..."
# FMP/Finnhub unset -> uses yfinance (unlimited from a home IP), so this never
# spends the FMP daily quota that the live per-ticker calls rely on.
STK_TICKERS="$TICKERS" STK_PERIOD="$PERIOD" STK_CACHE="$CACHE" \
  env -u FMP_API_KEY -u FINNHUB_API_KEY uv run python -c "
import os
from stockskill.watchlist.tickers import parse_tickers
from stockskill.watchlist import fetch_all
tk=parse_tickers(os.environ['STK_TICKERS'])['all']
data=fetch_all(tk, period=os.environ['STK_PERIOD'], workers=6,
               cache_dir=os.environ['STK_CACHE'], ttl=0.0)
ok=[t for t in tk if t in data and (data[t].ohlcv or {}).get('close')]
newest=max((str((data[t].ohlcv.get('dates') or [''])[-1]) for t in ok), default='?')
print(f'>> refreshed {len(ok)}/{len(tk)} tickers; newest date now = {newest}')
"
