import pytest

from stockskill.portfolio.lookthrough import Holding, expand
from stockskill.portfolio.risk import (
    herfindahl, effective_number_of_bets, top_n_concentration, group_exposure,
)
from stockskill.portfolio.decay import path_leveraged_return, monte_carlo_decay
from stockskill.leverage import registry


def test_lookthrough_single_and_basket():
    # $10k AAPU (2x AAPL) -> $20k AAPL notional.
    # $10k FNGU (3x, 10 equal names) -> $30k spread -> $3k each incl AAPL.
    holdings = [Holding("AAPU", 10_000), Holding("FNGU", 10_000)]
    lt = expand(holdings)
    assert lt.total_equity == pytest.approx(20_000)
    assert lt.total_notional == pytest.approx(50_000)      # 20k + 30k
    assert lt.effective_leverage == pytest.approx(2.5)
    assert lt.notional_by_underlying["AAPL"] == pytest.approx(23_000)  # 20k + 3k


def test_lookthrough_plain_holding_is_1x():
    lt = expand([Holding("COST", 5_000)])
    assert lt.effective_leverage == pytest.approx(1.0)
    assert lt.notional_by_underlying["COST"] == pytest.approx(5_000)


def test_registry_basket_weights_normalize():
    fngu = registry.get("FNGU")
    assert fngu is not None
    w = fngu.normalized_constituents()
    assert sum(w.values()) == pytest.approx(1.0)


def test_herfindahl_and_bets():
    assert herfindahl({"a": 1, "b": 1}) == pytest.approx(0.5)
    assert effective_number_of_bets({"a": 1, "b": 1}) == pytest.approx(2.0)
    assert herfindahl({"a": 9, "b": 1}) == pytest.approx(0.82)
    assert top_n_concentration({"a": 9, "b": 1, "c": 0}, 1) == pytest.approx(0.9)


def test_group_exposure():
    mapping = {"AAPL": "tech", "MSFT": "tech", "COIN": "crypto"}
    groups = group_exposure({"AAPL": 30, "MSFT": 30, "COIN": 40}, mapping)
    top = groups[0]
    assert top.group == "tech" and top.dollars == pytest.approx(60)
    assert top.share == pytest.approx(0.6)


def test_decay_oscillating_series_bleeds():
    # up then down: underlying ~flat, 3x loses money -> positive decay drag.
    res = path_leveraged_return([0.10, -0.10], multiplier=3.0)
    assert res.decay_drag > 0
    assert res.leveraged_actual < res.naive_expectation


def test_decay_smooth_trend_helps_leverage():
    # two equal up days: 3x compounding beats 3x simple -> negative drag.
    res = path_leveraged_return([0.10, 0.10], multiplier=3.0)
    assert res.decay_drag < 0


def test_monte_carlo_reproducible_and_decays():
    a = monte_carlo_decay(0.0, 0.50, 3.0, days=252, n_paths=5000, seed=7)
    b = monte_carlo_decay(0.0, 0.50, 3.0, days=252, n_paths=5000, seed=7)
    assert a.median_leveraged == b.median_leveraged        # deterministic
    assert a.median_leveraged < a.median_naive             # volatility decay
    assert 0.0 <= a.prob_leveraged_beats_naive <= 1.0
