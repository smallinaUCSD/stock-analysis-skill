"""Daily breakout candidates, and how breakouts have done on this watchlist.

A breakout is a close above the prior 20-day high. Each one is scored on the
confirmations traders and researchers look for:

* near the 52-week high: stocks near their 52-week high keep outperforming
  (George & Hwang, 2004, "The 52-Week High and Momentum Investing", JF);
* volume at least 1.5x its 50-day average (conviction behind the move);
* trend in order: close above the 50-day average, which is above the 200-day;
* relative strength: beating the S&P 500 over the last 3 months;
* a squeeze first: Bollinger bandwidth near its 6-month low the day before
  (a quiet range that resolves upward).

Grade A = 4-5 confirmations, B = 3, C = 0-2. ``backtest`` replays every
historical signal (one per stock per 10 days) and compares forward returns with
the same stocks' ordinary days, so the page can show whether it has worked here.
Pure (numpy) given aligned price arrays.
"""

from __future__ import annotations

import numpy as np

LOOKBACK = 20
COOLDOWN = 10
HORIZONS = (5, 20, 60)


def _sma(x, n):
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = np.full(len(x), np.nan)
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def _rolling_max(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        out[i] = np.max(x[i - n + 1:i + 1])
    return out


def features(close, high, volume, bench=None) -> dict:
    """Per-day arrays needed to score breakouts (index-aligned with close)."""
    c = np.asarray(close, float)
    h = np.asarray(high if high is not None else close, float)
    v = np.asarray(volume if volume is not None else np.ones(len(c)), float)
    n = len(c)
    prior_hi = np.full(n, np.nan)
    prior_hi[LOOKBACK:] = _rolling_max(c, LOOKBACK)[LOOKBACK - 1:-1]
    hi52 = _rolling_max(h, 252) if n >= 252 else np.full(n, np.nan)
    vavg = np.full(n, np.nan)
    vavg[50:] = _sma(v, 50)[49:-1]
    s50, s200 = _sma(c, 50), _sma(c, 200) if n >= 200 else np.full(n, np.nan)
    ret63 = np.full(n, np.nan)
    ret63[63:] = c[63:] / c[:-63] - 1.0
    rs = np.full(n, np.nan)
    if bench is not None and len(bench) == n and np.isfinite(np.asarray(bench, float)).any():
        b = np.asarray(bench, float)
        b63 = np.full(n, np.nan)
        b63[63:] = b[63:] / b[:-63] - 1.0
        rs = ret63 - b63
    # Bollinger bandwidth (20, 2) and where yesterday's sat in its last 126 days
    mid = _sma(c, 20)
    sd = np.full(n, np.nan)
    for i in range(19, n):
        sd[i] = np.std(c[i - 19:i + 1])
    bw = 4 * sd / mid
    bw_pct = np.full(n, np.nan)
    for i in range(146, n):
        win = bw[i - 126:i]
        bw_pct[i] = np.mean(win <= bw[i - 1])
    return {"c": c, "prior_hi": prior_hi, "hi52": hi52, "rvol": v / vavg, "s50": s50, "s200": s200,
            "rs": rs, "bw_pct": bw_pct}


def score_day(f: dict, i: int) -> dict | None:
    """The breakout read for day ``i`` (None when it isn't a breakout)."""
    c, ph = f["c"][i], f["prior_hi"][i]
    if not np.isfinite(ph) or c <= ph:
        return None
    checks = {
        "near_52w_high": bool(np.isfinite(f["hi52"][i]) and c >= 0.98 * f["hi52"][i]),
        "volume": bool(np.isfinite(f["rvol"][i]) and f["rvol"][i] >= 1.5),
        "trend": bool(np.isfinite(f["s200"][i]) and c > f["s50"][i] > f["s200"][i]),
        "relative_strength": bool(np.isfinite(f["rs"][i]) and f["rs"][i] > 0),
        "squeeze": bool(np.isfinite(f["bw_pct"][i]) and f["bw_pct"][i] <= 0.30),
    }
    n = sum(checks.values())
    return {"score": n, "grade": "A" if n >= 4 else ("B" if n == 3 else "C"), "checks": checks,
            "level": float(ph), "above": float(c / ph - 1.0),
            "rvol": None if not np.isfinite(f["rvol"][i]) else float(f["rvol"][i]),
            "from_52w_high": None if not np.isfinite(f["hi52"][i]) else float(c / f["hi52"][i] - 1.0),
            "rs_3m": None if not np.isfinite(f["rs"][i]) else float(f["rs"][i])}


def bench_on(dates, bench_dates, bench_close):
    """The benchmark's close on each of ``dates`` (last known value carried
    forward over any gap), so relative strength uses the stock's own calendar."""
    key = [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in bench_dates]
    m = dict(zip(key, bench_close))
    out, last = [], np.nan
    for d in dates:
        v = m.get(d.isoformat() if hasattr(d, "isoformat") else str(d))
        last = v if v is not None else last
        out.append(last)
    return np.asarray(out, float)


def scan(universe: dict) -> list[dict]:
    """Today's breakouts. ``universe``: {ticker: {close, high, volume, bench}}
    (``bench`` = the S&P 500 on the stock's own dates, optional). Best first."""
    out = []
    for t, u in universe.items():
        c = u["close"]
        if len(c) < 60:
            continue
        f = features(c, u.get("high"), u.get("volume"), u.get("bench"))
        s = score_day(f, len(c) - 1)
        if s:
            out.append({"ticker": t, "close": float(c[-1]),
                        "change": float(c[-1] / c[-2] - 1.0) if len(c) > 1 and c[-2] else None, **s})
    out.sort(key=lambda r: (r["score"], r["rvol"] or 0), reverse=True)
    return out


def backtest(universe: dict, horizons=HORIZONS) -> dict:
    """Forward returns after historical breakouts by grade vs the same stocks'
    ordinary days. {grade: {n, h: {mean, excess, hit}}, "base": {...}}."""
    sig: dict = {"A": [], "B": [], "C": []}
    base: dict = {h: [] for h in horizons}
    hmax = max(horizons)
    for t, u in universe.items():
        c = np.asarray(u["close"], float)
        if len(c) < 260 + hmax:
            continue
        f = features(c, u.get("high"), u.get("volume"), u.get("bench"))
        last = -COOLDOWN
        for i in range(252, len(c) - hmax):
            fw = {h: c[i + h] / c[i] - 1.0 for h in horizons}
            for h in horizons:
                base[h].append(fw[h])
            if i - last < COOLDOWN:
                continue
            s = score_day(f, i)
            if s:
                sig[s["grade"]].append(fw)
                last = i
    base_mean = {h: float(np.mean(base[h])) if base[h] else None for h in horizons}
    out = {"base": {h: {"mean": base_mean[h], "hit": float(np.mean(np.array(base[h]) > 0)) if base[h] else None}
                    for h in horizons}}
    for g, rows in sig.items():
        stats = {}
        for h in horizons:
            vals = np.array([r[h] for r in rows]) if rows else np.array([])
            stats[h] = {"mean": float(vals.mean()) if len(vals) else None,
                        "excess": float(vals.mean() - base_mean[h]) if len(vals) and base_mean[h] is not None else None,
                        "hit": float(np.mean(vals > 0)) if len(vals) else None}
        out[g] = {"n": len(rows), **{str(h): stats[h] for h in horizons}}
    out["base"] = {str(h): v for h, v in out["base"].items()}
    return out
