import pytest

from stockskill.portfolio.hedge import hedge_plan, portfolio_beta, put_contracts, reset_drag


def test_portfolio_beta_weights_by_dollars_and_counts_cash_as_zero():
    p = portfolio_beta([("FNGU", 30_000), ("VOO", 60_000), ("FNGU", 10_000), ("XYZ", 5_000)],
                       {"FNGU": 3.0, "VOO": 1.0}, cash=5_000)
    assert p["invested"] == 105_000 and p["total"] == 110_000
    assert p["exposure"] == pytest.approx(40_000 * 3 + 60_000)
    assert p["beta"] == pytest.approx(180_000 / 110_000)
    assert p["missing"] == ["XYZ"]                        # no beta: listed, not guessed
    assert [r["ticker"] for r in p["rows"]] == ["FNGU", "VOO"]
    assert sum(r["share"] for r in p["rows"]) == pytest.approx(1.0)


def test_hedge_plan_sizes_by_instrument_beta():
    plan = hedge_plan(180_000, 0.5, [
        {"ticker": "SPY", "label": "S&P 500", "beta": 1.0, "price": 600.0},
        {"ticker": "SH", "label": "-1x", "beta": -1.0, "price": 40.0},
        {"ticker": "SPXU", "label": "-3x", "beta": -3.0, "price": 10.0},
        {"ticker": "BAD", "beta": None}])
    by = {x["ticker"]: x for x in plan}
    assert by["SPY"]["action"] == "Short" and by["SPY"]["dollars"] == pytest.approx(90_000)
    assert by["SH"]["action"] == "Buy" and by["SH"]["dollars"] == pytest.approx(90_000)
    assert by["SPXU"]["dollars"] == pytest.approx(30_000) and by["SPXU"]["shares"] == pytest.approx(3000)
    assert "BAD" not in by
    assert hedge_plan(-5_000, 0.5, [{"ticker": "SH", "beta": -1.0}])[0]["dollars"] == 0.0


def test_put_contracts():
    assert put_contracts(120_000, 0.5, 600.0) == pytest.approx(2.0)   # 60k / (0.5*600*100)
    assert put_contracts(120_000, 0.5, 0) is None


def test_reset_drag_on_a_choppy_flat_index():
    idx = [100, 110, 100, 110, 100] * 5                  # ends flat
    fund = [100.0]
    for a, b in zip(idx[:-1], idx[1:]):
        fund.append(fund[-1] * (1 - 3 * (b / a - 1)))   # -3x daily reset
    d = reset_drag(fund, idx, -3.0)
    assert d["naive"] == pytest.approx(0.0)
    assert d["actual"] < 0 and d["drag"] < 0             # chop bleeds an inverse 3x fund
    assert reset_drag([1, 2], [1, 2], -1) is None
