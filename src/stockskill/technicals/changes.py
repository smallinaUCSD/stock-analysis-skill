"""Trailing price-change metrics and sparkline series."""

from __future__ import annotations

# trading-day lookbacks for the standard change columns
CHANGE_WINDOWS = {"1d": 1, "5d": 5, "1m": 21, "6m": 126, "1y": 252}


def pct_change(closes, bars: int) -> float | None:
    """Simple return over the last ``bars`` trading days (0.05 == +5%)."""
    seq = list(closes)
    if bars <= 0 or len(seq) <= bars:
        return None
    prev = seq[-1 - bars]
    if prev == 0:
        return None
    return seq[-1] / prev - 1.0


def change_metrics(closes) -> dict[str, float | None]:
    """The standard change columns (Day/5D/1M/6M/1Y) as decimals."""
    return {name: pct_change(closes, n) for name, n in CHANGE_WINDOWS.items()}


def ytd_change(closes, dates) -> float | None:
    """Year-to-date return, using the first close on/after Jan 1 of the last
    date's year. ``dates`` is a parallel sequence of date/datetime objects."""
    seq = list(closes)
    ds = list(dates)
    if not seq or len(seq) != len(ds):
        return None
    year = ds[-1].year
    start_price = next((p for d, p in zip(ds, seq) if d.year == year), None)
    if not start_price:
        return None
    return seq[-1] / start_price - 1.0


def sparkline(closes, bars: int) -> list[float]:
    """Last ``bars`` closes, for drawing a small trend line."""
    seq = list(closes)
    return seq[-bars:] if bars > 0 else []
