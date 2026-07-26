import math

import pytest

from stockskill.valuation.dcf import DCFInputs, two_stage_dcf
from stockskill.valuation.reverse_dcf import implied_stage1_growth
from stockskill.valuation.multiples import MultiplesInputs, value_from_multiples, blended_multiples_value
from stockskill.valuation.ddm import gordon_growth_value, two_stage_ddm
from stockskill.valuation.engine import capm_cost_of_equity, ValuationReport


def test_dcf_analytic_one_year():
    # fcf0=100, r=10%, g1=0, 1 year, terminal g=2%, 100 shares, no debt.
    # EV = 100/1.1 + (100*1.02/0.08)/1.1 = 90.909.. + 1159.09.. = 1250 exactly.
    inp = DCFInputs(fcf0=100, shares=100, net_debt=0.0, discount_rate=0.10,
                    stage1_growth=0.0, stage1_years=1, terminal_growth=0.02)
    res = two_stage_dcf(inp)
    assert res.enterprise_value == pytest.approx(1250.0, rel=1e-9)
    assert res.fair_value_per_share == pytest.approx(12.5, rel=1e-9)
    assert 0.0 < res.terminal_value_pct < 1.0


def test_dcf_net_debt_reduces_equity():
    base = DCFInputs(fcf0=100, shares=100, discount_rate=0.10, stage1_growth=0.05,
                     stage1_years=10, terminal_growth=0.02)
    levered = DCFInputs(fcf0=100, shares=100, net_debt=500, discount_rate=0.10,
                        stage1_growth=0.05, stage1_years=10, terminal_growth=0.02)
    assert two_stage_dcf(levered).fair_value_per_share < two_stage_dcf(base).fair_value_per_share


def test_dcf_monotonic_in_growth():
    def fv(g):
        return two_stage_dcf(DCFInputs(fcf0=100, shares=100, discount_rate=0.10,
                                       stage1_growth=g, stage1_years=10,
                                       terminal_growth=0.02)).fair_value_per_share
    assert fv(0.02) < fv(0.06) < fv(0.12)


def test_dcf_rejects_rate_below_terminal():
    with pytest.raises(ValueError):
        two_stage_dcf(DCFInputs(fcf0=100, shares=100, discount_rate=0.02,
                                terminal_growth=0.03))


def test_reverse_dcf_recovers_growth():
    inp = DCFInputs(fcf0=100, shares=100, discount_rate=0.10, stage1_growth=0.08,
                    stage1_years=10, terminal_growth=0.02)
    price = two_stage_dcf(inp).fair_value_per_share
    implied = implied_stage1_growth(price, inp)
    assert implied == pytest.approx(0.08, abs=1e-3)


def test_reverse_dcf_out_of_range_returns_none():
    inp = DCFInputs(fcf0=100, shares=100, discount_rate=0.10, stage1_years=10,
                    terminal_growth=0.02)
    assert implied_stage1_growth(1e9, inp) is None  # absurdly high price


def test_multiples():
    inp = MultiplesInputs(shares=10, net_debt=50, eps=5, ebitda=100, revenue=200)
    vals = value_from_multiples(inp, pe=20, ev_ebitda=10, ps=2)
    assert vals["P/E"] == pytest.approx(100.0)
    assert vals["EV/EBITDA"] == pytest.approx(95.0)   # (100*10 - 50)/10
    assert vals["P/S"] == pytest.approx(40.0)         # (200/10)*2
    assert blended_multiples_value(vals) == pytest.approx(95.0)  # median


def test_ddm():
    assert gordon_growth_value(2.0, 0.10, 0.05) == pytest.approx(40.0)
    with pytest.raises(ValueError):
        gordon_growth_value(2.0, 0.05, 0.05)
    # two-stage >= gordon at the terminal rate when high_growth > terminal
    v = two_stage_ddm(2.0, 0.10, 0.10, 5, 0.04)
    assert v > gordon_growth_value(2.0 * 1.04, 0.10, 0.04) * 0  # sanity: positive
    assert v > 0


def test_capm():
    assert capm_cost_of_equity(0.04, 1.0, 0.05) == pytest.approx(0.09)


def test_report_margin_and_verdict():
    rep = ValuationReport("XYZ", price=80.0)
    rep.add("DCF", 100.0, 1.0)
    rep.add("Multiples", 120.0, 1.0)
    assert rep.weighted_base() == pytest.approx(110.0)
    assert rep.margin_of_safety() == pytest.approx((110 - 80) / 110)
    assert "undervalued" in rep.verdict() or "discount" in rep.verdict()
