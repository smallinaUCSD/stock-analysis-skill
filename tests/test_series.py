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


def _hlcv(n=200):
    import random
    random.seed(3)
    c = [100.0]
    for _ in range(n):
        c.append(c[-1] * (1 + random.uniform(-0.02, 0.02)))
    c = c[1:]
    return [x * 1.01 for x in c], [x * 0.99 for x in c], c, [1e6] * len(c)


def _last(a):
    return next(x for x in reversed(a) if x is not None)


def test_atr_stoch_adx_obv_ichimoku_match_scalars():
    from stockskill.technicals import series as S
    h, l, c, v = _hlcv()
    assert abs(_last(S.atr_series(h, l, c)) - ta.atr(h, l, c)) < 1e-6
    k, d = S.stochastic_series(h, l, c)
    sk, sd = ta.stochastic(h, l, c)
    assert abs(_last(k) - sk) < 1e-6 and abs(_last(d) - sd) < 1e-6
    adx, pdi, mdi = S.adx_series(h, l, c)
    assert abs(_last(adx) - ta.adx(h, l, c)) < 1e-6
    assert abs(_last(S.obv_series(c, v)) - ta.obv(c, v)) < 1e-6
    ich = S.ichimoku_series(h, l, c)
    sc = ta.ichimoku(h, l, c)
    assert abs(_last(ich["tenkan"]) - sc.tenkan) < 1e-6
    assert abs(_last(ich["kijun"]) - sc.kijun) < 1e-6
