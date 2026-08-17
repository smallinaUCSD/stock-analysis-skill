"""Kelly + vol-targeted sizing: barrier win-prob, Kelly fraction, the plan."""

import math

import pytest

from stockskill.trade.setup import atr_trade_setup
from stockskill.trade.sizing import (
    win_prob_barrier, kelly_risk_fraction, vol_target_fraction, sizing_plan,
)


def test_barrier_symmetric_no_drift_is_half():
    # equal log-distances to target/stop, zero log-drift (mu = 0.5*sigma^2) -> 0.5
    entry, sigma = 100.0, 0.20
    a = 0.10
    target, stop = entry * math.exp(a), entry / math.exp(a)
    mu = 0.5 * sigma ** 2                             # -> nu = 0
    assert win_prob_barrier(entry, target, stop, mu, sigma) == pytest.approx(0.5, abs=1e-9)


def test_barrier_drift_moves_probability():
    entry, sigma = 100.0, 0.25
    target, stop = 110.0, 92.0
    up = win_prob_barrier(entry, target, stop, 0.40, sigma)     # strong up-drift
    down = win_prob_barrier(entry, target, stop, -0.40, sigma)  # strong down-drift
    assert up > 0.6 and down < 0.4 and up > down


def test_barrier_short_mirrors_long():
    # A SHORT that profits on a fall should behave like the mirrored long.
    p_short = win_prob_barrier(100.0, 90.0, 108.0, -0.30, 0.25, direction="SHORT")
    assert 0.0 <= p_short <= 1.0 and p_short > 0.5   # down-drift favors the short


def test_kelly_fraction():
    assert kelly_risk_fraction(0.5, 2.0) == pytest.approx(0.25)   # 0.5 - 0.5/2
    # at the breakeven win rate 1/(1+R), Kelly ~ 0
    assert kelly_risk_fraction(1 / 3, 2.0) == pytest.approx(0.0, abs=1e-9)
    assert kelly_risk_fraction(0.25, 2.0) < 0                     # below breakeven -> no edge
    assert kelly_risk_fraction(None, 2.0) == 0.0


def test_vol_target_fraction():
    assert vol_target_fraction(0.30, target_vol=0.15, max_alloc=1.0) == pytest.approx(0.5)
    assert vol_target_fraction(0.05, target_vol=0.15, max_alloc=0.25) == 0.25  # capped
    assert vol_target_fraction(0.0) is None


def test_sizing_plan_positive_and_negative_edge():
    setup = atr_trade_setup(100.0, 3.0, "LONG")      # 2:1 R:R, stop -6%, target +12%
    # strong up-drift -> positive edge -> Kelly sizes a real position
    good = sizing_plan(100_000, setup, mu_annual=0.35, sigma_annual=0.30)
    assert good.tradable and good.kelly_dollars and good.kelly_dollars > 0
    assert good.fixed_dollars and good.voltarget_dollars
    # strong down-drift -> negative edge on a long -> Kelly says don't
    bad = sizing_plan(100_000, setup, mu_annual=-0.50, sigma_annual=0.30)
    assert not bad.tradable and bad.kelly_dollars is None
