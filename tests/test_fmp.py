"""FMP adapter: JSON normalization and FMP-first routing with yfinance fallback.

No network — ``fmp._get`` is monkeypatched to return canned FMP payloads.
"""

from datetime import date

import pytest

from stockskill.data import fmp


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")


def _route(monkeypatch, responses: dict):
    """Route fmp._get(path,...) to a {path_substring: payload} table."""
    def fake_get(path, **params):
        for frag, payload in responses.items():
            if frag in path:
                return payload
        return None
    monkeypatch.setattr(fmp, "_get", fake_get)


def test_has_fmp_reflects_env(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    assert fmp.has_fmp() is False
    monkeypatch.setenv("FMP_API_KEY", "x")
    assert fmp.has_fmp() is True


def test_ohlcv_reverses_and_uses_adjclose(key, monkeypatch):
    _route(monkeypatch, {"historical-price-full": {"historical": [
        {"date": "2024-01-03", "open": 3, "high": 4, "low": 2, "close": 3.5,
         "adjClose": 3.4, "volume": 300},
        {"date": "2024-01-02", "open": 2, "high": 3, "low": 1, "close": 2.5,
         "adjClose": 2.4, "volume": 200},
    ]}})
    r = fmp.ohlcv("AAPL", "1y")
    assert r["dates"] == [date(2024, 1, 2), date(2024, 1, 3)]   # oldest -> newest
    assert r["close"] == [2.4, 3.4]                             # adjClose preferred
    assert r["volume"] == [200, 300]


def test_ohlcv_empty_returns_none(key, monkeypatch):
    _route(monkeypatch, {"historical-price-full": {"historical": []}})
    assert fmp.ohlcv("AAPL", "1y") is None


def test_snapshot_maps_fields(key, monkeypatch):
    _route(monkeypatch, {
        "/profile/": [{"companyName": "Apple Inc.", "sector": "Technology",
                       "beta": 1.2, "currency": "USD", "lastDiv": 0.96,
                       "mktCap": 3e12, "isEtf": False, "volAvg": 5e7}],
        "/quote/": [{"price": 190.0, "sharesOutstanding": 1.5e10, "eps": 6.1,
                     "marketCap": 2.85e12, "yearHigh": 199.0, "yearLow": 164.0,
                     "avgVolume": 6e7, "earningsAnnouncement": "2099-02-01T21:00:00.000+0000"}],
        "/cash-flow-statement/": [{"freeCashFlow": 9.9e10}],
        "/income-statement/": [{"revenue": 3.8e11, "ebitda": 1.2e11, "eps": 6.0}],
        "/balance-sheet-statement/": [{"totalDebt": 1.0e11,
                                       "cashAndShortTermInvestments": 6e10}],
        "/financial-growth/": [{"revenueGrowth": 0.08, "epsgrowth": 0.11}],
        "/price-target-consensus/": [{"targetConsensus": 210.0}],
    })
    s = fmp.snapshot("AAPL")
    assert s.name == "Apple Inc." and s.sector == "Technology"
    assert s.source == "fmp" and s.ticker == "AAPL"
    assert s.price == 190.0 and s.fcf == 9.9e10 and s.revenue == 3.8e11
    assert s.net_debt == pytest.approx(4e10)          # 1.0e11 - 6e10
    assert s.dividend_annual == 0.96 and s.beta == 1.2
    assert s.target_mean == 210.0
    assert s.next_earnings == "2099-02-01"            # future earnings kept


def test_snapshot_none_when_no_profile_or_quote(key, monkeypatch):
    _route(monkeypatch, {})           # everything returns None
    assert fmp.snapshot("ZZZZ") is None


def test_search_normalizes(key, monkeypatch):
    _route(monkeypatch, {"/search": [
        {"symbol": "AAPL", "name": "Apple Inc.", "exchangeShortName": "NASDAQ",
         "stockExchange": "NASDAQ Global Select"},
        {"symbol": None},
    ]})
    r = fmp.search("apple")
    assert r == [{"symbol": "AAPL", "name": "Apple Inc.",
                  "type": "NASDAQ", "exchange": "NASDAQ Global Select"}]


def test_etf_holdings_scales_and_sorts(key, monkeypatch):
    _route(monkeypatch, {"/etf-holder/": [
        {"asset": "MSFT", "name": "Microsoft", "weightPercentage": "5.0"},
        {"asset": "AAPL", "name": "Apple", "weightPercentage": "7.5"},
        {"asset": "X", "name": "bad", "weightPercentage": None},
    ]})
    r = fmp.etf_holdings("QQQ", limit=5)
    assert [h["underlying"] for h in r["holdings"]] == ["AAPL", "MSFT"]   # sorted desc
    assert r["holdings"][0]["weight"] == pytest.approx(0.075)            # percent -> fraction


def test_prices_ohlcv_prefers_fmp(key, monkeypatch):
    from stockskill.data import prices
    monkeypatch.setattr(fmp, "ohlcv", lambda t, p="1y": {
        "dates": [date(2024, 1, 2)], "open": [1], "high": [1], "low": [1],
        "close": [1.23], "volume": [10]})
    assert prices.ohlcv("AAPL", "1y")["close"] == [1.23]


def test_prices_ohlcv_falls_back_when_fmp_empty(key, monkeypatch):
    from stockskill.data import prices
    monkeypatch.setattr(fmp, "ohlcv", lambda t, p="1y": None)
    called = {}

    class FakeTk:
        def __init__(self, t):
            called["t"] = t

        def history(self, period, auto_adjust):
            import pandas as pd
            return pd.DataFrame()

    monkeypatch.setattr("yfinance.Ticker", FakeTk)
    r = prices.ohlcv("AAPL", "1y")
    assert r["close"] == [] and called["t"] == "AAPL"      # fell through to yfinance


def test_search_symbols_uses_fmp_when_keyed(key, monkeypatch):
    from stockskill.data import search
    monkeypatch.setattr(fmp, "search", lambda q, limit=12: [
        {"symbol": "ORCL", "name": "Oracle", "type": "NASDAQ", "exchange": "NASDAQ"}])
    r = search.search_symbols("oracle")
    assert r[0]["symbol"] == "ORCL"
