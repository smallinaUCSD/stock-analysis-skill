from stockskill.technicals.series import (sma_series, ema_series, bollinger_series,
                                          rsi_series, macd_series)
from stockskill import technicals as ta


def _closes(n=120):
    return [100 + i * 0.4 + (i % 5 - 2) for i in range(n)]


def test_series_lengths_match_input():
    c = _closes()
    assert len(sma_series(c, 20)) == len(c)
    assert len(rsi_series(c)) == len(c)
    mid, up, lo = bollinger_series(c)
    assert len(mid) == len(up) == len(lo) == len(c)
    m, s, h = macd_series(c)
    assert len(m) == len(s) == len(h) == len(c)


def test_series_last_values_match_scalar_technicals():
    c = _closes()
    assert abs(rsi_series(c)[-1] - ta.rsi(c)) < 1e-6
    m = ta.macd(c)
    ml, sig, hist = macd_series(c)
    assert abs(ml[-1] - m.macd) < 1e-6 and abs(sig[-1] - m.signal) < 1e-6
    bb = ta.bollinger(c)
    mid, up, lo = bollinger_series(c)
    assert abs(up[-1] - bb.upper) < 1e-6 and abs(lo[-1] - bb.lower) < 1e-6


def test_series_leading_nans_are_none():
    c = _closes(30)
    assert sma_series(c, 20)[0] is None      # not enough data at the start
    assert rsi_series(c)[0] is None
