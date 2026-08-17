"""Factor backtest: does the signal actually sort future returns?

At each monthly rebalance we rank the universe by a factor signal, split into
buckets, and measure each bucket's *forward* return. A working factor shows a
monotonic gradient (top bucket beats bottom) and a positive long-short spread
and information coefficient (IC = rank correlation of signal vs forward return).

Only momentum is backtestable from the data on hand (it's price-derived, and we
have 5y of daily closes). Value/quality need point-in-time historical
fundamentals; the panel/run split here lets them plug in unchanged once those
exist. No look-ahead: the signal at date d uses prices up to d, the return is
measured strictly after d.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date, timedelta

from ..screener.criteria import percentile_ranks


def _asof(dates: list[date], closes: list[float], target: date) -> float | None:
    """Last close on or before ``target``; None if the history doesn't reach it."""
    i = bisect.bisect_right(dates, target) - 1
    if i < 0:
        return None
    v = closes[i]
    return v if (v and v == v) else None


def _month_ends(start: date, end: date) -> list[date]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        nm_y, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        last = date(nm_y, nm, 1) - timedelta(days=1)   # last day of month (y, m)
        if start <= last <= end:
            out.append(last)
        y, m = nm_y, nm
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation (Spearman) of paired samples. None if degenerate."""
    if len(xs) < 3:
        return None
    rx = percentile_ranks(xs)
    ry = percentile_ranks(ys)
    pairs = [(a, b) for a, b in zip(rx, ry) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    n = len(pairs)
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    cov = sum((a - mx) * (b - my) for a, b in pairs)
    vx = sum((a - mx) ** 2 for a, _ in pairs)
    vy = sum((b - my) ** 2 for _, b in pairs)
    if vx <= 0 or vy <= 0:
        return None
    return cov / (vx * vy) ** 0.5


def bucket_returns(signals: dict[str, float], fwd: dict[str, float],
                   n_buckets: int = 5) -> dict | None:
    """One rebalance: sort by signal into ``n_buckets``, mean forward return each.

    Returns {buckets: [low..high mean fwd ret], long_short, ic} or None if too thin.
    """
    common = [(t, signals[t], fwd[t]) for t in signals
              if t in fwd and signals[t] == signals[t] and fwd[t] == fwd[t]]
    if len(common) < n_buckets * 2:
        return None
    common.sort(key=lambda r: r[1])                    # ascending by signal
    n = len(common)
    means = []
    for b in range(n_buckets):
        lo = b * n // n_buckets
        hi = (b + 1) * n // n_buckets
        chunk = common[lo:hi]
        means.append(sum(r[2] for r in chunk) / len(chunk))
    ic = spearman([r[1] for r in common], [r[2] for r in common])
    return {"buckets": means, "long_short": means[-1] - means[0], "ic": ic}


@dataclass
class BacktestResult:
    factor: str
    n_periods: int
    bucket_avg: list[float]          # mean monthly forward return, low..high signal
    long_short_avg: float            # mean monthly (top - bottom)
    long_short_annual: float
    hit_rate: float                  # share of months long-short > 0
    ic_avg: float | None
    ls_curve: list[float]            # cumulative growth of $1 long-short
    start: str
    end: str


def momentum_panel(price_data: dict[str, tuple[list[date], list[float]]],
                   lookback_days: int = 365, skip_days: int = 30,
                   hold_days: int = 30):
    """Build (signals_by_date, fwd_by_date) for 12-1 momentum from price series."""
    all_dates = [d for dc in price_data.values() for d in dc[0]]
    if not all_dates:
        return {}, []
    lo, hi = min(all_dates), max(all_dates)
    rebals = _month_ends(lo + timedelta(days=lookback_days + 5),
                         hi - timedelta(days=hold_days + 2))
    signals_by_date, fwd_by_date = {}, {}
    for d in rebals:
        sig, fwd = {}, {}
        for tk, (dates, closes) in price_data.items():
            c12 = _asof(dates, closes, d - timedelta(days=lookback_days))
            c1 = _asof(dates, closes, d - timedelta(days=skip_days))
            c0 = _asof(dates, closes, d)
            cf = _asof(dates, closes, d + timedelta(days=hold_days))
            if c12 and c1 and c0 and cf and c12 > 0 and c0 > 0:
                sig[tk] = c1 / c12 - 1.0
                fwd[tk] = cf / c0 - 1.0
        if sig:
            signals_by_date[d] = sig
            fwd_by_date[d] = fwd
    return signals_by_date, fwd_by_date


def run_backtest(signals_by_date: dict, fwd_by_date: dict, factor: str = "momentum",
                 n_buckets: int = 5) -> BacktestResult | None:
    dates = sorted(signals_by_date)
    per_bucket = [[] for _ in range(n_buckets)]
    ls, ics, curve, growth = [], [], [], 1.0
    for d in dates:
        r = bucket_returns(signals_by_date[d], fwd_by_date[d], n_buckets)
        if not r:
            continue
        for b, m in enumerate(r["buckets"]):
            per_bucket[b].append(m)
        ls.append(r["long_short"])
        if r["ic"] is not None:
            ics.append(r["ic"])
        growth *= 1.0 + r["long_short"]
        curve.append(growth)
    if not ls:
        return None
    bucket_avg = [sum(b) / len(b) if b else 0.0 for b in per_bucket]
    ls_avg = sum(ls) / len(ls)
    hit = sum(1 for x in ls if x > 0) / len(ls)
    used = [d for d in dates if bucket_returns(signals_by_date[d], fwd_by_date[d], n_buckets)]
    return BacktestResult(
        factor=factor, n_periods=len(ls), bucket_avg=bucket_avg,
        long_short_avg=ls_avg, long_short_annual=(1.0 + ls_avg) ** 12 - 1.0,
        hit_rate=hit, ic_avg=(sum(ics) / len(ics) if ics else None),
        ls_curve=curve, start=used[0].isoformat(), end=used[-1].isoformat())
