"""Dividends: yield, the last twelve months' payout, yearly totals, growth,
years of consecutive increases, payment frequency, payout ratio and the
next ex-dividend date.

History comes from Yahoo (every payment, split-adjusted), cached a day.
``summarize`` is pure (tested).
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta

_FREQ = [(11, "Monthly"), (4, "Quarterly"), (2, "Twice a year"), (1, "Once a year")]


def summarize(history: list[tuple[str, float]], price: float | None, eps: float | None = None,
              next_ex: str | None = None, today: date | None = None) -> dict:
    """``history``: [(iso date, amount per share)] oldest first."""
    today = today or date.today()
    pays = [(date.fromisoformat(d), float(a)) for d, a in history if a and a > 0]
    if not pays:
        return {"pays": False}
    year_ago = today - timedelta(days=365)
    last12 = [a for d, a in pays if d > year_ago]
    ttm = sum(last12)
    by_year: dict[int, float] = {}
    each: dict[int, list] = {}
    for d, a in pays:
        by_year[d.year] = by_year.get(d.year, 0.0) + a
        each.setdefault(d.year, []).append(a)
    # each year's typical payment (the median shrugs off a special dividend or
    # two payments merged into one in the data)
    rate = {y: sorted(v)[len(v) // 2] if len(v) % 2 else sum(sorted(v)[len(v) // 2 - 1:len(v) // 2 + 1]) / 2
            for y, v in each.items()}
    full = sorted(y for y in by_year if y < today.year)
    # years in a row the payment was raised (payment timing can't break it,
    # unlike yearly totals, which wobble when a payment slips into another year)
    streak = 0
    for y in reversed(full):
        prev = rate.get(y - 1)
        if prev and rate[y] > prev * 1.001:
            streak += 1
        else:
            break

    def cagr(n):
        if len(full) <= n:
            return None
        a, b = by_year.get(full[-1 - n]), by_year.get(full[-1])
        return (b / a) ** (1 / n) - 1 if a and b and a > 0 else None
    freq = next((lbl for k, lbl in _FREQ if len(last12) >= k), None) if last12 else None
    last_d, last_a = pays[-1]
    return {
        "pays": bool(last12),                     # still paying (anything in the last year)
        "ttm": ttm, "yield": ttm / price if price and ttm else None,
        "frequency": freq, "last_date": last_d.isoformat(), "last_amount": last_a,
        "next_ex": next_ex if next_ex and next_ex >= today.isoformat() else None,
        "payout_ratio": ttm / eps if eps and eps > 0 and ttm else None,
        "growth_1y": cagr(1), "growth_5y": cagr(5), "growth_10y": cagr(10),
        "streak": streak, "since": pays[0][0].year,
        "years": [{"year": y, "total": round(by_year[y], 4)} for y in sorted(by_year)[-11:]],
    }


def history(ticker: str, cache_dir: str | None = None) -> dict | None:
    """{"history": [(date, amount)], "next_ex": iso|None}, cached a day."""
    path = os.path.join(cache_dir or ".cache", "_dividends", f"{ticker.upper()}.json")
    try:
        if time.time() - os.path.getmtime(path) < 86400:
            return json.load(open(path))
    except OSError:
        pass
    out = None
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        s = tk.dividends
        hist = [(i.date().isoformat(), float(v)) for i, v in s.items()] if s is not None else []
        nxt = None
        try:
            ts = (tk.info or {}).get("exDividendDate")
            if isinstance(ts, (int, float)) and ts > 0:
                nxt = datetime.fromtimestamp(ts).date().isoformat()
        except Exception:  # noqa: BLE001
            pass
        out = {"history": hist, "next_ex": nxt}
    except Exception:  # noqa: BLE001
        out = None
    if out is not None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(out, f)
        os.replace(tmp, path)
        return out
    try:
        return json.load(open(path))                  # stale beats nothing
    except (OSError, ValueError):
        return None
