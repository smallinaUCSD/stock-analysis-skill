"""Pairs (relative value): find stocks that have moved together, flag when
their prices have stretched apart, and test how that worked historically.

Gatev, Goetzmann & Rouwenhorst (2006), "Pairs Trading: Performance of a
Relative-Value Arbitrage Rule" (Review of Financial Studies): over a 12-month
formation window, pair each stock with the one whose normalized price path is
closest (smallest sum of squared differences); over the next 6 months, open a
trade when the normalized spread moves more than 2 formation standard
deviations apart (long the laggard, short the leader, $1 each) and close it
when the prices cross back. They found profits through the 1990s that have
since shrunk; Avellaneda & Lee (2010) found the same fade after 2002.

Pure functions over aligned close lists. No transaction costs or short fees
are modelled, so real results would be lower.
"""

from __future__ import annotations

import math

FORMATION = 252
TRADING = 126


def _norm(c):
    return [x / c[0] for x in c] if c and c[0] else []


def _std(xs):
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _corr_returns(a, b):
    ra = [y / x - 1 for x, y in zip(a[:-1], a[1:]) if x]
    rb = [y / x - 1 for x, y in zip(b[:-1], b[1:]) if x]
    n = min(len(ra), len(rb))
    if n < 20:
        return 0.0
    ra, rb = ra[-n:], rb[-n:]
    ma, mb = sum(ra) / n, sum(rb) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in ra))
    sb = math.sqrt(sum((x - mb) ** 2 for x in rb))
    if not sa or not sb:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (sa * sb)


def select_pairs(window: dict, groups: dict, top: int = 20, min_corr: float = 0.6,
                 max_corr: float = 0.995) -> list[tuple[str, str, float]]:
    """Closest pairs within the same group over ``window`` {ticker: closes}.

    Returns [(a, b, ssd)] smallest distance first. Pairs whose daily returns are
    near-identical (share classes, ``max_corr``) or barely related are skipped."""
    tks = sorted(t for t in window if groups.get(t) and len(window[t]) >= 30)
    norm = {t: _norm(window[t]) for t in tks}
    out = []
    for i, a in enumerate(tks):
        for b in tks[i + 1:]:
            if groups[a] != groups[b]:
                continue
            na, nb = norm[a], norm[b]
            n = min(len(na), len(nb))
            if n < 30:
                continue
            c = _corr_returns(window[a][-n:], window[b][-n:])
            if not (min_corr <= c <= max_corr):
                continue
            out.append((a, b, sum((x - y) ** 2 for x, y in zip(na[-n:], nb[-n:]))))
    out.sort(key=lambda x: x[2])
    return out[:top]


def trade_pair(a, b, formation: int = FORMATION, entry: float = 2.0) -> list[dict]:
    """Trades on one pair: closes ``a``/``b`` cover formation + trading days.

    Spread = normalized a - normalized b (both scaled to the formation start);
    sigma from the formation window. Returns [{open, close, ret, converged}]."""
    if len(a) <= formation + 1 or len(b) != len(a) or not a[0] or not b[0]:
        return []
    na, nb = _norm(a), _norm(b)
    spread = [x - y for x, y in zip(na, nb)]
    sigma = _std(spread[:formation])
    if sigma <= 0:
        return []
    trades, pos = [], None
    for t in range(formation, len(a)):
        s = spread[t]
        if pos is None:
            if abs(s) > entry * sigma:
                pos = {"open": t, "sign": 1 if s > 0 else -1}    # +1: a rich -> short a, long b
        else:
            crossed = (s <= 0) if pos["sign"] > 0 else (s >= 0)
            if crossed or t == len(a) - 1:
                o = pos["open"]
                ra, rb = a[t] / a[o] - 1.0, b[t] / b[o] - 1.0
                ret = (rb - ra) if pos["sign"] > 0 else (ra - rb)
                trades.append({"open": o, "close": t, "ret": ret, "converged": crossed})
                pos = None
    return trades


