import pytest

from stockskill.pulse import metrics
from stockskill.pulse.pulse import sector_table, factor_table, breadth, regime


def test_trailing_return():
    assert metrics.trailing_return([100, 110], 1) == pytest.approx(0.10)
    assert metrics.trailing_return([100], 1) is None       # not enough data
    assert metrics.trailing_return([100, 0], 1) == pytest.approx(-1.0)


def test_moving_average_and_above():
    assert metrics.moving_average([1, 2, 3, 4], 2) == pytest.approx(3.5)
    assert metrics.above_ma([1, 2, 3, 10], 3) is True      # 10 > mean(2,3,10)=5
    assert metrics.above_ma([10, 9, 8, 1], 3) is False     # 1 < mean(9,8,1)=6
    assert metrics.above_ma([1, 2], 5) is None


def test_relative_strength():
    a = [100, 110]   # +10% over 1 day
    b = [100, 105]   # +5%
    assert metrics.relative_strength(a, b, 1) == pytest.approx(0.05)


def test_breadth_helpers():
    assert metrics.pct_positive([0.1, -0.2, None, 0.3]) == pytest.approx(2 / 3)
    series = [[1, 2, 3, 10], [10, 9, 8, 1]]                 # one above MA, one below
    assert metrics.pct_above_ma(series, 3) == pytest.approx(0.5)


def _flat_then(last, n=30, base=100.0):
    """Series flat at base for n-1 points, ending at `last` (controls returns)."""
    return [base] * (n - 1) + [last]


def test_sector_table_sorted_by_1m():
    pm = {
        "XLK": _flat_then(110),   # +10% 1m
        "XLP": _flat_then(95),    # -5% 1m
        "XLF": _flat_then(103),   # +3% 1m
    }
    rows = sector_table(pm, sort_window="1m")
    present = [r for r in rows if r.returns["1m"] is not None]
    assert present[0].ticker == "XLK"
    assert present[0].returns["1m"] == pytest.approx(0.10)
    assert present[-1].ticker == "XLP"


def test_regime_flags():
    pm = {
        "^VIX": [25.0],           # elevated (>20), not stressed (<30)
        "^TNX": [4.0],            # 10y
        "^IRX": [5.0],            # 3m higher -> inverted curve
    }
    r = regime(pm)
    assert r.values["yield_curve_10y_3m"] == pytest.approx(-1.0)
    assert r.flags["vix_elevated"] is True
    assert r.flags.get("vix_stressed") is False
    assert r.flags["yield_curve_inverted"] is True


def test_factor_table_shape():
    pm = {"VUG": _flat_then(110), "VTV": _flat_then(105)}
    rows = factor_table(pm)
    growth_value = next(r for r in rows if r.label == "Growth vs Value")
    assert growth_value.rs["1m"] == pytest.approx(0.10 - 0.05)
