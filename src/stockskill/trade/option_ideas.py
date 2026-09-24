"""Option trade ideas priced off a real option chain.

Each idea is a small defined structure chosen from the app's own read of the
stock and how options are priced:

* bullish trend  -> bull call spread; plus a cash-secured put when options are
  rich (implied vol above realized)
* bearish trend  -> bear put spread
* no clear trend -> iron condor when options are rich (collects premium if the
  stock stays in a range); nothing when they're cheap
* for shareholders, always: a covered call

Implied volatility has usually exceeded the volatility that followed (the
variance risk premium, Carr & Wu 2009, "Variance Risk Premiums", RFS), which is
why the premium-selling ideas need rich options and why simply buying options
tends to lose on average.

For each idea: the legs, net cost or credit, maximum profit and loss,
breakevens and the chance of profit at expiry (lognormal with the implied
volatility, no drift). Per-share figures; one contract is 100 shares. Pure.
"""

from __future__ import annotations

import math
from statistics import NormalDist

_N = NormalDist()


def leg_value(leg: dict, s: float) -> float:
    """A leg's value at expiry for stock price ``s`` (per share, before premium)."""
    k = leg.get("strike") or 0.0
    if leg["kind"] == "call":
        v = max(s - k, 0.0)
    elif leg["kind"] == "put":
        v = max(k - s, 0.0)
    else:                                       # stock
        v = s
    return v if leg["side"] == "buy" else -v


def net_premium(legs: list[dict]) -> float:
    """Paid (+) or received (-) up front, per share."""
    return sum(leg["price"] if leg["side"] == "buy" else -leg["price"] for leg in legs)


def payoff(legs: list[dict], s: float) -> float:
    return sum(leg_value(leg, s) for leg in legs) - net_premium(legs)


def analyze(legs: list[dict], spot: float, iv: float, days: int) -> dict:
    """Max profit/loss (None = unlimited), breakevens and chance of profit."""
    strikes = sorted({leg["strike"] for leg in legs if leg.get("strike")})
    top = max([spot] + strikes) * 3.0
    grid = sorted(set([0.0, top] + strikes + [top * i / 3000 for i in range(1, 3000)]))
    vals = [payoff(legs, s) for s in grid]
    # unlimited if the payoff is still rising/falling at the top of the grid
    slope = vals[-1] - vals[-2]
    max_profit = None if slope > 1e-9 else max(vals)
    max_loss = None if slope < -1e-9 else min(vals)
    bes = []
    for (s0, v0), (s1, v1) in zip(zip(grid, vals), zip(grid[1:], vals[1:])):
        if (v0 < 0 <= v1) or (v0 > 0 >= v1):
            bes.append(s0 + (s1 - s0) * (0 - v0) / (v1 - v0) if v1 != v0 else s0)
    # chance of profit: lognormal at expiry with the implied vol, no drift
    t = max(days, 1) / 365.0
    sd = iv * math.sqrt(t)
    pop = 0.0
    for (s0, v0), s1 in zip(zip(grid, vals), grid[1:]):
        if v0 > 0 and s0 > 0:
            p0 = _N.cdf((math.log(s0 / spot) + 0.5 * sd * sd) / sd)
            p1 = _N.cdf((math.log(s1 / spot) + 0.5 * sd * sd) / sd)
            pop += p1 - p0
    return {"net": net_premium(legs), "max_profit": max_profit,
            "max_loss": None if max_loss is None else -max_loss,
            "breakevens": [round(b, 2) for b in bes], "pop": min(1.0, max(0.0, pop))}


def nearest(options: list[dict], target: float) -> dict | None:
    """The option with the strike closest to ``target`` that has a price."""
    priced = [o for o in options if o.get("price")]
    return min(priced, key=lambda o: abs(o["strike"] - target)) if priced else None


def _leg(side, kind, o):
    return {"side": side, "kind": kind, "strike": o["strike"], "price": o["price"]}


def view_from(trend_score: float | None, p_bull: float | None) -> str:
    ts = trend_score or 0.0
    if ts > 1 and (p_bull is None or p_bull >= 0.55):
        return "bullish"
    if ts < -1 and (p_bull is None or p_bull <= 0.45):
        return "bearish"
    return "neutral"


def ideas(calls: list[dict], puts: list[dict], spot: float, iv: float, rv: float | None,
          days: int, view: str, earnings_before_expiry: bool = False) -> list[dict]:
    """Priced ideas for one expiry. ``calls``/``puts``: [{strike, price}]."""
    if not spot or not iv or not calls or not puts:
        return []
    move = spot * iv * math.sqrt(days / 365.0)            # a one-standard-deviation move
    rich = rv is not None and iv > rv * 1.10
    cheap = rv is not None and iv < rv * 0.90
    out = []

    def add(name, why, legs):
        if any(leg["price"] is None for leg in legs):
            return
        if len({(leg["kind"], leg["strike"]) for leg in legs if leg["kind"] != "stock"}) < \
                len([leg for leg in legs if leg["kind"] != "stock"]):
            return                                        # strikes collapsed onto each other
        out.append({"name": name, "why": why, "legs": legs, **analyze(legs, spot, iv, days)})

    vol_txt = (f"options imply {iv:.0%} volatility vs {rv:.0%} realized"
               if rv else f"options imply {iv:.0%} volatility")
    if view == "bullish":
        a, b = nearest(calls, spot), nearest(calls, spot + move)
        if a and b and b["strike"] > a["strike"]:
            add("Bull call spread", f"Uptrend on the board; a capped-risk bet on a rise. {vol_txt.capitalize()}.",
                [_leg("buy", "call", a), _leg("sell", "call", b)])
        if rich:
            p = nearest(puts, spot - move)
            if p:
                add("Cash-secured put", "Uptrend and options priced rich: get paid to wait to buy about "
                    f"one standard move lower (${p['strike']:,.0f}).", [_leg("sell", "put", p)])
    elif view == "bearish":
        a, b = nearest(puts, spot), nearest(puts, spot - move)
        if a and b and b["strike"] < a["strike"]:
            add("Bear put spread", f"Downtrend on the board; a capped-risk bet on a fall. {vol_txt.capitalize()}.",
                [_leg("buy", "put", a), _leg("sell", "put", b)])
    elif rich and not earnings_before_expiry:
        sp, lp = nearest(puts, spot - move), nearest(puts, spot - 1.6 * move)
        sc, lc = nearest(calls, spot + move), nearest(calls, spot + 1.6 * move)
        if sp and lp and sc and lc and lp["strike"] < sp["strike"] < sc["strike"] < lc["strike"]:
            add("Iron condor", "No clear trend and options priced rich: collects premium if the stock stays "
                "between the short strikes, with the loss capped by the wings.",
                [_leg("buy", "put", lp), _leg("sell", "put", sp), _leg("sell", "call", sc), _leg("buy", "call", lc)])
    c = nearest(calls, spot + move)
    if c:
        add("Covered call (if you own 100 shares)",
            "Earns the premium now; gives up gains above the strike. Better when options are rich"
            + (" (they are)." if rich else (" (they aren't now)." if cheap else ".")),
            [{"side": "buy", "kind": "stock", "strike": None, "price": spot}, _leg("sell", "call", c)])
    return out
