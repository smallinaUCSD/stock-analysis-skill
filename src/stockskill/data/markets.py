"""Cross-asset market overview: stock indexes, Treasury yields, bond funds,
commodities, currencies and crypto, each with day / week / month / year-to-
date / 1-year moves and a one-year weekly price line.

Prices come from Yahoo in one batched download (daily bars; today's bar is
live during the session), cached 10 minutes while US markets are open.
``performance`` is pure (tested).
"""

from __future__ import annotations

import threading
import time
from datetime import date, timedelta

# (section, [(symbol, name, kind)]); kind: "price", "yield" (percent level), "fx"
SECTIONS = [
    ("US stocks", [("^GSPC", "S&P 500", "price"), ("^IXIC", "Nasdaq Composite", "price"), ("^DJI", "Dow Jones", "price"),
                   ("^RUT", "Russell 2000", "price"), ("^VIX", "VIX (volatility)", "price")]),
    ("World stocks", [("^STOXX50E", "Euro Stoxx 50", "price"), ("^FTSE", "FTSE 100 (UK)", "price"),
                      ("^GDAXI", "DAX (Germany)", "price"), ("^N225", "Nikkei 225 (Japan)", "price"),
                      ("^HSI", "Hang Seng (Hong Kong)", "price"), ("000001.SS", "Shanghai Composite", "price")]),
    ("Treasury yields", [("^IRX", "3-month", "yield"), ("^FVX", "5-year", "yield"), ("^TNX", "10-year", "yield"),
                         ("^TYX", "30-year", "yield")]),
    ("Bond funds", [("SHY", "Short-term Treasuries (SHY)", "price"), ("IEF", "7-10 year Treasuries (IEF)", "price"),
                    ("TLT", "20+ year Treasuries (TLT)", "price"), ("TIP", "Inflation-protected (TIP)", "price"),
                    ("AGG", "US bond market (AGG)", "price"), ("LQD", "Investment-grade corporate (LQD)", "price"),
                    ("HYG", "High-yield corporate (HYG)", "price"), ("EMB", "Emerging-market bonds (EMB)", "price")]),
    ("Energy", [("CL=F", "Crude oil (WTI)", "price"), ("BZ=F", "Crude oil (Brent)", "price"),
                ("NG=F", "Natural gas", "price"), ("RB=F", "Gasoline", "price"), ("HO=F", "Heating oil", "price")]),
    ("Metals", [("GC=F", "Gold", "price"), ("SI=F", "Silver", "price"), ("HG=F", "Copper", "price"),
                ("PL=F", "Platinum", "price"), ("PA=F", "Palladium", "price")]),
    ("Agriculture", [("ZC=F", "Corn", "price"), ("ZW=F", "Wheat", "price"), ("ZS=F", "Soybeans", "price"),
                     ("KC=F", "Coffee", "price"), ("SB=F", "Sugar", "price"), ("CC=F", "Cocoa", "price"),
                     ("CT=F", "Cotton", "price"), ("LE=F", "Live cattle", "price")]),
    ("Currencies", [("DX-Y.NYB", "US dollar index", "fx"), ("EURUSD=X", "Euro in dollars", "fx"),
                    ("GBPUSD=X", "British pound in dollars", "fx"), ("JPY=X", "Dollar in yen", "fx"),
                    ("CNY=X", "Dollar in yuan", "fx"), ("CAD=X", "Dollar in Canadian dollars", "fx")]),
    ("Crypto", [("BTC-USD", "Bitcoin", "price"), ("ETH-USD", "Ethereum", "price"), ("SOL-USD", "Solana", "price")]),
]


def performance(dates: list[date], closes: list[float], kind: str = "price", today: date | None = None) -> dict:
    """Latest level and moves over standard windows. For yields the moves are
    changes in percentage points (shown as basis points), not percent changes."""
    pts = [(d, c) for d, c in zip(dates, closes) if c is not None and c == c]
    if not pts:
        return {}
    today = today or pts[-1][0]
    last_d, last = pts[-1]

    def at_or_before(target: date):
        best = None
        for d, c in pts:
            if d <= target:
                best = c
            else:
                break
        return best

    def move(then):
        if then is None:
            return None
        if kind == "yield":
            return last - then
        return last / then - 1 if then else None
    prev = pts[-2][1] if len(pts) > 1 else None
    out = {"last": last, "as_of": last_d.isoformat(), "d1": move(prev),
           "w1": move(at_or_before(last_d - timedelta(days=7))),
           "m1": move(at_or_before(last_d - timedelta(days=30))),
           "ytd": move(at_or_before(date(last_d.year - 1, 12, 31))),
           "y1": move(at_or_before(last_d - timedelta(days=365)))}
    # a weekly line for the last year, plus every day of the last three months
    year = [(d, c) for d, c in pts if d > last_d - timedelta(days=366)]
    weekly = [c for i, (d, c) in enumerate(year) if i % 5 == 0 or i == len(year) - 1]
    out["line"] = [round(c, 4) for c in weekly]
    out["spark"] = [round(c, 4) for d, c in pts if d > last_d - timedelta(days=92)]
    return out


_CACHE: dict = {"t": 0.0, "data": None}
_LOCK = threading.Lock()


def _download() -> dict:
    import yfinance as yf
    syms = [s for _, rows in SECTIONS for s, _, _ in rows]
    df = yf.download(syms, period="13mo", interval="1d", group_by="ticker", auto_adjust=True,
                     progress=False, threads=True)
    series = {}
    for s in syms:
        try:
            col = df[s]["Close"].dropna()
        except Exception:  # noqa: BLE001
            continue
        if len(col):
            series[s] = ([i.date() for i in col.index], [float(v) for v in col.values])
    return series


def overview() -> dict:
    """{sections: [{name, rows: [{symbol, name, kind, ...performance}]}], as_of}."""
    from ..marketclock import market_status
    ttl = 600 if market_status().label in ("open", "pre-market", "after-hours") else 3600
    with _LOCK:
        if _CACHE["data"] is not None and time.time() - _CACHE["t"] < ttl:
            return _CACHE["data"]
    try:
        series = _download()
    except Exception:  # noqa: BLE001
        series = {}
    sections = []
    for name, rows in SECTIONS:
        out = []
        for sym, label, kind in rows:
            if sym in series:
                p = performance(*series[sym], kind=kind)
                if p:
                    out.append({"symbol": sym, "name": label, "kind": kind, **p})
        if out:
            sections.append({"name": name, "rows": out})
    data = {"sections": sections, "as_of": time.time()}
    if sections:
        with _LOCK:
            _CACHE.update(t=time.time(), data=data)
    elif _CACHE["data"] is not None:
        return _CACHE["data"]
    return data
