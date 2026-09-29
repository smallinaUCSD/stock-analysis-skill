"""Brownian-motion price paths: geometric Brownian motion (log price moves
are normal and independent day to day) for one stock, or correlated
Brownian motions for a portfolio. Returns a fan (percentile bands over time)
and a few sample paths to draw, never a single forecast."""

from __future__ import annotations

import numpy as np

DAYS = 252


def fit(closes: list[float], lookback: int = 3 * DAYS, drift_cap: float = 0.3) -> tuple[float, float]:
    """(annual drift of log price, annual volatility), drift capped at +-30%:
    a stock that doubled last year is not assumed to keep doing it."""
    c = np.asarray([x for x in closes if x and x > 0][-(lookback + 1):], dtype=float)
    r = np.diff(np.log(c))
    if r.size < 30:
        raise ValueError("not enough price history")
    sig = float(r.std(ddof=1) * np.sqrt(DAYS))
    mu = float(r.mean() * DAYS)
    return max(-drift_cap, min(drift_cap, mu)), sig


def fan(log_paths: np.ndarray, start: float, points: int = 64, show: int = 8) -> dict:
    """Percentile bands (5/25/50/75/95) over time and ``show`` sample paths."""
    n_paths, n_days = log_paths.shape
    idx = np.unique(np.linspace(0, n_days - 1, min(points, n_days)).astype(int))
    vals = start * np.exp(log_paths[:, idx])
    q = np.percentile(vals, [5, 25, 50, 75, 95], axis=0)
    end = start * np.exp(log_paths[:, -1])
    return {"t": [int(i) + 1 for i in idx], "start": start,
            "bands": {k: [round(float(x), 4) for x in row] for k, row in zip(("p5", "p25", "p50", "p75", "p95"), q)},
            "samples": [[round(float(x), 4) for x in vals[i]] for i in range(min(show, n_paths))],
            "prob_up": float((end > start).mean()), "mean_end": float(end.mean()),
            "p5_end": float(np.percentile(end, 5)), "p95_end": float(np.percentile(end, 95))}


def one(closes: list[float], days: int = DAYS, n: int = 4000, seed: int = 7) -> dict:
    """One stock's paths from its own drift and volatility."""
    mu, sig = fit(closes)
    rng = np.random.default_rng(seed)
    dt = 1.0 / DAYS
    steps = (mu - sig * sig / 2) * dt + sig * np.sqrt(dt) * rng.standard_normal((n, days))
    return {**fan(np.cumsum(steps, axis=1), float(closes[-1])), "drift": mu, "vol": sig, "days": days}


def portfolio(R: np.ndarray, weights: np.ndarray, days: int = DAYS, n: int = 4000, seed: int = 7,
              start: float = 10_000.0, drift_cap: float = 0.3) -> dict:
    """A portfolio's value paths from correlated Brownian motions (daily
    rebalanced to ``weights``); R is daily log returns (T x assets)."""
    mu = np.clip(R.mean(axis=0) * DAYS, -drift_cap, drift_cap)
    cov = np.cov(R, rowvar=False) * DAYS
    cov = np.atleast_2d(cov)
    L = np.linalg.cholesky(cov + 1e-10 * np.eye(len(mu)))
    rng = np.random.default_rng(seed)
    dt = 1.0 / DAYS
    z = rng.standard_normal((n, days, len(mu))) @ L.T * np.sqrt(dt)
    asset = (mu - np.diag(cov) / 2) * dt + z                      # each asset's daily log return
    port = np.log(np.exp(asset) @ weights)                        # the rebalanced portfolio's log return
    return {**fan(np.cumsum(port, axis=1), start), "days": days}
