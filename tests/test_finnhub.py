"""Finnhub adapter: quote normalization + the overlay preferring it over FMP."""

from types import SimpleNamespace

import pytest

from stockskill.data import finnhub


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")


def test_has_finnhub_reflects_env(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert finnhub.has_finnhub() is False
    monkeypatch.setenv("FINNHUB_API_KEY", "x")
    assert finnhub.has_finnhub() is True


def test_quote_normalizes(key, monkeypatch):
    monkeypatch.setattr(finnhub, "_get",
                        lambda path, **p: {"c": 261.74, "d": -1.9, "dp": -0.72, "pc": 263.64})
    assert finnhub.quote("AAPL") == {"price": 261.74, "change_pct": -0.0072}


def test_quote_zero_is_no_data(key, monkeypatch):
    monkeypatch.setattr(finnhub, "_get", lambda path, **p: {"c": 0, "dp": 0})
    assert finnhub.quote("ZZZZ") is None            # c=0 -> unknown symbol


def test_batch_quotes_collects(key, monkeypatch):
    prices = {"AAPL": {"c": 200.0, "dp": 1.0}, "MSFT": {"c": 410.0, "dp": -0.5},
              "ZZZZ": {"c": 0}}
    monkeypatch.setattr(finnhub, "_get", lambda path, **p: prices.get(p["symbol"]))
    q = finnhub.batch_quotes(["AAPL", "MSFT", "ZZZZ"])
    assert q["AAPL"] == {"price": 200.0, "change_pct": 0.01}
    assert q["MSFT"]["change_pct"] == -0.005
    assert "ZZZZ" not in q                          # zero price dropped


def test_rate_limiter_caps_calls():
    import time
    rl = finnhub._RateLimiter(max_calls=3, period=0.5)
    start = time.monotonic()
    for _ in range(4):                              # 4th must wait for the window
        rl.acquire()
    assert time.monotonic() - start >= 0.4


# --- overlay prefers Finnhub over FMP ----------------------------------------
from stockskill.watchlist.build import _overlay_live_prices  # noqa: E402


def _row(tk, price):
    return SimpleNamespace(ticker=tk, price=price, changes={"1d": 0.0},
                           ext_price=None, ext_change=None)


def test_overlay_prefers_finnhub(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    monkeypatch.setattr(finnhub, "batch_quotes",
                        lambda tks: {"AAPL": {"price": 250.0, "change_pct": 0.04}})
    # FMP should NOT be consulted when Finnhub is present
    from stockskill.data import fmp
    monkeypatch.setattr(fmp, "batch_quotes",
                        lambda tks, chunk=100: {"AAPL": {"price": 999.0, "change_pct": 0.9}})
    rows = [_row("AAPL", 190.0)]
    _overlay_live_prices(rows, SimpleNamespace(label="open"))
    assert rows[0].price == 250.0 and rows[0].changes["1d"] == 0.04
