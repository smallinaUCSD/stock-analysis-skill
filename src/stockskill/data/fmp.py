"""Financial Modeling Prep (FMP) adapter — a licensed, server-friendly data
source so the hosted app works even though Yahoo blocks datacenter IPs.

Targets FMP's **stable** API (the legacy /api/v3 endpoints were retired for keys
issued after 2025-08-31). Enabled when ``FMP_API_KEY`` is set. Every function
returns None/{} on any failure (no key, rate limit, network, unknown ticker) so
callers fall back to yfinance. The API key is read from the environment and never
logged. Field access is tolerant of naming variants so small API differences
degrade gracefully rather than blanking a value.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

_BASE = "https://financialmodelingprep.com/stable"
_PERIOD_DAYS = {"5d": 7, "1mo": 31, "3mo": 95, "6mo": 190, "1y": 370,
                "2y": 740, "5y": 1830, "max": 36500}


def _key() -> str | None:
    return os.environ.get("FMP_API_KEY") or None


def has_fmp() -> bool:
    return bool(_key())


def _get(path: str, **params):
    key = _key()
    if not key:
        return None
    params["apikey"] = key
    try:
        import requests
        r = requests.get(_BASE + path, params=params, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:  # noqa: BLE001
        return None


def probe(path: str, **params):
    """Diagnostic: return (status_code, short_body) for one request.

    Surfaces FMP's actual error text (invalid key / legacy endpoint / rate
    limit) without ever echoing the key -- the key rides in the query params,
    never in the response body.
    """
    key = _key()
    if not key:
        return (None, "FMP_API_KEY not set")
    params["apikey"] = key
    try:
        import requests
        r = requests.get(_BASE + path, params=params, timeout=15)
        return (r.status_code, (r.text or "")[:300])
    except Exception as e:  # noqa: BLE001
        return (None, f"request failed: {e}")


def _first(j):
    return j[0] if isinstance(j, list) and j else (j if isinstance(j, dict) else None)


def _pick(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


def ohlcv(ticker: str, period: str = "1y") -> dict | None:
    days = _PERIOD_DAYS.get(period, 370)
    frm = (date.today() - timedelta(days=days)).isoformat()
    j = _get("/historical-price-eod/full", symbol=ticker, **{"from": frm})
    # stable returns a flat list; some shapes wrap it in {"historical": [...]}.
    hist = j.get("historical") if isinstance(j, dict) else j
    if not isinstance(hist, list) or not hist:
        return None
    rows = []
    for r in hist:
        c = _pick(r, "adjClose", "close")
        if c is None or not r.get("date"):
            continue
        try:
            y, m, d = (int(x) for x in str(r["date"])[:10].split("-"))
            rows.append((date(y, m, d), r, c))
        except Exception:  # noqa: BLE001
            continue
    rows.sort(key=lambda t: t[0])                  # oldest -> newest
    if not rows:
        return None
    out = {k: [] for k in ("dates", "open", "high", "low", "close", "volume")}
    for dt, r, c in rows:
        out["dates"].append(dt)
        out["open"].append(_pick(r, "adjOpen", "open"))
        out["high"].append(_pick(r, "adjHigh", "high"))
        out["low"].append(_pick(r, "adjLow", "low"))
        out["close"].append(c)
        out["volume"].append(r.get("volume"))
    return out if out["close"] else None


def snapshot(ticker: str):
    """Build a FundamentalSnapshot from FMP stable (profile/quote/statements)."""
    from .fundamentals import FundamentalSnapshot
    prof = _first(_get("/profile", symbol=ticker)) or {}
    quote = _first(_get("/quote", symbol=ticker)) or {}
    if not prof and not quote:
        return None
    cf = _first(_get("/cash-flow-statement", symbol=ticker, limit=1)) or {}
    inc = _first(_get("/income-statement", symbol=ticker, limit=1)) or {}
    bs = _first(_get("/balance-sheet-statement", symbol=ticker, limit=1)) or {}
    growth = _first(_get("/financial-growth", symbol=ticker, limit=1)) or {}
    tgt = _first(_get("/price-target-consensus", symbol=ticker)) or {}

    net_debt = _pick(bs, "netDebt")
    if net_debt is None and bs.get("totalDebt") is not None:
        cash = _pick(bs, "cashAndShortTermInvestments", "cashAndCashEquivalents") or 0
        net_debt = bs["totalDebt"] - cash

    # 52-week high/low: quote fields, falling back to profile's "223.78-344.57".
    hi, lo = _pick(quote, "yearHigh"), _pick(quote, "yearLow")
    if (hi is None or lo is None) and isinstance(_pick(prof, "range"), str):
        try:
            plo, phi = (float(x) for x in prof["range"].split("-"))
            lo, hi = (lo if lo is not None else plo), (hi if hi is not None else phi)
        except Exception:  # noqa: BLE001
            pass

    next_earnings = None
    ea = _pick(quote, "earningsAnnouncement")
    if ea:
        try:
            ed = date.fromisoformat(str(ea)[:10])
            if ed >= date.today():
                next_earnings = ed.isoformat()
        except Exception:  # noqa: BLE001
            next_earnings = None

    return FundamentalSnapshot(
        ticker=ticker.upper(), as_of=date.today().isoformat(), source="fmp",
        price=_pick(quote, "price") or _pick(prof, "price"),
        shares=_pick(quote, "sharesOutstanding"),
        market_cap=_pick(quote, "marketCap") or _pick(prof, "marketCap", "mktCap"),
        fcf=_pick(cf, "freeCashFlow"),
        net_debt=net_debt,
        eps=_pick(quote, "eps") or _pick(inc, "eps", "epsdiluted"),
        ebitda=_pick(inc, "ebitda"),
        revenue=_pick(inc, "revenue"),
        dividend_annual=_pick(prof, "lastDividend", "lastDiv"),
        beta=_pick(prof, "beta"),
        currency=_pick(prof, "currency"),
        revenue_growth=_pick(growth, "revenueGrowth"),
        earnings_growth=_pick(growth, "epsgrowth", "epsdilutedGrowth", "netIncomeGrowth"),
        target_mean=_pick(tgt, "targetConsensus"),
        name=_pick(prof, "companyName") or _pick(quote, "name"),
        sector=_pick(prof, "sector"),
        quote_type="ETF" if _pick(prof, "isEtf") else "EQUITY",
        fifty_two_week_high=hi,
        fifty_two_week_low=lo,
        avg_volume=_pick(quote, "avgVolume", "averageVolume") or _pick(prof, "averageVolume", "volAvg"),
        next_earnings=next_earnings,
    )


def batch_quotes(tickers: list[str], chunk: int = 100) -> dict[str, dict]:
    """Current price + day-change for many tickers in ONE call per ``chunk``.

    FMP's stable /quote accepts a comma-separated symbol list, so the whole board
    costs 1-2 calls (not one per ticker) -- cheap enough to refresh on the live
    15/30-min cadence within the free tier. Returns {TICKER: {price, change_pct}};
    {} on total failure so callers keep showing the cached snapshot price.
    """
    out: dict[str, dict] = {}
    syms = [t.upper() for t in (tickers or []) if t]
    for i in range(0, len(syms), max(1, chunk)):
        j = _get("/quote", symbol=",".join(syms[i:i + chunk]))
        if not isinstance(j, list):
            continue
        for q in j:
            sym = (q.get("symbol") or "").upper()
            price = _pick(q, "price")
            if not sym or price is None:
                continue
            cp = _pick(q, "changePercentage", "changesPercentage")
            out[sym] = {"price": price, "change_pct": (cp / 100.0) if cp is not None else None}
    return out


def search(query: str, limit: int = 10) -> list[dict] | None:
    j = _get("/search-symbol", query=query, limit=limit)
    if not isinstance(j, list):
        return None
    return [{"symbol": r.get("symbol"), "name": r.get("name") or r.get("symbol"),
             "type": _pick(r, "exchange", "exchangeShortName"),
             "exchange": _pick(r, "exchangeFullName", "stockExchange", "exchange")}
            for r in j if r.get("symbol")]


def news_raw(ticker: str, limit: int = 12) -> list[dict] | None:
    j = _get("/news/stock", symbols=ticker, limit=limit)
    if not isinstance(j, list):
        return None
    out = []
    for r in j:
        pub = str(_pick(r, "publishedDate", "date") or "").replace(" ", "T")
        if pub and "Z" not in pub and "+" not in pub:
            pub += "Z"
        out.append({"title": (r.get("title") or "").strip(),
                    "summary": _pick(r, "text", "content") or "",
                    "publisher": _pick(r, "site", "publisher") or "",
                    "url": r.get("url") or "", "published": pub})
    return out


def etf_holdings(ticker: str, limit: int = 15) -> dict | None:
    j = _get("/etf/holdings", symbol=ticker)
    if not isinstance(j, list) or not j:
        return None
    holdings = []
    for r in j:
        raw = _pick(r, "weightPercentage", "pctVal", "weight")
        asset = _pick(r, "asset", "symbol")
        try:
            w = float(raw)
        except Exception:  # noqa: BLE001
            w = None
        if w is None or not asset:
            continue
        w = w / 100.0 if w > 1.0 else w              # percent -> fraction
        holdings.append({"underlying": asset, "name": r.get("name", ""), "weight": w})
    if not holdings:
        return None
    holdings.sort(key=lambda h: h["weight"], reverse=True)
    return {"name": ticker.upper(), "holdings": holdings[:limit], "sectors": None}
