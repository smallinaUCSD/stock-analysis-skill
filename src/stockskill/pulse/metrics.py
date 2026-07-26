"""Pure market-pulse math: returns, moving averages, breadth, relative strength.

Every function takes a plain list of closing prices (oldest -> newest) and
returns a number. No network, no dates -- windows are trading-day counts. Fully
unit-tested so the pulse tables are reproducible.
"""

from __future__ import annotations

# common trading-day lookbacks
WINDOWS: dict[str, int] = {"1d": 1, "1w": 5, "1m": 21, "3m": 63, "6m": 126}


def trailing_return(closes: list[float], n: int) -> float | None:
    """Simple return over the last ``n`` trading days. None if not enough data."""
    if n <= 0 or len(closes) <= n:
        return None
    prev = closes[-1 - n]
    if prev == 0:
        return None
    return closes[-1] / prev - 1.0


def moving_average(closes: list[float], n: int) -> float | None:
    if n <= 0 or len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def above_ma(closes: list[float], n: int) -> bool | None:
    ma = moving_average(closes, n)
    if ma is None:
        return None
    return closes[-1] > ma


def relative_strength(a: list[float], b: list[float], n: int) -> float | None:
    """ret(a, n) - ret(b, n). Positive => a is outperforming b over the window."""
    ra, rb = trailing_return(a, n), trailing_return(b, n)
    if ra is None or rb is None:
        return None
    return ra - rb


def pct_positive(returns: list[float | None]) -> float | None:
    """Share of present returns that are > 0 (market breadth)."""
    vals = [r for r in returns if r is not None]
    if not vals:
        return None
    return sum(1 for r in vals if r > 0) / len(vals)


def pct_above_ma(series: list[list[float]], n: int) -> float | None:
    """Share of price series trading above their own ``n``-day moving average."""
    flags = [above_ma(s, n) for s in series]
    present = [f for f in flags if f is not None]
    if not present:
        return None
    return sum(1 for f in present if f) / len(present)
