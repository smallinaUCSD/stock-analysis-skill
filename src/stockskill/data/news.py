"""Recent news headlines per ticker (yfinance). Best-effort, normalized.

Handles both the current yfinance shape (``{id, content:{...}}``) and the older
flat shape (``{title, publisher, link, providerPublishTime}``). Returns a list of
``{title, publisher, url, published, age, type}`` dicts, newest first.
"""

from __future__ import annotations

from datetime import datetime, timezone


def _iso(value) -> str | None:
    """Coerce a pubDate string or a unix timestamp to an ISO string."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except Exception:
            return None
    return str(value)


def _age(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        secs = (datetime.now(timezone.utc) - dt).total_seconds()
        if secs < 3600:
            return f"{int(secs // 60)}m ago"
        if secs < 86400:
            return f"{int(secs // 3600)}h ago"
        return f"{int(secs // 86400)}d ago"
    except Exception:
        return ""


def _url(c: dict) -> str:
    for k in ("clickThroughUrl", "canonicalUrl"):
        u = c.get(k)
        if isinstance(u, dict) and u.get("url"):
            return u["url"]
    return c.get("link") or ""


# dropped when tokenizing a company name for relevance matching
_NAME_STOP = {"inc", "inc.", "corp", "corp.", "corporation", "co", "co.", "company",
              "ltd", "plc", "sa", "nv", "ag", "holdings", "holding", "group",
              "technologies", "technology", "systems", "the", "class", "cl", "&",
              "com", "incorporated", "limited", "companies", "international", "intl"}


def _name_tokens(name: str | None) -> list[str]:
    if not name:
        return []
    toks = []
    for t in name.replace(",", " ").replace(".", " ").lower().split():
        if t in _NAME_STOP or len(t) < 3:
            continue
        toks.append(t)
    return toks


def _relevant(text: str, ticker: str, tokens: list[str]) -> bool:
    low = text.lower()
    if ticker.lower() in low:
        return True
    return any(tok in low for tok in tokens)


def _yf_raw(ticker: str) -> list[dict]:
    """Fetch and flatten yfinance news to {title, summary, publisher, url, published}."""
    import yfinance as yf

    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:  # noqa: BLE001
        return []

    items = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        c = item.get("content") if "content" in item else item
        if not isinstance(c, dict):
            continue
        title = (c.get("title") or "").strip()
        if not title:
            continue
        prov = c.get("provider")
        publisher = prov.get("displayName") if isinstance(prov, dict) else (c.get("publisher") or "")
        items.append({
            "title": title,
            "summary": c.get("summary") or c.get("description") or "",
            "publisher": publisher or "",
            "url": _url(c),
            "published": _iso(c.get("pubDate") or c.get("displayTime")
                              or c.get("providerPublishTime")) or "",
        })
    return items


def fetch_news(ticker: str, limit: int = 6, name: str | None = None) -> list[dict]:
    """Recent, company-relevant headlines, newest first.

    When ``name`` is given, keep only items whose headline/summary mentions the
    ticker or a company-name token (drops broad market roundups). Falls back to
    the unfiltered set if that would leave nothing. Prefers FMP when a key is
    configured (works from datacenter IPs), falling back to yfinance.
    """
    from . import fmp

    raw = None
    if fmp.has_fmp():
        raw = fmp.news_raw(ticker, limit=max(limit * 2, 12))
    if not raw:
        raw = _yf_raw(ticker)

    tokens = _name_tokens(name)
    out: list[dict] = []
    for item in raw:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        summary = item.get("summary") or ""
        pub = item.get("published") or ""
        out.append({
            "title": title,
            "publisher": item.get("publisher") or "",
            "url": item.get("url") or "",
            "published": pub,
            "age": _age(pub),
            "_ts": _epoch(pub),
            "_rel": _relevant(title + " " + summary, ticker, tokens),
            "type": (item.get("type") or "STORY").upper(),
        })

    # keep only company-relevant items when we can tell them apart
    relevant = [n for n in out if n["_rel"]]
    kept = relevant if relevant else out

    # rank most-recent first, then take the top ``limit`` (undated sort last)
    kept.sort(key=lambda n: n["_ts"], reverse=True)
    for n in kept:
        n.pop("_ts", None)
        n.pop("_rel", None)
    return kept[:limit]


def _epoch(iso: str | None) -> float:
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0
