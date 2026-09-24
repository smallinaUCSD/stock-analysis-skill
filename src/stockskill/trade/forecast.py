"""Price-range forecasts: where a stock could plausibly be in 1, 3, 6 and 12
months, as a probability cone rather than a single target.

The spread comes from volatility: the options market's implied volatility when
available (a forward-looking estimate; implied vol forecasts future realized
vol reasonably well, Christensen & Prabhala 1998, JFE), otherwise the stock's
realized volatility over the past year. Prices are lognormal with a drift of
the risk-free rate, i.e. no assumed edge in either direction: this is a range
forecast, not a directional call.

``coverage`` checks the method on history: how often the real price landed
inside the predicted 80% range (fat tails usually make it a bit less than 80%).
Pure functions.
"""

from __future__ import annotations

import math
from statistics import NormalDist

_N = NormalDist()
HORIZONS = (21, 63, 126, 252)
PCTS = (0.10, 0.25, 0.50, 0.75, 0.90)


def price_at(spot: float, sigma: float, days: int, p: float, drift: float = 0.043) -> float:
    """The ``p`` percentile price after ``days`` trading days (lognormal)."""
    t = days / 252.0
    return spot * math.exp((drift - 0.5 * sigma * sigma) * t + sigma * math.sqrt(t) * _N.inv_cdf(p))


def ranges(spot: float, sigma: float, horizons=HORIZONS, pcts=PCTS, drift: float = 0.043) -> list[dict]:
    """[{days, p10, p25, p50, p75, p90}] for each horizon."""
    if not spot or not sigma or sigma <= 0:
        return []
    return [{"days": h, **{f"p{round(p * 100)}": price_at(spot, sigma, h, p, drift) for p in pcts}}
            for h in horizons]


def cone(spot: float, sigma: float, days: int = 252, step: int = 5, drift: float = 0.043) -> dict:
    """Percentile paths for a fan chart: {"days": [...], "p10": [...], ...}."""
    ds = list(range(0, days + 1, step))
    out = {"days": ds}
    for p in PCTS:
        out[f"p{round(p * 100)}"] = [spot if d == 0 else price_at(spot, sigma, d, p, drift) for d in ds]
    return out


def realized_vol(closes, window: int = 252) -> float | None:
    c = [x for x in (closes or [])[-(window + 1):] if x]
    r = [math.log(b / a) for a, b in zip(c[:-1], c[1:]) if a > 0 and b > 0]
    if len(r) < 40:
        return None
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(252)


def coverage(closes, horizon: int = 63, window: int = 252, step: int = 21,
             lo: float = 0.10, hi: float = 0.90) -> dict:
    """Replay the realized-vol range forecast through history: {n, inside,
    above, below} as fractions of forecasts (inside should be about hi - lo)."""
    n = inside = above = below = 0
    for i in range(window, len(closes) - horizon, step):
        s = closes[i]
        sig = realized_vol(closes[:i + 1], window)
        if not s or not sig:
            continue
        a, b = price_at(s, sig, horizon, lo), price_at(s, sig, horizon, hi)
        x = closes[i + horizon]
        n += 1
        if x < a:
            below += 1
        elif x > b:
            above += 1
        else:
            inside += 1
    return {"n": n, "inside": inside / n if n else None, "above": above / n if n else None,
            "below": below / n if n else None, "target": hi - lo}
