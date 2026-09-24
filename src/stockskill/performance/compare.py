"""Side-by-side comparison of 2-4 tickers: growth of $10k, drawdowns, trailing
returns, risk vs SPY, return correlations and fund-holdings overlap.

Pure functions over price series and holdings weights; the server fetches.
"""

from __future__ import annotations

from datetime import date

from .metrics import (TRADING_DAYS, align_closes, annual_vol, cagr, correlation,
                      drawdown_series, max_drawdown, risk_stats, sharpe,
                      simple_returns, sortino)

PERIOD_DAYS = {"1y": 252, "3y": 756, "5y": 1260, "max": None}

# (label, trading days, annualize?) — YTD handled separately
RETURN_WINDOWS = [("1M", 21, False), ("3M", 63, False), ("6M", 126, False),
                  ("YTD", None, False), ("1Y", 252, False),
                  ("3Y", 756, True), ("5Y", 1260, True)]


def _iso(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def trailing_returns(dates, closes) -> dict:
    """{label: return or None} over each window, from the ticker's own history.
    3Y and 5Y are annualized; the rest are total returns."""
    out: dict = {}
    n = len(closes)
    for label, days, annualize in RETURN_WINDOWS:
        if label == "YTD":
            out[label] = _ytd(dates, closes)
            continue
        if n <= days or not closes[-1 - days]:
            out[label] = None
            continue
        r = closes[-1] / closes[-1 - days] - 1.0
        out[label] = (1.0 + r) ** (TRADING_DAYS / days) - 1.0 if annualize else r
    return out


def _ytd(dates, closes):
    if not dates:
        return None
    year = _iso(dates[-1])[:4]
    prior = [i for i, d in enumerate(dates) if _iso(d)[:4] < year]
    if not prior or not closes[prior[-1]]:
        return None
    return closes[-1] / closes[prior[-1]] - 1.0


def _sample_idx(n: int, max_points: int = 420) -> list[int]:
    """Evenly spaced indices (always keeping the first and last point)."""
    if n <= max_points:
        return list(range(n))
    step = (n - 1) / (max_points - 1)
    idx = sorted({round(i * step) for i in range(max_points)} | {n - 1})
    return idx


def _common(series: dict) -> list[str]:
    """ISO dates every ticker traded on, oldest first."""
    sets = [{_iso(d) for d in s["dates"]} for s in series.values()]
    return sorted(set.intersection(*sets)) if sets else []


def compare(series: dict, period: str = "5y", bench: dict | None = None,
            bench_name: str = "SPY", rf_annual: float = 0.043) -> dict:
    """Compare tickers over their common history (capped at ``period``).

    ``series``: {ticker: {"dates": [...], "closes": [...]}} in display order.
    ``bench``: {"dates", "closes"} for beta/alpha (optional).
    """
    tickers = list(series)
    common = _common(series)
    cap = PERIOD_DAYS.get(period)
    if cap:
        common = common[-(cap + 1):]
    if len(common) < 30:
        return {"ok": False, "error": "not enough shared price history to compare"}

    aligned = {}
    for t in tickers:
        m = {_iso(d): c for d, c in zip(series[t]["dates"], series[t]["closes"])}
        aligned[t] = [float(m[d]) for d in common]
    idx = _sample_idx(len(common))
    days = len(common) - 1

    # the ticker whose shorter history set the start date, if any
    starts = {t: _iso(series[t]["dates"][0]) for t in tickers if series[t]["dates"]}
    limited_by = None
    if cap is None or len(common) < cap + 1:
        latest = max(starts.values()) if starts else None
        if latest and latest == common[0] and latest > min(starts.values()):
            limited_by = [t for t, s in starts.items() if s == latest][0]

    rows = []
    rets = {t: simple_returns(aligned[t]) for t in tickers}
    for t in tickers:
        c = aligned[t]
        rs = None
        if bench and t != bench_name:
            rs = risk_stats(common, c, bench["dates"], bench["closes"],
                            benchmark=bench_name, window=days, rf_annual=rf_annual)
        rows.append({
            "ticker": t,
            "growth": [round(10000.0 * c[i] / c[0], 2) for i in idx],
            "drawdown": [round(v, 4) for v in (drawdown_series(c)[i] for i in idx)],
            "total_return": c[-1] / c[0] - 1.0,
            "cagr": cagr(c, days) if days >= TRADING_DAYS else None,
            "vol": annual_vol(rets[t]),
            "sharpe": sharpe(rets[t], rf_annual),
            "sortino": sortino(rets[t], rf_annual),
            "max_drawdown": max_drawdown(c),
            "beta": rs.beta if rs else (1.0 if t == bench_name else None),
            "alpha": rs.alpha if rs else None,
            "alpha_t": rs.alpha_t if rs else None,
            "alpha_significant": rs.alpha_significant if rs else False,
            "returns": trailing_returns(series[t]["dates"], series[t]["closes"]),
        })

    corr = [[1.0 if a == b else correlation(rets[a], rets[b]) for b in tickers]
            for a in tickers]
    return {"ok": True, "tickers": tickers, "start": common[0], "end": common[-1],
            "days": days, "years": round(days / TRADING_DAYS, 2),
            "limited_by": limited_by, "dates": [common[i] for i in idx],
            "rows": rows, "correlation": corr, "benchmark": bench_name,
            "as_of": date.today().isoformat()}


def holdings_overlap(weights: dict) -> list[list]:
    """Pairwise overlap matrix: the share of holdings (by weight) two funds hold
    in common, i.e. the sum over shared names of min(weight_a, weight_b).

    ``weights``: {ticker: {underlying: weight fraction}} (a plain stock is
    {itself: 1.0}). With only top holdings known it's a LOWER bound."""
    tks = list(weights)
    out = []
    for a in tks:
        row = []
        for b in tks:
            if a == b:
                row.append(1.0)
                continue
            wa, wb = weights[a] or {}, weights[b] or {}
            row.append(sum(min(wa[k], wb[k]) for k in wa.keys() & wb.keys()))
        out.append(row)
    return out
