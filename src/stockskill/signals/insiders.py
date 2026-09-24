"""Insider trading read from SEC Form 4 transactions.

Only open-market trades carry information: code P (purchase) and S (sale).
Grants (A), option exercises (M), tax withholding (F) and gifts (G) are
mechanical and are ignored.

Cohen, Malloy & Pomorski (2012), "Decoding Inside Information" (Journal of
Finance): an insider who traded in the same calendar month in each of the
three prior years is ROUTINE (their trades predict nothing); an insider with
trades in each of the three prior years but no such pattern is OPPORTUNISTIC,
and a portfolio of opportunistic trades earned about 0.8% a month in abnormal
returns. Insiders without three prior years of trades can't be classified.

Pure functions over [{name, date, code, shares, price}] dicts.
"""

from __future__ import annotations

from datetime import date, timedelta

OPEN_MARKET = {"P", "S"}


def _d(iso: str) -> date | None:
    try:
        y, m, d = (int(x) for x in str(iso)[:10].split("-"))
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def classify_trade(trade: dict, history: list[dict]) -> str:
    """"routine", "opportunistic" or "unclassified" for one open-market trade,
    judged on the same insider's open-market trades in the three prior years."""
    td = _d(trade.get("date"))
    if td is None:
        return "unclassified"
    months_by_year: dict[int, set[int]] = {}
    for h in history:
        if h.get("name") != trade.get("name") or h.get("code") not in OPEN_MARKET:
            continue
        hd = _d(h.get("date"))
        if hd:
            months_by_year.setdefault(hd.year, set()).add(hd.month)
    prior = [td.year - k for k in (1, 2, 3)]
    if not all(y in months_by_year for y in prior):
        return "unclassified"
    if all(td.month in months_by_year[y] for y in prior):
        return "routine"
    return "opportunistic"


def summarize(trades: list[dict], today: date | None = None, days: int = 90) -> dict:
    """Open-market insider activity over the last ``days``.

    Returns counts and dollar values for buys and sells, the distinct buyers,
    how many buys were opportunistic, and a plain-English ``label``."""
    today = today or date.today()
    start = today - timedelta(days=days)
    recent = [t for t in trades if t.get("code") in OPEN_MARKET
              and (_d(t.get("date")) or date.min) >= start]
    buys = [t for t in recent if t["code"] == "P"]
    sells = [t for t in recent if t["code"] == "S"]

    def value(ts):
        return sum(abs(t.get("shares") or 0) * (t.get("price") or 0) for t in ts)
    kinds = [classify_trade(t, trades) for t in buys]
    opp = kinds.count("opportunistic")
    sell_kinds = [classify_trade(t, trades) for t in sells]
    buyers = sorted({t.get("name", "") for t in buys})
    if opp:
        label, tone = f"Opportunistic insider buying ({opp} trade{'s' if opp > 1 else ''})", "up"
    elif buys:
        label, tone = "Insider buying (routine or too little history to judge)", "muted"
    elif sells and sell_kinds.count("opportunistic"):
        label, tone = "Opportunistic insider selling", "down"
    elif sells:
        label, tone = "Insider selling only (much of it is routine or diversification)", "muted"
    else:
        label, tone = "No open-market insider trades", "muted"
    return {"days": days, "buys": len(buys), "buy_value": value(buys), "buyers": buyers,
            "opportunistic_buys": opp, "routine_buys": kinds.count("routine"),
            "sells": len(sells), "sell_value": value(sells),
            "opportunistic_sells": sell_kinds.count("opportunistic"),
            "label": label, "tone": tone,
            "recent": [{**t, "kind": k} for t, k in zip(buys, kinds)][:8]}
