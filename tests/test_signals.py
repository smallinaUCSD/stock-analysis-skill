import pytest

from stockskill.signals import (
    SignalConfig, IndicatorSnapshot, BUY, SELL, SHORT, HOLD,
    bb_signal, rsi_signal, macd_signal, ichimoku_signal,
    combined_signal, bb_ichimoku_signal, all_strategy_signals,
    trend, trend_arrow, signal_confidence,
)

CFG = SignalConfig()


def snap(**kw) -> IndicatorSnapshot:
    return IndicatorSnapshot(**kw)


# --------------------------- individual strategies --------------------------- #
def test_bb_signal():
    assert bb_signal(snap(bb_position=5), CFG) == BUY
    assert bb_signal(snap(bb_position=95), CFG) == SHORT
    assert bb_signal(snap(bb_position=87, bb_position_prev=90), CFG) == SELL   # reversing down
    assert bb_signal(snap(bb_position=87, bb_position_prev=80), CFG) == HOLD   # rising, no exit
    assert bb_signal(snap(bb_position=50), CFG) == HOLD
    assert bb_signal(snap(), CFG) == HOLD                                      # no data


def test_rsi_signal():
    assert rsi_signal(snap(rsi=25), CFG) == BUY
    assert rsi_signal(snap(rsi=75), CFG) == SHORT
    assert rsi_signal(snap(rsi=65, rsi_prev=72), CFG) == SELL                  # dropping from OB
    assert rsi_signal(snap(rsi=50), CFG) == HOLD


def test_macd_signal():
    assert macd_signal(snap(macd_state="bull_cross"), CFG) == BUY
    assert macd_signal(snap(macd_state="bear_cross"), CFG) == SHORT
    assert macd_signal(snap(macd_state="bullish"), CFG) == HOLD
    assert macd_signal(snap(), CFG) == HOLD


def test_ichimoku_signal():
    assert ichimoku_signal(snap(ich_price_vs_cloud="above", ich_tk="bull"), CFG) == BUY
    assert ichimoku_signal(snap(ich_price_vs_cloud="below", ich_tk="bear"), CFG) == SHORT
    assert ichimoku_signal(snap(ich_price_vs_cloud="in_cloud"), CFG) == HOLD
    assert ichimoku_signal(snap(ich_price_vs_cloud="above", ich_tk="bear"), CFG) == HOLD


# --------------------------- combined & bb+ichimoku --------------------------- #
def test_combined_weighted_vote():
    # BB BUY (1.0) + Ichimoku BUY (1.5) = 2.5 >= 2.0 threshold -> BUY
    s = snap(bb_position=5, ich_price_vs_cloud="above", ich_tk="bull")
    assert combined_signal(s, CFG) == BUY


def test_combined_conflict_holds():
    # BB BUY (1.0) vs Ichimoku SHORT (1.5): neither side clears threshold -> HOLD
    s = snap(bb_position=5, ich_price_vs_cloud="below", ich_tk="bear")
    assert combined_signal(s, CFG) == HOLD


def test_combined_sell_when_no_entry():
    # RSI SELL, nothing else -> SELL (no entry conflict)
    s = snap(rsi=65, rsi_prev=72)
    assert combined_signal(s, CFG) == SELL


def test_bb_ichimoku_modes():
    both_buy = snap(bb_position=5, ich_price_vs_cloud="above", ich_tk="bull")
    bb_only = snap(bb_position=5, ich_price_vs_cloud="in_cloud")
    conflict = snap(bb_position=5, ich_price_vs_cloud="below", ich_tk="bear")

    confirm = SignalConfig(bb_ichimoku_mode="CONFIRM")
    assert bb_ichimoku_signal(both_buy, confirm) == BUY
    assert bb_ichimoku_signal(bb_only, confirm) == HOLD      # needs agreement

    andc = SignalConfig(bb_ichimoku_mode="AND")
    assert bb_ichimoku_signal(both_buy, andc) == BUY
    assert bb_ichimoku_signal(conflict, andc) == HOLD

    orc = SignalConfig(bb_ichimoku_mode="OR")
    assert bb_ichimoku_signal(bb_only, orc) == BUY           # either can trigger
    assert bb_ichimoku_signal(conflict, orc) == HOLD         # BUY vs SHORT cancels


# --------------------------- trend & confidence --------------------------- #
def test_trend_strong_up_and_down():
    up = snap(macd_state="bullish", rsi=65, bb_position=85,
              ich_price_vs_cloud="above", ich_tk="bull", change_pct=3.0)
    t = trend(up, BUY, CFG)
    assert t.score >= 4.0 and t.arrow == "↑"

    down = snap(macd_state="bearish", rsi=35, bb_position=15,
                ich_price_vs_cloud="below", ich_tk="bear", change_pct=-3.0)
    assert trend(down, SHORT, CFG).arrow == "↓"


def test_trend_arrow_bands():
    assert trend_arrow(5.0)[0] == "↑"
    assert trend_arrow(2.0)[0] == "↗"
    assert trend_arrow(0.0)[0] == "→"
    assert trend_arrow(-2.0)[0] == "↘"
    assert trend_arrow(-5.0)[0] == "↓"


def test_confidence():
    strong = {"BB": BUY, "RSI": BUY, "MACD": BUY, "Ichimoku": BUY}
    c = signal_confidence(strong, BUY)
    assert c.level == "STRONG" and c.pct == pytest.approx(1.0)

    mixed = {"BB": BUY, "RSI": BUY, "MACD": HOLD, "Ichimoku": SHORT}
    assert signal_confidence(mixed, BUY).level == "MODERATE"   # 2/4

    weak = {"BB": BUY, "RSI": HOLD, "MACD": HOLD, "Ichimoku": HOLD}
    assert signal_confidence(weak, BUY).level == "WEAK"        # 1/4

    assert signal_confidence(strong, HOLD) is None             # HOLD isn't scored


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("RSI_OVERSOLD", "25")
    monkeypatch.setenv("TRADING_STRATEGY", "macd")
    cfg = SignalConfig.from_env()
    assert cfg.rsi_oversold == 25.0
    assert cfg.strategy == "macd"


def test_all_strategy_signals_keys():
    s = snap(bb_position=5, ich_price_vs_cloud="above", ich_tk="bull",
             rsi=25, macd_state="bull_cross")
    sigs = all_strategy_signals(s, CFG)
    assert set(sigs) == {"BB", "RSI", "MACD", "Ichimoku", "Combined", "BB+Ichimoku"}
