"""Compare / OHLC routes over stubbed price data (no network)."""

import random
from datetime import date, timedelta

import pytest

from stockskill.data.fundamentals import FundamentalSnapshot
from stockskill.watchlist.pipeline import TickerData


def _late(td, keep):
    """The same series, listed later: only its last ``keep`` bars."""
    td.ohlcv = {k: v[-keep:] for k, v in td.ohlcv.items()}
    return td


def _td(ticker, mult=1.0, n=400, quote_type="EQUITY", seed=3):
    rnd = random.Random(seed)
    dates, c = [], [100.0]
    d = date(2025, 1, 6)
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    for _ in range(n - 1):
        c.append(c[-1] * (1 + mult * rnd.gauss(0.0005, 0.01)))
    o = {"dates": dates, "open": [x * 0.999 for x in c], "high": [x * 1.01 for x in c],
         "low": [x * 0.99 for x in c], "close": c, "volume": [1_000_000] * n}
    snap = FundamentalSnapshot(ticker=ticker, as_of="2026-09-23", name=f"{ticker} Inc",
                               quote_type=quote_type, market_cap=1e11, eps=2.0)
    return TickerData(ticker, o, snap, fetched_at=0.0)


@pytest.fixture
def client(tmp_path, monkeypatch):
    import stockskill.watchlist.pipeline as pipe
    from stockskill.server import create_app
    book = {"SPY": _td("SPY", 1.0, quote_type="ETF"), "QQQ": _td("QQQ", 1.2, quote_type="ETF"),
            "VOO": _td("VOO", 1.0, quote_type="ETF"), "FNGU": _late(_td("FNGU", 3.0), 200),
            "AAPL": _td("AAPL", 1.1)}

    def fake_fetch(t, period="1y", cache_dir=None, ttl=0):
        return book.get(t) or TickerData(t, {"close": []}, None, error="unknown")
    monkeypatch.setattr(pipe, "fetch_one", fake_fetch)
    monkeypatch.setattr("stockskill.data.funds.etf_holdings", lambda t, limit=10: {
        "name": t, "holdings": [{"underlying": "AAPL", "weight": 0.07},
                                {"underlying": "NVDA", "weight": 0.08}], "sectors": None})
    monkeypatch.setenv("STOCKSKILL_CACHE_DIR", str(tmp_path))
    return create_app(tickers_path=str(tmp_path / "none.csv"), public=True).test_client()


def test_compare_api_returns_aligned_series_and_profiles(client):
    d = client.get("/api/compare?t=VOO,fngu&period=max").get_json()
    assert d["ok"] and d["tickers"] == ["VOO", "FNGU"]
    assert d["limited_by"] == "FNGU"
    fngu = d["rows"][1]
    assert fngu["growth"][0] == 10000.0 and fngu["beta"] is not None
    prof = {p["ticker"]: p for p in d["profiles"]}
    assert prof["FNGU"]["leverage"] == 3.0 and prof["VOO"]["type"] == "ETF"


def test_compare_api_validates_input(client):
    assert client.get("/api/compare?t=VOO").status_code == 400
    assert client.get("/api/compare?t=A,B,C,D,E").status_code == 400
    r = client.get("/api/compare?t=VOO,ZZZZ")
    assert r.status_code == 404 and "ZZZZ" in r.get_json()["error"]


def test_compare_holdings_overlap(client):
    d = client.get("/api/compare/holdings?t=VOO,FNGU,AAPL").get_json()
    kinds = {f["ticker"]: f["kind"] for f in d["funds"]}
    assert kinds == {"VOO": "etf", "FNGU": "basket", "AAPL": "stock"}
    assert d["overlap"][0][2] == pytest.approx(0.07)     # AAPL's weight inside VOO


def test_ohlc_route_daily_and_weekly(client):
    daily = client.get("/api/ohlc/AAPL?period=6mo").get_json()
    assert daily["interval"] == "1d" and len(daily["open"]) == len(daily["close"]) == 127
    wk = client.get("/api/ohlc/AAPL?period=5y").get_json()
    assert wk["interval"] == "1wk" and len(wk["close"]) < 100
    assert client.get("/api/ohlc/ZZZZ").status_code == 404


def test_compare_page_renders_initial_tickers(client):
    html = client.get("/compare?t=VOO,FNGU,<script>").get_data(as_text=True)
    assert 'var INIT=["VOO", "FNGU"]' in html and "<script>alert" not in html
    assert "page-x" in html


