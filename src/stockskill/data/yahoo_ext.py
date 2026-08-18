"""Yahoo extended-hours (pre/post-market) quotes for the board.

Finnhub's free tier returns the regular *close* during extended hours, so the
after-hours price line is sourced from Yahoo's v7 quote endpoint instead, which
carries ``postMarketPrice`` / ``preMarketPrice``. Used ONLY to populate the
pre/after-hours line during those sessions.

Best-effort: Yahoo rate-limits datacenter IPs (that's why it's not the main
feed), so any failure returns ``{}`` and the board shows *no* extended price
rather than a stale one. The v7 quote needs a cookie + crumb, handled here.
"""

from __future__ import annotations

# UA-only: the getcrumb endpoint returns plain text and 406s on Accept: json.
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def _get_crumb(session) -> str | None:
    try:
        session.get("https://fc.yahoo.com/", headers=_HEADERS, timeout=8)  # sets cookies
    except Exception:  # noqa: BLE001
        pass
    for host in ("query1", "query2"):
        try:
            r = session.get(f"https://{host}.finance.yahoo.com/v1/test/getcrumb",
                            headers=_HEADERS, timeout=8)
            txt = (r.text or "").strip()
            if r.status_code == 200 and txt and "<" not in txt:
                return txt
        except Exception:  # noqa: BLE001
            continue
    return None


def _ext_from_quote(q: dict):
    """Pull the pre/post-market price + change from a v7 quote result, by state."""
    state = q.get("marketState")
    if state in ("POST", "POSTPOST", "CLOSED"):
        price, ch = q.get("postMarketPrice"), q.get("postMarketChangePercent")
    elif state in ("PRE", "PREPRE"):
        price, ch = q.get("preMarketPrice"), q.get("preMarketChangePercent")
    else:
        return None
    if not price:
        return None
    return {"market_state": state, "ext_price": price,
            "ext_change": (ch / 100.0) if ch is not None else None}


def ext_quotes(tickers: list[str], chunk: int = 100) -> dict[str, dict]:
    """{TICKER: {market_state, ext_price, ext_change}} for names in an extended
    session. {} on any failure (e.g. a rate-limited datacenter IP)."""
    import requests

    syms = [t.upper() for t in (tickers or []) if t]
    if not syms:
        return {}
    session = requests.Session()
    crumb = _get_crumb(session)
    if not crumb:
        return {}

    out: dict[str, dict] = {}
    for i in range(0, len(syms), chunk):
        try:
            r = session.get("https://query1.finance.yahoo.com/v7/finance/quote",
                            params={"symbols": ",".join(syms[i:i + chunk]), "crumb": crumb},
                            headers=_HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            results = (r.json().get("quoteResponse") or {}).get("result") or []
        except Exception:  # noqa: BLE001
            continue
        for q in results:
            sym = (q.get("symbol") or "").upper()
            ext = _ext_from_quote(q) if sym else None
            if ext:
                out[sym] = ext
    return out
