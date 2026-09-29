"""Mean-variance (Markowitz) and Black-Litterman portfolios, long-only with a
per-stock cap, in plain numpy (no solver needed at this size).

* ``estimate``: annual expected returns and a covariance matrix from daily
  prices, the covariance shrunk toward its diagonal (Ledoit-Wolf style, fixed
  intensity) so a few noisy correlations don't drive the answer.
* ``solve``: maximize  w'mu - (lam/2) w'Sigma w  over the capped simplex by
  projected gradient ascent. Sweeping lam traces the efficient frontier.
* ``black_litterman``: the market's implied returns (pi = delta Sigma w_mkt)
  blended with views (here: analysts' 12-month price targets) weighted by how
  confident each view is.

Historical means are noisy estimates of future returns; the page says so.
"""

from __future__ import annotations

import math

import numpy as np

DAYS = 252


def align(series: dict, lookback: int = 3 * DAYS, min_days: int = 2 * DAYS) -> tuple[list[str], np.ndarray]:
    """{ticker: (dates, closes)} -> (tickers, daily log returns T x n) over the
    dates all of them share (the last ``lookback`` of them). Stocks with less
    than ``min_days`` of history are left out when enough others have it, so a
    recent listing doesn't shrink everyone's window."""
    common = None
    maps = {}
    for t, (dates, closes) in series.items():
        m = {d: c for d, c in zip(dates, closes) if c and c > 0}
        if len(m) >= 60:
            maps[t] = m
    long_ = {t: m for t, m in maps.items() if len(m) >= min_days}
    if len(long_) >= 2:
        maps = long_
    for m in maps.values():
        common = set(m) if common is None else common & set(m)
    tickers = sorted(maps)
    if not tickers or not common or len(common) < 60:
        return [], np.zeros((0, 0))
    days = sorted(common)[-(lookback + 1):]
    px = np.array([[maps[t][d] for t in tickers] for d in days], dtype=float)
    return tickers, np.diff(np.log(px), axis=0)


def estimate(R: np.ndarray, shrink: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """Annual arithmetic mean returns and shrunk annual covariance."""
    mu = R.mean(axis=0) * DAYS + R.var(axis=0, ddof=1) * DAYS / 2       # log -> simple (approx.)
    S = np.cov(R, rowvar=False, ddof=1) * DAYS
    S = np.atleast_2d(S)
    S = (1 - shrink) * S + shrink * np.diag(np.diag(S))
    return mu, S


def blend(mu_hist: np.ndarray, pi: np.ndarray, weight: float = 0.5, lo: float = -0.3, hi: float = 0.6) -> np.ndarray:
    """Expected returns for the optimizer: past returns shrunk halfway toward the
    market-implied ones and capped, so a recent run-up doesn't dominate."""
    return np.clip(weight * mu_hist + (1 - weight) * pi, lo, hi)


def project(v: np.ndarray, cap: float) -> np.ndarray:
    """Closest point to v with 0 <= w <= cap and sum(w) = 1 (bisection on the shift)."""
    lo, hi = v.min() - cap - 1, v.max() + 1
    for _ in range(100):
        tau = (lo + hi) / 2
        s = np.clip(v - tau, 0, cap).sum()
        if s > 1:
            lo = tau
        else:
            hi = tau
    return np.clip(v - (lo + hi) / 2, 0, cap)


def solve(mu: np.ndarray, S: np.ndarray, lam: float, cap: float, iters: int = 600) -> np.ndarray:
    n = len(mu)
    cap = max(cap, 1.0 / n + 1e-9)
    L = max(float(np.linalg.eigvalsh(S).max()) * lam, 1e-9)
    w = project(np.full(n, 1.0 / n), cap)
    step = 1.0 / L
    for _ in range(iters):
        w_new = project(w + step * (mu - lam * S @ w), cap)
        if np.abs(w_new - w).max() < 1e-9:
            w = w_new
            break
        w = w_new
    return w


def stats(w: np.ndarray, mu: np.ndarray, S: np.ndarray, rf: float) -> dict:
    ret = float(w @ mu)
    vol = float(math.sqrt(max(w @ S @ w, 0.0)))
    return {"ret": ret, "vol": vol, "sharpe": (ret - rf) / vol if vol > 0 else None}


def frontier(mu: np.ndarray, S: np.ndarray, cap: float, rf: float = 0.04, points: int = 24) -> dict:
    """The efficient frontier plus the minimum-risk and best risk-adjusted (max Sharpe) mixes."""
    lams = np.logspace(-1.3, 2.7, points)
    pts = []
    for lam in lams:
        w = solve(mu, S, float(lam), cap)
        pts.append({**stats(w, mu, S, rf), "w": w})
    minvar = solve(np.zeros_like(mu), S, 1.0, cap)
    pts.append({**stats(minvar, mu, S, rf), "w": minvar})
    best = max((p for p in pts if p["sharpe"] is not None), key=lambda p: p["sharpe"])
    mv = min(pts, key=lambda p: p["vol"])
    curve = sorted(({"ret": p["ret"], "vol": p["vol"]} for p in pts), key=lambda p: p["vol"])
    return {"curve": curve, "max_sharpe": best, "min_var": mv}


def black_litterman(S: np.ndarray, w_mkt: np.ndarray, views: dict, delta: float = 2.5,
                    tau: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """(pi, posterior mu). ``views``: {index: (expected annual return, confidence 0..1)}.
    Uncertainty of a view shrinks as confidence rises (Idzorek-style scaling)."""
    pi = delta * S @ w_mkt
    if not views:
        return pi, pi.copy()
    n = len(w_mkt)
    idx = sorted(views)
    P = np.zeros((len(idx), n))
    Q = np.zeros(len(idx))
    om = np.zeros(len(idx))
    for k, i in enumerate(idx):
        q, c = views[i]
        P[k, i] = 1.0
        Q[k] = q
        c = min(max(c, 0.05), 0.95)
        om[k] = tau * S[i, i] * (1 - c) / c
    tS_inv = np.linalg.inv(tau * S)
    O_inv = np.diag(1.0 / om)
    A = tS_inv + P.T @ O_inv @ P
    b = tS_inv @ pi + P.T @ O_inv @ Q
    return pi, np.linalg.solve(A, b)


def analyst_views(tickers: list[str], snaps: dict, max_abs: float = 0.4) -> dict:
    """{i: (q, confidence)} from 12-month price targets: q = target/price - 1,
    capped; confidence grows with the number of analysts (up to 0.6)."""
    out = {}
    for i, t in enumerate(tickers):
        s = snaps.get(t)
        if not s or not s.get("target") or not s.get("price"):
            continue
        q = max(-max_abs, min(max_abs, s["target"] / s["price"] - 1))
        n = s.get("analysts") or 1
        out[i] = (q, min(0.6, 0.1 + 0.02 * n))
    return out
