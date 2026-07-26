import pytest

from stockskill.trade import (
    atr_trade_setup, position_size, implied_move, suggest_options,
)


def test_atr_trade_setup_long():
    s = atr_trade_setup(100.0, 2.5, "LONG", atr_mult=2.0, rr=2.0)
    assert s.stop == pytest.approx(95.0)      # 100 - 2*2.5
    assert s.target == pytest.approx(110.0)   # 100 + 2*2.5*2
    assert s.risk_pct == pytest.approx(0.05)
    assert s.reward_pct == pytest.approx(0.10)
    assert s.rr_ratio == pytest.approx(2.0)


def test_atr_trade_setup_short_and_guards():
    s = atr_trade_setup(100.0, 2.5, "SHORT")
    assert s.stop == pytest.approx(105.0) and s.target == pytest.approx(90.0)
    assert atr_trade_setup(100.0, 0.0) is None
    assert atr_trade_setup(100.0, None) is None


def test_position_size_and_cap():
    # risk $10/share, 2% of 100k = $2000 -> 200 shares, $20k (20%) -> not capped
    p = position_size(100_000, 100.0, 90.0)
    assert p.shares == pytest.approx(200.0) and p.capped is False
    # risk $5/share -> 400 shares/$40k (40%) -> capped to 25% ($25k)
    c = position_size(100_000, 100.0, 95.0)
    assert c.capped is True and c.pct_of_account == pytest.approx(0.25)
    assert position_size(100_000, 100.0, 100.0) is None   # zero risk


def test_implied_move():
    assert implied_move(3.0, 3.0, 100.0) == pytest.approx(0.06)
    assert implied_move(3.0, None, 100.0) is None


def test_suggest_options_directional():
    assert suggest_options(trend_score=5.0, change_pct=3.0)[0].label == "Buy calls"
    assert suggest_options(rsi=75, change_pct=1.5)[0].direction == "bullish"
    assert suggest_options(golden_death="death")[0].label == "Buy puts"
    assert suggest_options(trend_score=-5.0)[0].direction == "bearish"
    assert suggest_options(rsi=25, change_pct=-2.0)[0].label == "Buy puts"
    assert suggest_options(trend_score=0.0, rsi=50, change_pct=0.0) == []


def test_suggest_options_earnings():
    straddle = suggest_options(imp_move=0.10, days_to_earnings=3)
    assert any(i.label == "Earnings straddle/strangle" for i in straddle)
    pre = suggest_options(imp_move=0.06, days_to_earnings=5)
    assert any(i.label == "Pre-earnings directional" for i in pre)
