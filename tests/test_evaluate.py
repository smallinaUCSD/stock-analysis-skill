import pytest

from stockskill.trade import evaluate_trade


def test_well_aligned_buy():
    ev = evaluate_trade("X", "buy", 100.0, valuation_mos=0.20, tech_signal="BUY",
                        trend_score=3.0, rsi=30, consensus_reco="Buy",
                        stop=95.0, target=110.0)
    assert ev.n_against == 0 and ev.n_support >= 5
    assert "well aligned" in ev.alignment
    assert ev.rr == pytest.approx(2.0)          # reward 10 / risk 5


def test_poorly_aligned_buy():
    ev = evaluate_trade("X", "buy", 100.0, valuation_mos=-0.30, tech_signal="SHORT",
                        trend_score=-3.0, rsi=75, consensus_reco="Sell")
    assert ev.n_against >= 3
    assert "poorly aligned" in ev.alignment


def test_short_action_alignment():
    # overvalued + short signal + downtrend + overbought + sell consensus all support a SHORT
    ev = evaluate_trade("X", "short", 100.0, valuation_mos=-0.20, tech_signal="SHORT",
                        trend_score=-3.0, rsi=72, consensus_reco="Sell")
    assert ev.n_support >= 4 and ev.n_against == 0


def test_rr_only():
    ev = evaluate_trade("X", "buy", 100.0, stop=90.0, target=120.0)
    assert ev.rr == pytest.approx(2.0)          # reward 20 / risk 10
    assert any(f.name == "Risk/reward" and f.stance == "support" for f in ev.factors)


def test_mixed():
    ev = evaluate_trade("X", "buy", 100.0, valuation_mos=0.20, tech_signal="SHORT")
    # one support (valuation), one against (signal) -> mixed
    assert "mixed" in ev.alignment
