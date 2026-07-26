"""Leveraged-ETF volatility decay: quantify the cost of daily resetting.

A 3x fund delivers 3x the *daily* return, then resets. Over multiple days,
compounding of a volatile series means the realized multi-day return is
almost always LESS than 3x the underlying's multi-day return -- the gap is
"volatility decay" (aka beta slippage). In choppy-but-flat markets it bleeds
you; only in smooth strong trends does leverage compound in your favor.

Two tools:
* :func:`path_leveraged_return` -- exact replay over a real return series.
* :func:`monte_carlo_decay` -- distribution of outcomes given drift & vol.

Deterministic given inputs (Monte Carlo takes an explicit seed).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DecayResult:
    underlying_total_return: float   # buy-and-hold underlying, over the window
    naive_expectation: float         # multiplier * underlying_total_return
    leveraged_actual: float          # true daily-reset compounded return
    decay_drag: float                # naive_expectation - leveraged_actual


def path_leveraged_return(daily_returns, multiplier: float,
                          daily_fee: float = 0.0) -> DecayResult:
    """Replay a daily-reset leveraged fund over an explicit return series.

    ``daily_returns`` is a sequence of simple daily returns of the underlying
    (0.01 == +1%). Each day the fund returns ``multiplier * r - daily_fee``
    and compounds. ``daily_fee`` bundles expense ratio + financing cost per
    day (e.g. annual 1.2% -> ~0.012/252).
    """
    r = np.asarray(list(daily_returns), dtype=float)
    underlying_total = float(np.prod(1.0 + r) - 1.0)
    lev_daily = multiplier * r - daily_fee
    leveraged_total = float(np.prod(1.0 + lev_daily) - 1.0)
    naive = multiplier * underlying_total
    return DecayResult(
        underlying_total_return=underlying_total,
        naive_expectation=naive,
        leveraged_actual=leveraged_total,
        decay_drag=naive - leveraged_total,
    )


@dataclass
class MonteCarloDecay:
    days: int
    multiplier: float
    median_underlying: float
    median_leveraged: float
    median_naive: float
    prob_leveraged_beats_naive: float   # P(leveraged >= multiplier * underlying)
    prob_leveraged_loss: float          # P(leveraged total return < 0)
    pctiles_leveraged: dict[str, float] # 5/25/50/75/95 percentile returns


def monte_carlo_decay(
    annual_drift: float,
    annual_vol: float,
    multiplier: float,
    days: int = 252,
    n_paths: int = 20000,
    daily_fee: float = 0.0,
    seed: int = 12345,
) -> MonteCarloDecay:
    """Simulate underlying daily returns and compare leveraged vs naive.

    Underlying daily returns ~ Normal(mu_d, sigma_d) with
    mu_d = annual_drift/252, sigma_d = annual_vol/sqrt(252). For each path we
    compound the true daily-reset leveraged return and compare to the naive
    ``multiplier * underlying_total``. Reproducible via ``seed``.
    """
    rng = np.random.default_rng(seed)
    mu_d = annual_drift / 252.0
    sigma_d = annual_vol / np.sqrt(252.0)
    shocks = rng.normal(mu_d, sigma_d, size=(n_paths, days))

    underlying_total = np.prod(1.0 + shocks, axis=1) - 1.0
    lev_daily = multiplier * shocks - daily_fee
    leveraged_total = np.prod(1.0 + lev_daily, axis=1) - 1.0
    naive = multiplier * underlying_total

    q = np.percentile(leveraged_total, [5, 25, 50, 75, 95])
    return MonteCarloDecay(
        days=days,
        multiplier=multiplier,
        median_underlying=float(np.median(underlying_total)),
        median_leveraged=float(np.median(leveraged_total)),
        median_naive=float(np.median(naive)),
        prob_leveraged_beats_naive=float(np.mean(leveraged_total >= naive)),
        prob_leveraged_loss=float(np.mean(leveraged_total < 0.0)),
        pctiles_leveraged={
            "p5": float(q[0]), "p25": float(q[1]), "p50": float(q[2]),
            "p75": float(q[3]), "p95": float(q[4]),
        },
    )
