"""Wall Street analyst ratings: how many analysts rate a stock a buy, hold or
sell each month (Finnhub, free), the consensus and the average price target
(from the stock's data snapshot). Reported third-party opinions, shown as-is.

``summarize`` is pure (tested); ``ratings`` fetches and caches a day.
"""

from __future__ import annotations

import json
import os
import time

_KEYS = ("strong_buy", "buy", "hold", "sell", "strong_sell")
_LABELS = [(1.5, "Strong buy"), (2.5, "Buy"), (3.5, "Hold"), (4.5, "Sell"), (9, "Strong sell")]


def _score(m: dict) -> float | None:
    """Average rating on the usual 1 (strong buy) to 5 (strong sell) scale."""
    n = sum(m.get(k, 0) for k in _KEYS)
    if not n:
        return None
    return sum((i + 1) * m.get(k, 0) for i, k in enumerate(_KEYS)) / n


def summarize(trend: list[dict], target_mean: float | None = None, price: float | None = None) -> dict:
    """Latest month's split, consensus label, change in the buy share over
    the months shown, and the price target vs the current price."""
    trend = [m for m in trend if sum(m.get(k, 0) for k in _KEYS)]
    out: dict = {"trend": trend, "target_mean": target_mean,
                 "upside": (target_mean / price - 1) if target_mean and price else None}
    if not trend:
        return out
    last = trend[-1]
    n = sum(last.get(k, 0) for k in _KEYS)
    score = _score(last)
    buy = (last.get("strong_buy", 0) + last.get("buy", 0)) / n
    first = trend[0]
    n0 = sum(first.get(k, 0) for k in _KEYS)
    buy0 = (first.get("strong_buy", 0) + first.get("buy", 0)) / n0
    out.update({
        "period": last.get("period"), "analysts": n, "score": score,
        "label": next(lbl for cut, lbl in _LABELS if score <= cut),
        "buy_pct": buy, "hold_pct": last.get("hold", 0) / n,
        "sell_pct": (last.get("sell", 0) + last.get("strong_sell", 0)) / n,
        "buy_change": buy - buy0 if len(trend) > 1 else None, "months": len(trend),
    })
    return out


def ratings(ticker: str, cache_dir: str | None = None) -> list[dict] | None:
    """Monthly rating counts, oldest first, cached a day on disk."""
    path = os.path.join(cache_dir or ".cache", "_analysts", f"{ticker.upper()}.json")
    try:
        if time.time() - os.path.getmtime(path) < 86400:
            return json.load(open(path))
    except OSError:
        pass
    from .earnings import recommendations
    from .finnhub import has_finnhub
    rows = recommendations(ticker, months=6) if has_finnhub() else None
    if rows:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(rows, f)
        os.replace(tmp, path)
        return rows
    try:
        return json.load(open(path))                  # stale beats nothing
    except (OSError, ValueError):
        return None
