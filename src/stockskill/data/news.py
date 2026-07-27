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


def fetch_news(ticker: str, limit: int = 6) -> list[dict]:
    import yfinance as yf

    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:  # noqa: BLE001
        return []

    out: list[dict] = []
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
        pub = _iso(c.get("pubDate") or c.get("displayTime") or c.get("providerPublishTime"))
        out.append({
            "title": title,
            "publisher": publisher or "",
            "url": _url(c),
            "published": pub or "",
            "age": _age(pub),
            "type": (c.get("contentType") or "").upper(),
        })
        if len(out) >= limit:
            break
    return out
