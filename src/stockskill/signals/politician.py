"""A politician's trading profile, from their reported trades.

Reports give amount RANGES, so dollar figures use each range's midpoint and are
estimates. "Positions" are what the filings imply they still hold (bought and
not reported sold) since the first trade we have - not their full portfolio,
which the annual reports cover. Performance is a "copy their trades" portfolio:
put the midpoint into each stock on the trade date, sell on the reported sale,
and compare with putting the same dollars into the S&P 500 on the same days.
Pure functions.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import date

# committee -> industries it oversees (matched against a stock's sector name)
COMMITTEE_SECTORS = {
    "armed services": ["industrials", "aerospace", "defense"],
    "energy": ["energy", "utilities"],
    "natural resources": ["energy", "basic materials"],
    "financial services": ["financial"], "banking": ["financial"], "finance": ["financial", "healthcare"],
    "health": ["healthcare"], "agriculture": ["consumer defensive", "basic materials"],
    "commerce": ["technology", "communication services", "consumer cyclical"],
    "science": ["technology"], "transportation": ["industrials"], "intelligence": ["technology"],
    "homeland security": ["technology", "industrials"], "ways and means": ["healthcare", "financial"],
    "veterans": ["healthcare"],
}


def _mid(t: dict) -> float:
    lo, hi = t.get("amount_low"), t.get("amount_high")
    if lo and hi:
        return (lo + hi) / 2.0
    return float(lo or 0)


def _lag(t: dict) -> int | None:
    try:
        return (date.fromisoformat(t["filed"]) - date.fromisoformat(t["traded"])).days
    except (KeyError, TypeError, ValueError):
        return None


def stats(trades: list[dict]) -> dict:
    """Counts, estimated dollars, reporting delay and most-traded tickers."""
    buys = [t for t in trades if (t.get("type") or "").startswith("Buy")]
    sells = [t for t in trades if (t.get("type") or "").startswith("Sell")]
    lags = [x for x in (_lag(t) for t in trades) if x is not None and x >= 0]
    by_tk: dict = {}
    for t in trades:
        if t.get("ticker"):
            d = by_tk.setdefault(t["ticker"], {"ticker": t["ticker"], "buys": 0, "sells": 0, "dollars": 0.0})
            d["buys" if (t.get("type") or "").startswith("Buy") else "sells"] += 1
            d["dollars"] += _mid(t)
    dates = sorted(t["traded"] for t in trades if t.get("traded"))
    return {"trades": len(trades), "buys": len(buys), "sells": len(sells),
            "bought": sum(_mid(t) for t in buys), "sold": sum(_mid(t) for t in sells),
            "avg_lag": (sum(lags) / len(lags)) if lags else None,
            "late": sum(1 for x in lags if x > 45),
            "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
            "top": sorted(by_tk.values(), key=lambda d: d["dollars"], reverse=True)[:12],
            "spouse_share": (sum(1 for t in trades if (t.get("owner") or "") == "Spouse") / len(trades))
            if trades else None}


def positions(trades: list[dict]) -> list[dict]:
    """Per ticker: estimated dollars still held per the filings (buys minus
    reported sales; a full sale closes the position)."""
    pos: dict = {}
    for t in sorted((t for t in trades if t.get("ticker") and t.get("traded")), key=lambda t: t["traded"]):
        p = pos.setdefault(t["ticker"], {"ticker": t["ticker"], "asset": t.get("asset", ""), "cost": 0.0,
                                         "first": t["traded"], "last": t["traded"], "open": False})
        p["last"] = t["traded"]
        kind = t.get("type") or ""
        if kind.startswith("Buy"):
            p["cost"] += _mid(t)
            p["open"] = True
        elif kind == "Sell":
            p["cost"], p["open"] = 0.0, False
        elif kind.startswith("Sell"):
            p["cost"] = max(0.0, p["cost"] - _mid(t))
            p["open"] = p["cost"] > 0
    return sorted(pos.values(), key=lambda p: (p["open"], p["cost"]), reverse=True)


def _price_on(dates: list[str], closes: list[float], d: str):
    i = bisect_right(dates, d) - 1
    return closes[i] if i >= 0 else None


def simulate(trades: list[dict], prices: dict, bench: tuple, step: int = 5) -> dict | None:
    """Copy-their-trades portfolio vs the same dollars in the benchmark.

    ``prices``: {ticker: (iso_dates, closes)}; ``bench``: (iso_dates, closes).
    Returns {dates, value, bench, invested, summary}; None if nothing priced."""
    tr = sorted((t for t in trades if t.get("ticker") in prices and t.get("traded")), key=lambda t: t["traded"])
    if not tr or not bench or not bench[0]:
        return None
    bdates, bcl = bench
    start = tr[0]["traded"]
    days = [d for d in bdates if d >= start]
    if not days:
        return None
    shares: dict = {}
    cash = invested = 0.0
    b_units = b_cash = 0.0
    ti = 0
    out_d, out_v, out_b, out_i = [], [], [], []
    for k, d in enumerate(days):
        while ti < len(tr) and tr[ti]["traded"] <= d:
            t = tr[ti]
            ti += 1
            tk = t["ticker"]
            px = _price_on(*prices[tk], d)
            bpx = _price_on(bdates, bcl, d)
            if not px or not bpx:
                continue
            amt = _mid(t)
            kind = t.get("type") or ""
            if kind.startswith("Buy"):
                shares[tk] = shares.get(tk, 0.0) + amt / px
                invested += amt
                b_units += amt / bpx
            elif kind.startswith("Sell"):
                held = shares.get(tk, 0.0) * px
                sell = held if kind == "Sell" else min(held, amt)
                if sell <= 0:
                    continue
                frac = sell / held if held else 0.0
                shares[tk] = shares.get(tk, 0.0) * (1 - frac)
                cash += sell
                # the benchmark sells the same share of what it bought for that stock
                b_sell = min(b_units * bpx, sell / px * bpx) if px else 0.0
                b_units -= b_sell / bpx
                b_cash += b_sell
        if k % step == 0 or k == len(days) - 1:
            hv = sum(sh * (_price_on(*prices[t], d) or 0.0) for t, sh in shares.items())
            out_d.append(d)
            out_v.append(round(hv + cash, 2))
            out_b.append(round(b_units * (_price_on(bdates, bcl, d) or 0.0) + b_cash, 2))
            out_i.append(round(invested, 2))
    if not invested:
        return None
    return {"dates": out_d, "value": out_v, "bench": out_b, "invested": out_i,
            "summary": {"invested": invested, "value": out_v[-1], "gain": out_v[-1] / invested - 1.0,
                        "bench_value": out_b[-1], "bench_gain": out_b[-1] / invested - 1.0,
                        "priced_trades": len(tr)}}


def committee_overlap(trades: list[dict], committees: list[dict], sectors: dict) -> list[dict]:
    """Trades in stocks whose sector a member's committee oversees."""
    covered = set()
    for c in committees or []:
        name = (c.get("name") or "").lower()
        for key, secs in COMMITTEE_SECTORS.items():
            if key in name:
                covered.update(secs)
    out = []
    for t in trades:
        sec = (sectors.get(t.get("ticker")) or "").lower()
        if sec and any(s in sec for s in covered):
            out.append({**t, "sector": sectors.get(t.get("ticker"))})
    return out
