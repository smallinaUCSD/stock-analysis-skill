"""Monte Carlo DCF: matches the point DCF at zero spread; sane distribution/probs."""

import pytest

from stockskill.valuation.dcf import DCFInputs, two_stage_dcf
from stockskill.valuation.mc_dcf import MCDCFSpec, monte_carlo_dcf


def _base():
    return DCFInputs(fcf0=1000.0, shares=100.0, net_debt=0.0, discount_rate=0.09,
                     stage1_growth=0.10, stage1_years=10, terminal_growth=0.025)


def test_zero_spread_reproduces_point_dcf():
    base = _base()
    point = two_stage_dcf(base).fair_value_per_share
    spec = MCDCFSpec(base=base, growth_sd=0, discount_sd=0, terminal_sd=0, fcf_cv=0)
    res = monte_carlo_dcf(spec, price=point, n_paths=200)
    assert res.mean == pytest.approx(point, abs=1e-6)
    assert res.median == pytest.approx(point, abs=1e-6)
    assert res.std < 1e-6
    assert res.pctiles["p50"] == pytest.approx(point, abs=1e-6)


def test_distribution_has_spread_and_ordered_pctiles():
    res = monte_carlo_dcf(MCDCFSpec(base=_base()), price=None, n_paths=3000)
    p = res.pctiles
    assert p["p5"] < p["p25"] < p["p50"] < p["p75"] < p["p95"]
    assert res.std > 0
    assert res.prob_undervalued is None            # no price given


def test_prob_undervalued_tracks_price():
    base = _base()
    point = two_stage_dcf(base).fair_value_per_share
    spec = MCDCFSpec(base=base)
    cheap = monte_carlo_dcf(spec, price=point * 0.5, n_paths=4000)
    rich = monte_carlo_dcf(spec, price=point * 2.0, n_paths=4000)
    assert cheap.prob_undervalued > 0.8            # price well below fair -> likely undervalued
    assert rich.prob_undervalued < 0.2             # price well above fair -> likely overvalued
    assert cheap.prob_upside_25 > rich.prob_upside_25


def test_deterministic_given_seed():
    spec = MCDCFSpec(base=_base())
    a = monte_carlo_dcf(spec, price=100.0, n_paths=1000, seed=7)
    b = monte_carlo_dcf(spec, price=100.0, n_paths=1000, seed=7)
    assert a.mean == b.mean and a.pctiles == b.pctiles
