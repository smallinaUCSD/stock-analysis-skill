import pytest

from stockskill.data.fundamentals import FundamentalSnapshot
from stockskill.valuation.service import Assumptions
from stockskill.valuation.scenarios import three_scenarios
from stockskill.analyze import analyze_ticker, _reco_label


def _snap(**kw):
    base = dict(ticker="TST", as_of="2026-01-01", price=100.0, shares=1000.0,
                market_cap=100000.0, fcf=6000.0, net_debt=0.0, eps=5.0,
                ebitda=9000.0, revenue=50000.0, beta=1.1)
    base.update(kw)
    return FundamentalSnapshot(**base)


def test_scenarios_ordered_bear_base_bull():
    scen = three_scenarios(_snap())
    fv = scen.fair_values()
    assert fv["bear"] < fv["base"] < fv["bull"]


def test_scenarios_respect_base_assumptions():
    a = Assumptions(stage1_growth=0.10)
    scen = three_scenarios(_snap(), a)
    # base uses 10% growth; bull uses 14%, bear 6% -> base between them
    assert scen.bear.report.weighted_base() < scen.base.report.weighted_base()


def test_reco_label():
    assert _reco_label(1.2, None) == "Strong Buy"
    assert _reco_label(2.0, None) == "Buy"
    assert _reco_label(3.0, None) == "Hold"
    assert _reco_label(4.6, None) == "Strong Sell"
    assert _reco_label(None, "strong_buy") == "Strong Buy"  # key wins when present
    assert _reco_label(None, None) == "n/a"


def test_analyze_ticker_payload_shape():
    d = analyze_ticker("TST", snapshot=_snap(), with_options=False)
    assert d["ticker"] == "TST"
    assert d["price"] == 100.0
    v = d["valuation"]
    assert v["bear"] < v["base"] < v["bull"]
    assert "signal" in v and isinstance(v["signal"], str)
    assert "decision is yours" in d["disclaimer"]
    # no buy/sell/hold *instruction* leaks into the signal itself
    assert not any(w in v["signal"].lower() for w in ["you should", "buy now", "sell now"])


def test_analyze_unprofitable_withholds_fair_value():
    # Negative FCF AND negative earnings -> nothing to value on -> withhold.
    d = analyze_ticker("BURN", snapshot=_snap(fcf=-5000.0, eps=-2.0,
                                              dividend_annual=None), with_options=False)
    v = d["valuation"]
    assert v["reliable"] is False
    assert v["base"] is None and v["bear"] is None and v["bull"] is None
    assert v["margin_of_safety"] is None
    assert v["signal"] == "no reliable fair-value basis"


def test_analyze_earnings_basis_when_fcf_negative():
    # Negative FCF but positive earnings -> earnings-based DCF, flagged as proxy.
    d = analyze_ticker("ORCLish", snapshot=_snap(fcf=-5000.0, eps=5.0),
                       with_options=False)
    v = d["valuation"]
    assert v["reliable"] is True
    assert v["base"] is not None and v["bear"] < v["base"] < v["bull"]
    assert "DCF (earnings)" in [m["method"] for m in v["methods"]]
    assert "net income" in v["note"].lower()


def test_analyze_low_yield_ddm_only_is_unreliable():
    # Low-yield dividend, no FCF, no earnings -> DDM is the only method -> unreliable.
    d = analyze_ticker("DIVX", snapshot=_snap(fcf=None, eps=None, dividend_annual=1.5),
                       with_options=False)
    val = d["valuation"]
    assert val["reliable"] is False
    assert [m["method"] for m in val["methods"]] == ["DDM"]  # DDM ran, but isn't enough


def test_analyze_ticker_consensus_reported():
    d = analyze_ticker("TST", snapshot=_snap(analyst_mean=2.0, analyst_count=30,
                                             target_mean=120.0), with_options=False)
    c = d["consensus"]
    assert c["reco"] == "Buy"
    assert c["count"] == 30
    assert c["target_vs_price"] == pytest.approx(0.20)  # 120/100 - 1
