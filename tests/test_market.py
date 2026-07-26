import pytest

from stockskill.pulse import (
    cvr3_signal, market_quotes, detect_rotation, all_market_tickers, market_climate,
)


def test_market_climate_risk_on():
    # copper +10%, gold -5%, copper/gold rising -> risk-on
    cu = [100.0] * 21 + [110.0]
    au = [100.0] * 21 + [95.0]
    c = market_climate({"HG=F": cu, "GC=F": au})
    assert c.score >= 2 and "Risk-on" in c.label


def test_market_climate_risk_off():
    # copper -10%, gold +10% (fear bid), copper/gold falling -> risk-off
    cu = [100.0] * 21 + [90.0]
    au = [100.0] * 21 + [110.0]
    c = market_climate({"HG=F": cu, "GC=F": au})
    assert c.score <= -2 and "Risk-off" in c.label


def test_cvr3_signal():
    assert cvr3_signal([20.0] * 9 + [24.0]) == "BUY"      # VIX spike above MA
    assert cvr3_signal([20.0] * 9 + [17.0]) == "SELL"     # VIX below MA
    assert cvr3_signal([20.0] * 11) == "NEUTRAL"          # at MA
    assert cvr3_signal([20.0] * 5) == "NEUTRAL"           # not enough data


def test_market_quotes():
    pm = {"^GSPC": [100.0, 110.0], "^DJI": [200.0, 198.0], "GC=F": [3000.0, 3030.0],
          "BTC-USD": [90000.0, 99000.0]}
    q = {x.ticker: x for x in market_quotes(pm)}
    assert q["^GSPC"].change == pytest.approx(0.10)
    assert q["^GSPC"].group == "index"
    assert q["GC=F"].group == "commodity"
    assert q["BTC-USD"].change == pytest.approx(0.10)


def test_detect_rotation_picks_accelerating_leader():
    labels = {"SPY": "S&P", "QQQ": "Nasdaq"}
    pm = {
        "QQQ": [100, 100, 100, 100, 100, 102, 105],   # sharp recent up -> accelerating
        "SPY": [100, 101, 102, 103, 102, 101, 100],   # rolling over -> decelerating
    }
    leader = detect_rotation(pm, labels)
    assert leader is not None
    assert leader.ticker == "QQQ"
    assert leader.acceleration > 0


def test_detect_rotation_none_when_all_declining():
    pm = {"SPY": [100, 101, 102, 103, 102, 101, 100]}
    assert detect_rotation(pm, {"SPY": "S&P"}) is None


def test_all_market_tickers_deduped():
    tickers = all_market_tickers()
    assert len(tickers) == len(set(tickers))
    assert "^GSPC" in tickers and "BTC-USD" in tickers
