import pytest

from stockskill.screener.criteria import (
    MetricSpec, percentile_ranks, score_universe,
)
from stockskill.screener.screen import extract_metrics, run_screen
from stockskill.data.fundamentals import FundamentalSnapshot


def test_percentile_ranks_basic():
    assert percentile_ranks([10, 20, 30]) == [0.0, 0.5, 1.0]


def test_percentile_ranks_ties():
    # sorted [10,10,20]: the tied 10s share avg rank 0.5 -> 0.25; 20 -> 1.0
    assert percentile_ranks([10, 10, 20]) == [0.25, 0.25, 1.0]


def test_percentile_ranks_handles_none():
    assert percentile_ranks([10, None, 30]) == [0.0, None, 1.0]


def test_score_universe_direction_and_ordering():
    rows = [
        {"ticker": "A", "a": 30, "b": 10},
        {"ticker": "B", "a": 20, "b": 20},
        {"ticker": "C", "a": 10, "b": 30},
    ]
    specs = [MetricSpec("a", 1.0, True), MetricSpec("b", 1.0, False)]  # b: lower better
    ranked = score_universe(rows, specs)
    assert [s.ticker for s in ranked] == ["A", "B", "C"]
    assert ranked[0].score == pytest.approx(1.0)
    assert ranked[-1].score == pytest.approx(0.0)


def test_score_universe_coverage_with_missing_metric():
    rows = [{"ticker": "A", "a": 1}, {"ticker": "B", "a": 2}]
    specs = [MetricSpec("a", 1.0, True), MetricSpec("b", 1.0, True)]  # 'b' absent
    ranked = score_universe(rows, specs)
    for s in ranked:
        assert s.coverage == pytest.approx(0.5)   # only half the weight was scorable
        assert s.components["b"] is None


def test_extract_metrics_computes_yields():
    snap = FundamentalSnapshot(
        ticker="X", as_of="2026-01-01", price=100.0, shares=10.0,
        market_cap=1000.0, fcf=50.0, net_debt=200.0, eps=5.0, ebitda=100.0,
        revenue=800.0, dividend_annual=2.0,
    )
    m = extract_metrics(snap)
    assert m["fcf_yield"] == pytest.approx(0.05)          # 50/1000
    assert m["earnings_yield"] == pytest.approx(0.05)     # 5/100
    assert m["ev_ebitda"] == pytest.approx(12.0)          # (1000+200)/100
    assert m["dividend_yield"] == pytest.approx(0.02)     # 2/100


def test_run_screen_ranks_dominant_name_first():
    # A dominates on cash yield, margins, cheap EV/EBITDA -> should top core lane.
    strong = FundamentalSnapshot("A", "2026-01-01", price=100, shares=10,
                                 market_cap=1000, fcf=120, net_debt=0, eps=10,
                                 ebitda=200, revenue=1000, profit_margin=0.30,
                                 roe=0.35, revenue_growth=0.20)
    weak = FundamentalSnapshot("B", "2026-01-01", price=100, shares=10,
                               market_cap=5000, fcf=20, net_debt=3000, eps=1,
                               ebitda=100, revenue=1000, profit_margin=0.03,
                               roe=0.04, revenue_growth=0.01)
    ranked = run_screen([strong, weak], lane="core")
    assert ranked[0].ticker == "A"
    assert ranked[0].score > ranked[1].score


def test_run_screen_rejects_bad_lane():
    with pytest.raises(ValueError):
        run_screen([], lane="nonsense")
