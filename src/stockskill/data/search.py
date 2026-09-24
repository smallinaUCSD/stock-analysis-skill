"""Resolve a company name or partial query to ticker symbols (Yahoo search).

Lets the analyzer accept "oracle" and offer ORCL, rather than requiring the
exact symbol. Best-effort; returns [] on failure. Ranks primary US-listed
equities/ETFs first so the obvious match is on top.
"""

from __future__ import annotations

_SEARCH_HOSTS = (
    "https://query1.finance.yahoo.com/v1/finance/search",
    "https://query2.finance.yahoo.com/v1/finance/search",
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json"}
_US = {"NYSE", "NASDAQ", "NasdaqGS", "NYSEArca", "NYSE Arca", "NYSEAmerican", "BATS"}


def _fetch_quotes(query: str) -> list[dict]:
    """Query Yahoo search across both hosts; return raw quotes or []."""
    import requests

    params = {"q": query, "quotesCount": 12, "newsCount": 0}
    for host in _SEARCH_HOSTS:
        try:
            r = requests.get(host, params=params, headers=_HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            quotes = r.json().get("quotes")
            if quotes:
                return quotes
        except Exception:
            continue
    return []


# Symbol search backs the add box's type-ahead, which fires on nearly every
# keystroke - uncached, that alone can spend the FMP daily quota. Results change
# slowly, so remember each query for an hour (bounded).
_CACHE: dict[tuple[str, int], tuple[float, list[dict]]] = {}
_CACHE_TTL = 3600.0
_CACHE_MAX = 500


def search_symbols(query: str, limit: int = 8) -> list[dict]:
    """Return [{symbol, name, type, exchange}] matching ``query``, best first."""
    import time
    query = (query or "").strip()
    if len(query) < 1:
        return []
    key = (query.upper(), limit)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return [dict(r) for r in hit[1]]
    out = _search_uncached(query, limit)
    if out:                                   # never cache an outage's empty result
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = (time.time(), [dict(r) for r in out])
    return out


def _search_uncached(query: str, limit: int) -> list[dict]:
    from . import fmp
    results = fmp.search(query, limit=max(limit, 12)) if fmp.has_fmp() else None

    if not results:
        results = []
        for q in _fetch_quotes(query):
            sym = q.get("symbol")
            if not sym:
                continue
            results.append({
                "symbol": sym,
                "name": q.get("shortname") or q.get("longname") or sym,
                "type": q.get("quoteType"),
                "exchange": q.get("exchDisp"),
            })

    ql = query.upper()

    def rank(x):
        return (
            x["symbol"].upper() != ql,              # exact symbol match first
            x["type"] not in ("EQUITY", "ETF"),     # then stocks/ETFs
            x["exchange"] not in _US,               # then US listings
            "." in x["symbol"],                     # then primary (no suffix)
        )

    results.sort(key=rank)
    return results[:limit]
