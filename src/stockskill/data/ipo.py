"""IPO calendar (Finnhub, free tier): upcoming listings and recently priced ones.

``normalize`` and ``split`` are pure (tested); ``calendar`` fetches with a
6-hour cache. Recently priced IPOs get their move since pricing from a live
quote. Long-run, IPOs have lagged comparable stocks on average (Ritter, 1991,
"The Long-Run Performance of Initial Public Offerings", Journal of Finance).
"""

from __future__ import annotations

import time
from datetime import date, timedelta

_CACHE: dict = {}
_TTL = 6 * 3600


def _price_range(p):
    """"40.00-44.00" / "18" / None -> (low, high)."""
    if p in (None, ""):
        return None, None
    try:
        parts = [float(x) for x in str(p).replace("$", "").split("-") if x.strip()]
    except ValueError:
        return None, None
    if not parts:
        return None, None
    return min(parts), max(parts)


def normalize(rows: list[dict]) -> list[dict]:
    """Finnhub rows -> [{date, symbol, name, exchange, low, high, shares, value, status}]."""
    out = []
    for r in rows or []:
        lo, hi = _price_range(r.get("price"))
        shares = r.get("numberOfShares")
        value = r.get("totalSharesValue") or ((shares * (lo + hi) / 2) if (shares and lo and hi) else None)
        name = r.get("name") or ""
        sym = (r.get("symbol") or "").upper()
        # blank-check shells list at $10 as units ("...Acquisition Corp", ticker ending U)
        spac = ("acquisition" in name.lower() and (hi in (10.0, None))) or \
               (sym.endswith("U") and hi == 10.0)
        out.append({"date": r.get("date") or "", "symbol": sym, "spac": spac,
                    "name": name, "exchange": r.get("exchange") or "",
                    "low": lo, "high": hi, "shares": shares, "value": value,
                    "status": (r.get("status") or "").lower()})
    return out


def split(rows: list[dict], today: date | None = None) -> dict:
    """{"upcoming": soonest first, "recent": priced in the past, newest first}.
    Withdrawn deals are dropped."""
    today = (today or date.today()).isoformat()
    live = [r for r in rows if r["status"] != "withdrawn"]
    upcoming = sorted((r for r in live if r["date"] >= today and r["status"] != "priced"),
                      key=lambda r: (r["date"], -(r["value"] or 0)))
    recent = sorted((r for r in live if r["status"] == "priced" and r["date"] <= today),
                    key=lambda r: r["date"], reverse=True)
    return {"upcoming": upcoming, "recent": recent}


def calendar(days_back: int = 30, days_ahead: int = 45, quotes: bool = True) -> dict | None:
    """Upcoming and recent IPOs, cached 6 hours. None without a Finnhub key."""
    from . import finnhub
    if not finnhub.has_finnhub():
        return None
    key = ("cal", quotes)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    today = date.today()
    j = finnhub._get("/calendar/ipo", **{"from": str(today - timedelta(days=days_back)),
                                           "to": str(today + timedelta(days=days_ahead))})
    rows = (j or {}).get("ipoCalendar") if isinstance(j, dict) else None
    if rows is None:
        return None
    out = split(normalize(rows), today)
    missing = False
    if quotes:
        syms = [r["symbol"] for r in out["recent"][:25] if r["symbol"]]
        # through the shared rate limiter: the board's refresh uses the same quota
        qs = finnhub.batch_quotes(syms) if syms else {}
        for r in out["recent"][:25]:
            q = qs.get(r["symbol"])
            ipo_px = r["high"] if r["high"] == r["low"] else None   # priced deals report one price
            r["last"] = q["price"] if q else None
            r["since_ipo"] = (q["price"] / ipo_px - 1.0) if (q and ipo_px) else None
            missing = missing or (r["symbol"] and q is None)
    out["as_of"] = today.isoformat()
    # a quote can fail while the quota is busy: retry those sooner than 6 hours
    _CACHE[key] = (time.time() - (_TTL - 600 if missing else 0), out)
    return out