def test_holdings_risk_route_is_private_and_sizes_hedges(tmp_path, monkeypatch):
    import stockskill.watchlist.pipeline as pipe
    from stockskill.server import create_app
    from stockskill.server.holdings_service import HoldingsService
    book = {"SPY": _td("SPY", 1.0, quote_type="ETF"), "SH": _td("SH", -1.0, quote_type="ETF"),
            "SPXU": _td("SPXU", -3.0, quote_type="ETF"), "FNGU": _td("FNGU", 3.0),
            "VOO": _td("VOO", 1.0, quote_type="ETF")}
    monkeypatch.setattr(pipe, "fetch_one", lambda t, **k: book.get(t) or TickerData(t, {"close": []}, None))
    monkeypatch.setattr(HoldingsService, "snapshot", lambda self: {
        "accounts": [{"positions": [{"ticker": "FNGU", "market_value": 30_000.0},
                                    {"ticker": "VOO", "market_value": 60_000.0}]}],
        "grand_cash": 10_000.0})
    monkeypatch.setenv("STOCKSKILL_CACHE_DIR", str(tmp_path))
    private = create_app(tickers_path=str(tmp_path / "t.csv"), public=False,
                         holdings_path=str(tmp_path / "h.csv")).test_client()
    d = private.get("/api/holdings/risk?bench=SPY&pct=50").get_json()
    p = d["portfolio"]
    assert d["ok"] and p["total"] == 100_000
    assert p["beta"] == pytest.approx(1.5, abs=0.01)   # (30k*3 + 60k*1 + 10k cash*0) / 100k
    by = {h["ticker"]: h for h in d["hedges"]}
    assert by["SPY"]["action"] == "Short" and by["SH"]["action"] == "Buy"
    assert by["SPXU"]["dollars"] == pytest.approx(by["SH"]["dollars"] / 3, rel=0.05)
    assert d["lookthrough"]["leverage"] > 1.0
    public = create_app(tickers_path=str(tmp_path / "t.csv"), public=True).test_client()
    assert public.get("/api/holdings/risk").status_code == 404


def test_pairs_signals_and_options_routes(tmp_path, monkeypatch):
    import pickle
    from stockskill.server import create_app
    import stockskill.watchlist.pipeline as pipe
    import stockskill.data.signals_extra as X
    cache = tmp_path / "cache"
    cache.mkdir()
    base = _td("SPY", 1.0, n=600, quote_type="ETF")
    book = {"SPY": base, "AAA": _td("AAA", 1.0, n=600, seed=3), "BBB": _td("BBB", 1.05, n=600, seed=3),
            "CCC": _td("CCC", 1.0, n=600, seed=11)}
    for t, td in book.items():
        (cache / f"{t}.pkl").write_bytes(pickle.dumps(td))
    tf = tmp_path / "t.csv"
    tf.write_text("[SEMIS]\nAAA, BBB, CCC\n\n[LEVERAGED]\nNVDL\n")
    monkeypatch.setenv("STOCKSKILL_CACHE_DIR", str(cache))
    monkeypatch.setattr(pipe, "fetch_one", lambda t, **k: book.get(t) or TickerData(t, {"close": []}, None))
    monkeypatch.setattr(X, "insider_trades", lambda t: [
        {"name": "CEO", "date": "2026-09-01", "code": "P", "shares": 100, "price": 10.0}])
    monkeypatch.setattr(X, "short_interest", lambda t: {"pct_float": 0.12, "days_to_cover": 3.0,
                                                         "shares_short": 1, "as_of": None,
                                                         "change_vs_prior": None})
    monkeypatch.setattr(X, "annual_statements", lambda t: None)
    monkeypatch.setattr("stockskill.data.options.expected_moves",
                        lambda t, spot, earn: {"available": True, "moves": [{"label": "Next week"}],
                                               "stale": False, "note": ""})
    c = create_app(tickers_path=str(tf), public=True).test_client()

    pr = c.get("/api/pairs").get_json()
    assert pr["ok"] and pr["backtest"]["periods"] >= 1
    assert all(p["group"] == "SEMIS" for p in pr["pairs"])

    sg = c.get("/api/signals/AAA").get_json()
    assert sg["insiders"]["buys"] == 1 and sg["short"]["pct_float"] == 0.12
    assert sg["quality"] is None

    op = c.get("/api/options/AAA").get_json()
    assert op["available"] and op["spot"] and op["moves"][0]["label"] == "Next week"

    cmp = c.get("/api/compare?t=AAA,BBB&period=1y").get_json()
    assert cmp["pair"]["a"] == "AAA" and len(cmp["pair"]["z"]) == len(cmp["pair"]["dates"])