def align_to(master_dates, series: dict) -> dict:
    """{ticker: closes on ``master_dates``} with None where a ticker has no bar
    (not yet listed, or a missing day). ``series``: {ticker: (dates, closes)}."""
    def key(d):
        return d.isoformat() if hasattr(d, "isoformat") else str(d)
    keys = [key(d) for d in master_dates]
    out = {}
    for t, (dates, cl) in series.items():
        m = {key(d): c for d, c in zip(dates or [], cl or [])}
        out[t] = [m.get(k) for k in keys]
    return out


def backtest(closes: dict, groups: dict, formation: int = FORMATION, trading: int = TRADING,
             top: int = 20, entry: float = 2.0) -> dict | None:
    """Rolling GGR test over aligned ``closes`` {ticker: [..]} (same length;
    None = no bar). Each period uses the tickers with a full formation + trading
    window, picks ``top`` pairs on the formation window and trades them over the
    next ``trading`` days. Returns per-trade statistics, or None if too short."""
    lens = {len(v) for v in closes.values()}
    if not closes or len(lens) != 1:
        return None
    n = lens.pop()
    rets, days, conv, periods = [], [], 0, 0
    start = 0
    while start + formation + trading <= n:
        form = {t: c[start:start + formation] for t, c in closes.items()
                if None not in c[start:start + formation + trading]}
        pairs = select_pairs(form, groups, top=top)
        periods += 1
        for a, b, _ in pairs:
            seg_a = closes[a][start:start + formation + trading]
            seg_b = closes[b][start:start + formation + trading]
            for tr in trade_pair(seg_a, seg_b, formation, entry):
                rets.append(tr["ret"])
                days.append(tr["close"] - tr["open"])
                conv += 1 if tr["converged"] else 0
        start += trading
    if not periods:
        return None
    k = len(rets)
    srt = sorted(rets)
    return {"periods": periods, "years": round(n / 252, 1), "trades": k,
            "mean": (sum(rets) / k) if k else None,
            "median": (srt[k // 2] if k % 2 else (srt[k // 2 - 1] + srt[k // 2]) / 2) if k else None,
            "win_rate": (sum(1 for r in rets if r > 0) / k) if k else None,
            "avg_days": (sum(days) / k) if k else None,
            "converged": (conv / k) if k else None}


def stretched_now(closes: dict, groups: dict, formation: int = FORMATION, top: int = 30,
                  threshold: float = 2.0) -> list[dict]:
    """Current pairs (picked on the last ``formation`` days) with their spread
    z-score today; those beyond ``threshold`` are flagged ``stretched``."""
    window = {t: c[-formation:] for t, c in closes.items()
              if len(c) >= formation and None not in c[-formation:]}
    out = []
    for a, b, d in select_pairs(window, groups, top=top):
        na, nb = _norm(window[a]), _norm(window[b])
        spread = [x - y for x, y in zip(na, nb)]
        sd = _std(spread)
        if sd <= 0:
            continue
        m = sum(spread) / len(spread)
        z = (spread[-1] - m) / sd
        rich, cheap = (a, b) if z > 0 else (b, a)
        out.append({"a": a, "b": b, "z": z, "stretched": abs(z) >= threshold,
                    "rich": rich, "cheap": cheap, "group": groups.get(a),
                    "corr": _corr_returns(window[a], window[b])})
    out.sort(key=lambda x: abs(x["z"]), reverse=True)
    return out


def spread_z_series(a, b, lookback: int = FORMATION) -> list[float | None]:
    """Rolling z-score of the log price ratio log(a/b) against its trailing
    ``lookback``-day mean and deviation (None until enough history)."""
    lr = [math.log(x / y) if x and y else None for x, y in zip(a, b)]
    out: list[float | None] = []
    for i in range(len(lr)):
        w = [v for v in lr[max(0, i - lookback + 1):i + 1] if v is not None]
        if len(w) < min(60, lookback) or lr[i] is None:
            out.append(None)
            continue
        sd = _std(w)
        out.append(((lr[i] - sum(w) / len(w)) / sd) if sd > 0 else None)
    return out
