"""Regime models: time-series momentum sign + inverse-vol scaling."""

from stockskill.regime.tsmom import tsmom


def _ramp(n, daily):
    return [100.0 * (1 + daily) ** i for i in range(n)]


def test_tsmom_uptrend_is_long():
    r = tsmom(_ramp(300, 0.001))            # steadily rising
    assert r.signal == 1 and r.trailing_return > 0
    assert "uptrend" in r.label
    assert r.position_scale > 0             # long, inverse-vol scaled


def test_tsmom_downtrend_is_short():
    r = tsmom(_ramp(300, -0.001))
    assert r.signal == -1 and r.trailing_return < 0
    assert r.position_scale < 0


def test_tsmom_too_short_is_none():
    assert tsmom(_ramp(100, 0.001), lookback=252) is None


def test_tsmom_inverse_vol_scaling():
    # a calmer series earns a larger position scale than a jumpy one at the same sign
    calm = _ramp(300, 0.001)
    jumpy = [c * (1 + (0.05 if i % 2 else -0.05)) for i, c in enumerate(calm)]
    rc, rj = tsmom(calm), tsmom(jumpy)
    assert rc.signal == 1 and rj.signal in (1, -1)
    assert abs(rc.position_scale) > abs(rj.position_scale)   # calm -> bigger scale


# --- Dai-Zhang-Zhu regime rule --------------------------------------------
from stockskill.regime.dzz import dzz_rule, estimate_regimes, filter_p_bull  # noqa: E402


def test_dzz_uptrend_reads_bull():
    r = dzz_rule(_ramp(400, 0.0015))          # persistent uptrend
    assert r is not None and r.state == "bull" and r.p_bull > 0.6
    assert r.params.mu_bull > r.params.mu_bear


def test_dzz_downtrend_reads_bear():
    r = dzz_rule(_ramp(400, -0.0015))
    assert r is not None and r.state == "bear" and r.p_bull < 0.4


def test_dzz_filter_bounded_and_responsive():
    import math
    # a series that trends up then reverses down: P(bull) should fall by the end
    closes = _ramp(250, 0.002) + [(_ramp(250, 0.002)[-1]) * (0.998 ** i) for i in range(150)]
    p = estimate_regimes(closes)
    series = filter_p_bull(closes, p)
    assert all(0.0 <= x <= 1.0 for x in series)
    assert series[-1] < series[250]           # regime probability dropped after the reversal


def test_dzz_too_short_is_none():
    assert dzz_rule(_ramp(30, 0.001)) is None
