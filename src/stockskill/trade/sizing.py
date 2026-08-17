"""Position sizing, three ways: fixed-risk, fractional Kelly, vol-targeted.

- **Fixed 2%-risk** — the existing rule (risk a fixed % on the stop).
- **Fractional Kelly** — size by the trade's *edge*. Kelly's `f* = W − (1−W)/R`
  is the growth-optimal fraction of capital to risk; we use **half-Kelly** and
  cap it, and if the edge is ≤ 0, Kelly says *don't take the trade*.
- **Volatility-targeted** — Moreira-Muir: size so the position runs at a target
  volatility (take less when the name is jumpy).

The Kelly edge needs a win probability, which we estimate *honestly* as the
first-passage probability that price reaches the **target before the stop** under
a GBM with drift/vol from history (a barrier-hit probability) — not a guess. All
pure, tested functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .setup import position_size


def win_prob_barrier(entry: float, target: float, stop: float,
                     mu_annual: float, sigma_annual: float,
                     direction: str = "LONG") -> float | None:
    """P(target hit before stop) for GBM log-price with drift μ, vol σ.

    Depends only on *which* barrier is hit first, so it's horizon-independent.
    LONG: target > entry > stop; SHORT mirrors (a win is price falling to target).
    """
    if not (entry > 0 and target > 0 and stop > 0) or not sigma_annual or sigma_annual <= 0:
        return None
    if direction.upper() == "SHORT":
        a = math.log(entry / target)                 # favorable distance (down)
        b = math.log(stop / entry)                   # adverse distance (up)
        nu = -(mu_annual - 0.5 * sigma_annual ** 2)
    else:
        a = math.log(target / entry)                 # favorable distance (up)
        b = math.log(entry / stop)                   # adverse distance (down)
        nu = mu_annual - 0.5 * sigma_annual ** 2
    if a <= 0 or b <= 0:
        return None
    k = 2.0 * nu / (sigma_annual ** 2)
    if abs(k) < 1e-9:                                 # driftless -> b/(a+b)
        return b / (a + b)
    try:
        p = (1.0 - math.exp(k * b)) / (math.exp(-k * a) - math.exp(k * b))
    except OverflowError:
        return 1.0 if nu > 0 else 0.0
    return min(1.0, max(0.0, p))


def kelly_risk_fraction(win_prob: float | None, rr: float | None) -> float:
    """Full-Kelly fraction of capital to RISK: f* = W − (1−W)/R. ≤ 0 = no edge."""
    if win_prob is None or rr is None or rr <= 0:
        return 0.0
    return win_prob - (1.0 - win_prob) / rr


def vol_target_fraction(sigma_annual: float | None, target_vol: float = 0.15,
                        max_alloc: float = 0.25) -> float | None:
    """Allocation fraction so a position runs at ~``target_vol`` (Moreira-Muir),
    capped at ``max_alloc`` for single-name concentration."""
    if not sigma_annual or sigma_annual <= 0:
        return None
    return min(target_vol / sigma_annual, max_alloc)


@dataclass
class SizingPlan:
    win_prob: float | None
    rr: float
    kelly_fraction: float            # full-Kelly risk fraction (can be ≤ 0)
    tradable: bool                   # positive edge (kelly_fraction > 0)
    fixed_dollars: float | None
    fixed_pct: float | None
    kelly_dollars: float | None      # half-Kelly, risk-based
    kelly_pct: float | None
    voltarget_dollars: float | None
    voltarget_pct: float | None


def sizing_plan(account: float, setup, mu_annual: float, sigma_annual: float,
                kelly_mult: float = 0.5, target_vol: float = 0.15,
                risk_per_trade: float = 0.02, max_pct: float = 0.25) -> SizingPlan:
    """Fixed / half-Kelly / vol-targeted sizes for a :class:`TradeSetup`."""
    p = win_prob_barrier(setup.entry, setup.target, setup.stop,
                         mu_annual, sigma_annual, setup.direction)
    rr = setup.rr_ratio
    f = kelly_risk_fraction(p, rr)

    fixed = position_size(account, setup.entry, setup.stop, risk_per_trade, max_pct)
    kelly_risk = max(0.0, f) * kelly_mult
    kelly = position_size(account, setup.entry, setup.stop, kelly_risk, max_pct) if kelly_risk > 0 else None
    vf = vol_target_fraction(sigma_annual, target_vol, max_pct)

    return SizingPlan(
        win_prob=p, rr=rr, kelly_fraction=f, tradable=f > 0,
        fixed_dollars=fixed.dollars if fixed else None,
        fixed_pct=fixed.pct_of_account if fixed else None,
        kelly_dollars=kelly.dollars if kelly else None,
        kelly_pct=kelly.pct_of_account if kelly else None,
        voltarget_dollars=(account * vf) if vf else None,
        voltarget_pct=vf,
    )
