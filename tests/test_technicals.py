import math
from datetime import date

import pytest

from stockskill.technicals import (
    rsi, stochastic, williams_r, roc, cci, mfi,
    sma, ema, golden_death_cross, macd, adx,
    bollinger, atr, historical_volatility,
    obv, volume_roc, volume_bias, volume_spike,
    ichimoku,
    pct_change, change_metrics, ytd_change, sparkline,
    pe_relative_to_avg, pe_volatility,
)


# --------------------------- momentum --------------------------- #
def test_rsi_extremes():
    assert rsi(list(range(1, 40))) == pytest.approx(100.0)      # all gains
    assert rsi(list(range(40, 1, -1))) == pytest.approx(0.0)    # all losses
    assert rsi([1, 2, 3]) is None                               # too short


def test_rsi_bounded():
    vals = rsi([10, 11, 10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16])
    assert 0.0 <= vals <= 100.0


def test_stochastic_and_williams_at_high():
    seq = list(range(1, 21))                                    # last close = window high
    k, d = stochastic(seq, seq, seq)
    assert k == pytest.approx(100.0)
    assert williams_r(seq, seq, seq) == pytest.approx(0.0)


def test_roc():
    assert roc([100] * 12 + [110], period=12) == pytest.approx(0.10)


def test_cci_and_mfi():
    seq = list(range(1, 30))
    assert isinstance(cci(seq, seq, seq), float)
    assert cci([1, 2], [1, 2], [1, 2]) is None
    # all up days -> MFI pinned to 100
    assert mfi(seq, seq, seq, [100] * 29) == pytest.approx(100.0)


# --------------------------- trend --------------------------- #
def test_sma_ema():
    assert sma([1, 2, 3, 4, 5], 5) == pytest.approx(3.0)
    assert sma([1, 2, 3, 4, 5], 3) == pytest.approx(4.0)        # last 3
    assert sma([1, 2], 5) is None
    assert isinstance(ema(list(range(1, 20)), 5), float)


def test_golden_death_cross():
    # small periods make the crossover hand-checkable
    assert golden_death_cross([10] * 7 + [20], fast=2, slow=4, lookback=3) == "golden"
    assert golden_death_cross([10] * 7 + [2], fast=2, slow=4, lookback=3) == "death"
    assert golden_death_cross([10] * 8, fast=2, slow=4, lookback=3) is None
    assert golden_death_cross([1, 2, 3], fast=2, slow=4) is None


def test_macd_invariant_and_trend():
    r = macd(list(range(1, 60)))
    assert r is not None
    assert r.histogram == pytest.approx(r.macd - r.signal)      # definitional
    assert r.macd > 0                                           # rising series
    assert r.state in ("bullish", "bull_cross")


def test_adx_range():
    a = adx(list(range(1, 60)), list(range(1, 60)), list(range(1, 60)))
    assert a is None or 0.0 <= a <= 100.0
    assert adx([1, 2, 3], [1, 2, 3], [1, 2, 3]) is None


# --------------------------- volatility --------------------------- #
def test_bollinger_middle_and_constant():
    bb = bollinger(list(range(1, 21)), period=20)
    assert bb.middle == pytest.approx(10.5)                     # mean(1..20)
    flat = bollinger([5.0] * 25, period=20)
    assert flat.width_pct == pytest.approx(0.0)
    assert flat.position_pct == pytest.approx(50.0)


def test_atr_constant_range():
    highs, lows, closes = [12.0] * 20, [10.0] * 20, [11.0] * 20
    assert atr(highs, lows, closes) == pytest.approx(2.0, abs=1e-6)
    assert atr([1, 2], [1, 2], [1, 2]) is None


def test_historical_volatility():
    assert historical_volatility([100.0] * 40) == pytest.approx(0.0)
    assert historical_volatility([1, 2, 3]) is None
    assert historical_volatility([100, 101, 99, 102, 98] * 8) > 0


# --------------------------- volume --------------------------- #
def test_obv():
    assert obv([10, 11, 12], [100, 200, 300]) == pytest.approx(500.0)  # first bar sign 0


def test_volume_roc_bias_spike():
    assert volume_roc([100, 150], period=1) == pytest.approx(0.5)
    assert volume_bias([10, 12, 11], [10, 100, 50], period=2) == pytest.approx(1 / 3)
    is_spike, ratio = volume_spike([100.0] * 20 + [200.0], period=20)
    assert is_spike and ratio == pytest.approx(2.0)
    assert volume_spike([100.0] * 5, period=20) == (False, None)


# --------------------------- ichimoku --------------------------- #
def test_ichimoku_bullish_uptrend():
    seq = [float(x) for x in range(1, 120)]                     # steady uptrend
    ich = ichimoku(seq, seq, seq)
    assert ich is not None
    assert ich.price_vs_cloud == "above"                       # price leads the cloud up
    assert ich.tk_state == "bull"
    assert ichimoku([1, 2, 3], [1, 2, 3], [1, 2, 3]) is None


# --------------------------- changes --------------------------- #
def test_changes():
    assert pct_change([100, 110], 1) == pytest.approx(0.10)
    assert pct_change([100], 1) is None
    m = change_metrics(list(range(1, 300)))
    assert set(m) == {"1d", "5d", "1m", "6m", "1y"}
    assert sparkline([1, 2, 3, 4, 5], 3) == [3, 4, 5]


def test_ytd_change():
    dates = [date(2025, 12, 31), date(2026, 1, 2), date(2026, 6, 1)]
    closes = [100.0, 200.0, 240.0]                             # first 2026 close = 200
    assert ytd_change(closes, dates) == pytest.approx(240 / 200 - 1)


# --------------------------- pe --------------------------- #
def test_pe_features():
    assert pe_relative_to_avg([10, 20, 30], current_pe=30) == pytest.approx(0.5)  # 30/20-1
    assert pe_volatility([10, 20, 30]) == pytest.approx(10.0)
    assert pe_volatility([15]) is None
