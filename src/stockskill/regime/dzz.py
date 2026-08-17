"""Dai-Zhang-Zhu regime-switching trend rule.

*Trend Following Trading under a Regime-Switching Model* (Dai, Zhang, Zhu, SIAM
J. Financial Math 2010 / Math. of OR 2016). The drift switches between a **bull**
state (mu1 > 0) and a **bear** state (mu2 < 0) via a hidden 2-state Markov chain;
the bull probability given the price path follows the **Wonham filter**. The
optimal rule buys when that probability rises through an upper threshold and
sells when it falls through a lower one — enter a trend early, exit at the first
real evidence of reversal.

We estimate the states from history and run the filter to get the current
**P(bull)**, then read it against a threshold band. The regime is *inferred*, so
this is a model read, not a signal to obey; the thresholds here are a simplified
band (the optimal free-boundary thresholds depend on transaction cost). Pure and
tested.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_YEAR = 252


@dataclass(frozen=True)
class RegimeParams:
    mu_bull: float          # annualized drift, bull state
    mu_bear: float          # annualized drift, bear state
    sigma: float            # annualized volatility
    lam_b2r: float          # bull -> bear transition rate (per year)
    lam_r2b: float          # bear -> bull transition rate (per year)


@dataclass(frozen=True)
class DZZ:
    p_bull: float           # current P(bull) from the filter
    state: str              # "bull" | "bear" | "neutral"
    signal: str             # plain-English read
    params: RegimeParams


def _log_returns(closes: list[float]) -> list[float]:
    out = []
    for a, b in zip(closes[:-1], closes[1:]):
        if a and b and a > 0 and b > 0:
            out.append(math.log(b / a))
    return out


def estimate_regimes(closes: list[float], roll: int = 20) -> RegimeParams | None:
    """Estimate the 2-state params by labelling days bull/bear via a rolling mean."""
    rets = _log_returns(closes)
    if len(rets) < 60:
        return None
    sd = (sum((x - sum(rets) / len(rets)) ** 2 for x in rets) / (len(rets) - 1)) ** 0.5
    sigma = sd * math.sqrt(_YEAR)
    if sigma <= 0:
        return None

    # rough regime label: bull when the trailing rolling-mean return is positive
    labels = []
    for i in range(len(rets)):
        lo = max(0, i - roll + 1)
        labels.append(1 if sum(rets[lo:i + 1]) > 0 else 0)

    bull = [r for r, l in zip(rets, labels) if l == 1]
    bear = [r for r, l in zip(rets, labels) if l == 0]
    if not bull and not bear:
        return None
    # If one regime never showed (a steady climber/faller), synthesize the other
    # from the overall drift so the filter still has two states to sit between.
    overall = (sum(rets) / len(rets)) * _YEAR
    mu_bull = (sum(bull) / len(bull)) * _YEAR if bull else overall + 0.10
    mu_bear = (sum(bear) / len(bear)) * _YEAR if bear else overall - 0.10
    if mu_bull <= mu_bear:                    # degenerate: force a minimal separation
        mid = 0.5 * (mu_bull + mu_bear)
        mu_bull, mu_bear = mid + 0.05, mid - 0.05

    # transition rates from label switches: (# exits from a state) / (years in state)
    b2r = sum(1 for a, b in zip(labels[:-1], labels[1:]) if a == 1 and b == 0)
    r2b = sum(1 for a, b in zip(labels[:-1], labels[1:]) if a == 0 and b == 1)
    yr_bull = max(len(bull) / _YEAR, 1e-6)
    yr_bear = max(len(bear) / _YEAR, 1e-6)
    lam_b2r = max(b2r / yr_bull, 0.1)
    lam_r2b = max(r2b / yr_bear, 0.1)
    return RegimeParams(mu_bull, mu_bear, sigma, lam_b2r, lam_r2b)


def filter_p_bull(closes: list[float], p: RegimeParams) -> list[float]:
    """Wonham filter: P(bull) each day from the log-return path. Euler, dt=1/252."""
    rets = _log_returns(closes)
    dt = 1.0 / _YEAR
    var = p.sigma ** 2
    prob = p.lam_r2b / (p.lam_b2r + p.lam_r2b)     # stationary P(bull) as the prior
    out = []
    for dx in rets:
        drift = (p.lam_r2b * (1.0 - prob) - p.lam_b2r * prob) * dt
        expected = (p.mu_bull * prob + p.mu_bear * (1.0 - prob)) * dt
        innov = (p.mu_bull - p.mu_bear) / var * prob * (1.0 - prob) * (dx - expected)
        prob = min(1.0 - 1e-4, max(1e-4, prob + drift + innov))
        out.append(prob)
    return out


def dzz_rule(closes: list[float], p_hi: float = 0.6, p_lo: float = 0.4) -> DZZ | None:
    """Estimate regimes, filter P(bull), and read it against a threshold band."""
    params = estimate_regimes(closes)
    if not params:
        return None
    series = filter_p_bull(closes, params)
    if not series:
        return None
    p_bull = series[-1]
    if p_bull >= p_hi:
        state, signal = "bull", f"bull regime (P={p_bull:.0%}) — trend-following stays long"
    elif p_bull <= p_lo:
        state, signal = "bear", f"bear regime (P={p_bull:.0%}) — trend rule exits / avoids"
    else:
        state, signal = "neutral", f"unclear regime (P bull={p_bull:.0%}) — no trend-follow signal"
    return DZZ(p_bull=p_bull, state=state, signal=signal, params=params)
