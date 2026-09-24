"""Options-implied expected move from an at-the-money straddle.

The price of an at-the-money call plus put (a straddle) is what the options
market charges to bet on a move in either direction, so it's the market's
priced-in move to that expiry. The Brenner-Subrahmanyam (1988) approximation
C ~= 0.4 * S * sigma * sqrt(T) for an ATM option gives the implied volatility
back out of it: straddle ~= 0.8 * S * sigma * sqrt(T).

Pure functions; the fetch lives in data/options.py.
"""

from __future__ import annotations

import math
from datetime import date

_BS = math.sqrt(2.0 / math.pi)           # 0.7979, the exact ATM constant (2 * 0.3989)


def option_price(bid, ask, last):
    """(price, source): the bid/ask midpoint when both are live, else the last
    trade (stale outside market hours). (None, None) when there's nothing."""
    try:
        b, a = float(bid or 0), float(ask or 0)
    except (TypeError, ValueError):
        b = a = 0.0
    if b > 0 and a > 0 and a >= b:
        return (b + a) / 2.0, "mid"
    try:
        lp = float(last)
    except (TypeError, ValueError):
        return None, None
    return (lp, "last") if lp > 0 else (None, None)


def straddle_move(spot: float, call: float, put: float, days: int) -> dict | None:
    """Priced-in move to expiry from the ATM call + put prices.

    Returns {straddle, move_pct, move_dollar, low, high, iv} where ``iv`` is
    the annualized implied volatility backed out of the straddle."""
    if not spot or spot <= 0 or call is None or put is None or days <= 0:
        return None
    straddle = call + put
    t = days / 365.0
    return {"straddle": straddle, "move_pct": straddle / spot, "move_dollar": straddle,
            "low": spot - straddle, "high": spot + straddle,
            "iv": straddle / (_BS * spot * math.sqrt(t))}


def pick_expiries(expiries, today: date, earnings: str | None = None) -> list[tuple[str, str]]:
    """Choose which expiries to show: [(label, iso_expiry)].

    * "Next week": the first expiry at least 5 days out
    * "About a month": the expiry closest to 30 days (21 days or more)
    * "Through earnings": the first expiry on or after the next earnings date,
      when earnings are within 60 days and that expiry isn't already listed."""
    dated = []
    for e in expiries or []:
        try:
            y, m, d = (int(x) for x in str(e)[:10].split("-"))
            dated.append(((date(y, m, d) - today).days, str(e)[:10]))
        except ValueError:
            continue
    dated = sorted(x for x in dated if x[0] > 0)
    out: list[tuple[str, str]] = []
    wk = next((e for n, e in dated if n >= 5), None)
    if wk:
        out.append(("Next week", wk))
    month = [x for x in dated if x[0] >= 21]
    if month:
        mo = min(month, key=lambda x: abs(x[0] - 30))[1]
        if mo not in [e for _, e in out]:
            out.append(("About a month", mo))
    if earnings:
        try:
            y, m, d = (int(x) for x in earnings[:10].split("-"))
            ed = date(y, m, d)
        except ValueError:
            ed = None
        if ed and 0 <= (ed - today).days <= 60:
            er = next((e for n, e in dated if e >= ed.isoformat()), None)
            if er and er not in [e for _, e in out]:
                out.append(("Through earnings", er))
            elif er:
                out = [(lbl + " (includes earnings)" if e == er else lbl, e) for lbl, e in out]
    return out
