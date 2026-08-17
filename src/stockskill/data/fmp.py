"""Financial Modeling Prep (FMP) adapter — a licensed, server-friendly data
source so the hosted app works even though Yahoo blocks datacenter IPs.

Enabled when ``FMP_API_KEY`` is set. Every function returns None on any failure
(no key, rate limit, network, unknown ticker) so callers fall back to yfinance.
The API key is read from the environment and never logged.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

_BASE = "https://financialmodelingprep.com/api/v3"
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


def _first(j):
    return j[0] if isinstance(j, list) and j else (j if isinstance(j, dict) else None)


def ohlcv(ticker: str, period: str = "1y") -> dict | None:
    days = _PERIOD_DAYS.get(period, 370)
    frm = (date.today() - timedelta(days=days)).isoformat()
    j = _get(f"/historical-price-full/{ticker}", **{"from": frm})
    hist = j.get("historical") if isinstance(j, dict) else None
    if not hist:
        return None
    out = {k: [] for k in ("dates", "open", "high", "low", "close", "volume")}
    for row in reversed(hist):                     # FMP returns newest-first
        c = row.get("adjClose", row.get("close"))
        if c is None or not row.get("date"):
            continue
        try:
            y, m, d = (int(x) for x in row["date"][:10].split("-"))
            dt = date(y, m, d)
        except Exception:  # noqa: BLE001
            continue
        out["dates"].append(dt)
        out["open"].append(row.get("open"))
        out["high"].append(row.get("high"))
        out["low"].append(row.get("low"))
        out["close"].append(c)
        out["volume"].append(row.get("volume"))
    return out if out["close"] else None


def snapshot(ticker: str):
    """Build a FundamentalSnapshot from FMP (profile/quote/statements)."""
    from .fundamentals import FundamentalSnapshot
    prof = _first(_get(f"/profile/{ticker}")) or {}
    quote = _first(_get(f"/quote/{ticker}")) or {}
    if not prof and not quote:
        return None
    cf = _first(_get(f"/cash-flow-statement/{ticker}", limit=1)) or {}
    inc = _first(_get(f"/income-statement/{ticker}", limit=1)) or {}
    bs = _first(_get(f"/balance-sheet-statement/{ticker}", limit=1)) or {}
    growth = _first(_get(f"/financial-growth/{ticker}", limit=1)) or {}
    tgt = _first(_get(f"/price-target-consensus/{ticker}")) or {}

    net_debt = None
    if bs.get("totalDebt") is not None:
        cash = bs.get("cashAndShortTermInvestments") or bs.get("cashAndCashEquivalents") or 0
        net_debt = bs["totalDebt"] - cash

    next_earnings = None
    ea = quote.get("earningsAnnouncement")
    if ea:
        try:
            ed = date.fromisoformat(ea[:10])
            if ed >= date.today():
                next_earnings = ed.isoformat()
        except Exception:  # noqa: BLE001
            next_earnings = None

    return FundamentalSnapshot(
        ticker=ticker.upper(), as_of=date.today().isoformat(), source="fmp",
        price=quote.get("price") or prof.get("price"),
        shares=quote.get("sharesOutstanding"),
        market_cap=quote.get("marketCap") or prof.get("mktCap"),
        fcf=cf.get("freeCashFlow"),
        net_debt=net_debt,
        eps=quote.get("eps") or inc.get("eps"),
        ebitda=inc.get("ebitda"),
        revenue=inc.get("revenue"),
        dividend_annual=prof.get("lastDiv"),
        beta=prof.get("beta"),
        currency=prof.get("currency"),
        revenue_growth=growth.get("revenueGrowth"),
        earnings_growth=growth.get("epsgrowth"),
        target_mean=tgt.get("targetConsensus"),
        name=prof.get("companyName") or quote.get("name"),
        sector=prof.get("sector"),
        quote_type="ETF" if prof.get("isEtf") else "EQUITY",
        fifty_two_week_high=quote.get("yearHigh"),
        fifty_two_week_low=quote.get("yearLow"),
        avg_volume=quote.get("avgVolume") or prof.get("volAvg"),
        next_earnings=next_earnings,
    )


def batch_quotes(tickers: list[str], chunk: int = 100) -> dict[str, dict]:
    """Current price + day-change for many tickers in ONE call per ``chunk``.

    FMP's /quote endpoint takes a comma-separated symbol list, so the whole board
    costs 1-2 calls (not one per ticker) -- cheap enough to refresh on the live
    15/30-min cadence within the free tier. Returns {TICKER: {price, change_pct}};
    {} on total failure so callers keep showing the cached snapshot price.
    """
    out: dict[str, dict] = {}
    syms = [t.upper() for t in (tickers or []) if t]
    for i in range(0, len(syms), max(1, chunk)):
        part = syms[i:i + chunk]
        j = _get("/quote/" + ",".join(part))
        if not isinstance(j, list):
            continue
        for q in j:
            sym = (q.get("symbol") or "").upper()
            if not sym or q.get("price") is None:
                continue
            cp = q.get("changesPercentage")
            out[sym] = {"price": q.get("price"),
                        "change_pct": (cp / 100.0) if cp is not None else None}
    return out


def search(query: str, limit: int = 10) -> list[dict] | None:
    j = _get("/search", query=query, limit=limit)
    if not isinstance(j, list):
        return None
    return [{"symbol": r.get("symbol"), "name": r.get("name") or r.get("symbol"),
             "type": r.get("exchangeShortName"), "exchange": r.get("stockExchange")}
            for r in j if r.get("symbol")]


def news_raw(ticker: str, limit: int = 12) -> list[dict] | None:
    j = _get("/stock_news", tickers=ticker, limit=limit)
    if not isinstance(j, list):
        return None
    out = []
    for r in j:
        pub = (r.get("publishedDate") or "").replace(" ", "T")
        if pub and "Z" not in pub and "+" not in pub:
            pub += "Z"
        out.append({"title": (r.get("title") or "").strip(),
                    "summary": r.get("text") or "",
                    "publisher": r.get("site") or "",
                    "url": r.get("url") or "", "published": pub})
    return out


def etf_holdings(ticker: str, limit: int = 15) -> dict | None:
    j = _get(f"/etf-holder/{ticker}")
    if not isinstance(j, list) or not j:
        return None
    holdings = []
    for r in j:
        try:
            w = float(r.get("weightPercentage")) / 100.0
        except Exception:  # noqa: BLE001
            w = None
        if not w or not r.get("asset"):
            continue
        holdings.append({"underlying": r["asset"], "name": r.get("name", ""), "weight": w})
    if not holdings:
        return None
    holdings.sort(key=lambda h: h["weight"], reverse=True)
    return {"name": ticker.upper(), "holdings": holdings[:limit], "sectors": None}
