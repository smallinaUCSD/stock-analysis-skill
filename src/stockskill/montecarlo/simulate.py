"""Monte Carlo price-path simulation — the "model" (this project's ML step).

Two engines, both pure and deterministic given a seed:
* **GBM** — geometric Brownian motion from an estimated drift & volatility.
* **Bootstrap** — resample the ticker's own historical daily returns (captures
  fat tails / skew the normal misses).

"Training" here is parameter estimation: drift & vol are fit from the ticker's
history (and can be nudged by the market climate). Outputs are a distribution of
outcomes — probability of a >X% gain / >Y% loss, expected return, percentile
bands, and VaR — never a point prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TRADING_DAYS = 252


def daily_returns(closes) -> list[float]:
    c = [x for x in closes if x == x]
    return [c[i] / c[i - 1] - 1.0 for i in range(1, len(c)) if c[i - 1]]


def estimate_params(returns, annualize: int = TRADING_DAYS) -> tuple[float, float]:
    """Fit annualized drift & volatility from daily returns (the 'training')."""
    r = np.asarray(list(returns), dtype=float)
    if r.size < 2:
        return (0.0, 0.0)
    mu_d = float(r.mean())
    sig_d = float(r.std(ddof=1))
    return (mu_d * annualize, sig_d * np.sqrt(annualize))


def _simulate_gbm(drift: float, vol: float, days: int, n_paths: int,
                  rng, drift_adj: float = 0.0) -> np.ndarray:
    """Terminal simple returns from GBM (log-normal). ``drift_adj`` shifts the
    annual drift (e.g. a market-climate nudge)."""
    mu_d = (drift + drift_adj) / TRADING_DAYS
    sig_d = vol / np.sqrt(TRADING_DAYS)
    log_mu = mu_d - 0.5 * sig_d ** 2          # Ito correction so E[return]≈drift
    shocks = rng.normal(log_mu, sig_d, size=(n_paths, days))
    return np.exp(shocks.sum(axis=1)) - 1.0


def _simulate_bootstrap(hist_returns, days: int, n_paths: int, rng) -> np.ndarray:
    """Terminal returns by resampling historical daily returns with replacement."""
    h = np.asarray(list(hist_returns), dtype=float)
    if h.size == 0:
        return np.zeros(n_paths)
    sampled = rng.choice(h, size=(n_paths, days), replace=True)
    return np.prod(1.0 + sampled, axis=1) - 1.0


@dataclass
class MCResult:
    spot: float | None
    days: int
    n_paths: int
    method: str
    drift_annual: float
    vol_annual: float
    expected_return: float
    median_return: float
    prob_up: float
    prob_gain: float           # P(return >= +gain_threshold)
    prob_loss: float           # P(return <= -loss_threshold)
    gain_threshold: float
    loss_threshold: float
    var_95: float              # 5th-percentile return (loss at 95% confidence)
    pctiles: dict = field(default_factory=dict)   # p5/p25/p50/p75/p95


def summarize(terminal_returns, spot, days, n_paths, method, drift, vol,
              gain: float = 0.10, loss: float = 0.10) -> MCResult:
    t = np.asarray(terminal_returns, dtype=float)
    q = np.percentile(t, [5, 25, 50, 75, 95])
    return MCResult(
        spot=spot, days=days, n_paths=n_paths, method=method,
        drift_annual=drift, vol_annual=vol,
        expected_return=float(t.mean()), median_return=float(np.median(t)),
        prob_up=float(np.mean(t > 0)),
        prob_gain=float(np.mean(t >= gain)),
        prob_loss=float(np.mean(t <= -loss)),
        gain_threshold=gain, loss_threshold=loss,
        var_95=float(q[0]),
        pctiles={"p5": float(q[0]), "p25": float(q[1]), "p50": float(q[2]),
                 "p75": float(q[3]), "p95": float(q[4])},
    )


def montecarlo(closes, days: int = 63, n_paths: int = 20000, method: str = "gbm",
               gain: float = 0.10, loss: float = 0.10, seed: int = 12345,
               drift_adj: float = 0.0) -> MCResult:
    """Fit params from ``closes`` and simulate ``days`` ahead. Reproducible."""
    rets = daily_returns(closes)
    drift, vol = estimate_params(rets)
    spot = closes[-1] if closes else None
    rng = np.random.default_rng(seed)
    if method == "bootstrap":
        term = _simulate_bootstrap(rets, days, n_paths, rng)
    else:
        term = _simulate_gbm(drift, vol, days, n_paths, rng, drift_adj)
    return summarize(term, spot, days, n_paths, method, drift, vol, gain, loss)
