#!/usr/bin/env bash
# Refresh the local data snapshot (data/cache/*.pkl) to today's data via yfinance
# -- no FMP quota used, ~15s for the full list. The committed snapshot is built
# for the cloud (served with a long cache), so run this locally to bring the
# derived numbers (multi-day changes, 52w range, charts, valuation) up to date.
# Safe to run while the board is up: it reads the fresh pkls on its next rebuild.
#
# Skips anything fetched within REFRESH_TTL seconds (default 12h): daily bars only
# change once a day, and re-pulling all ~160 names on every restart is what gets a
# home IP throttled by Yahoo. Force a full refresh with REFRESH_TTL=0.
set -euo pipefail
cd "$(dirname "$0")/.."

CACHE="${STOCKSKILL_CACHE_DIR:-data/cache}"
TICKERS="${STOCKSKILL_TICKERS:-data/tickers.csv}"
PERIOD="${STOCKSKILL_PERIOD:-5y}"
REFRESH_TTL="${REFRESH_TTL:-43200}"

echo ">> Refreshing ${CACHE} from ${TICKERS} via yfinance ..."
# FMP/Finnhub unset -> uses yfinance (no API key/quota, but Yahoo does throttle
# heavy use - hence the TTL above), so this never
# spends the FMP daily quota that the live per-ticker calls rely on.
STK_TICKERS="$TICKERS" STK_PERIOD="$PERIOD" STK_CACHE="$CACHE" STK_TTL="$REFRESH_TTL" \
  env -u FMP_API_KEY -u FINNHUB_API_KEY uv run python -c "
import os
from stockskill.watchlist.tickers import parse_tickers
from stockskill.watchlist import fetch_all
tk=parse_tickers(os.environ['STK_TICKERS'])['all']
tk += [b for b in ('SPY', 'QQQ') if b not in tk]      # benchmarks for beta/alpha
data=fetch_all(tk, period=os.environ['STK_PERIOD'], workers=6,
               cache_dir=os.environ['STK_CACHE'], ttl=float(os.environ['STK_TTL']))
ok=[t for t in tk if t in data and (data[t].ohlcv or {}).get('close')]
newest=max((str((data[t].ohlcv.get('dates') or [''])[-1]) for t in ok), default='?')
print(f'>> {len(ok)}/{len(tk)} tickers current; newest date = {newest}')
# annual reports from SEC EDGAR (needs SEC_USER_AGENT in .env; cached a day)
from stockskill.data import sec
from stockskill.leverage import registry
if sec.has_sec():
    n = 0
    for t in tk:
        if registry.get(t) is None and (sec.annual_history(t, os.environ['STK_CACHE'])
                                        or sec.yahoo_revenue_history(t, os.environ['STK_CACHE'])):
            n += 1
    print(f'>> annual reports cached for {n} companies (SEC EDGAR, Yahoo fallback)')
"
