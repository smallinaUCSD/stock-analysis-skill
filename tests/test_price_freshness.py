"""Board prices never fall back to days-old bars: Yahoo fills what the quote
feed missed, and the after-close refresh knows which session's bars to expect."""

from datetime import date, datetime

from stockskill.marketclock import ET, last_session
from stockskill.watchlist import build as B


def test_last_session():
    assert last_session(datetime(2026, 9, 29, 15, 0, tzinfo=ET)) == date(2026, 9, 28)   # Tue, still open
    assert last_session(datetime(2026, 9, 29, 16, 10, tzinfo=ET)) == date(2026, 9, 28)  # final bar not settled
    assert last_session(datetime(2026, 9, 29, 16, 30, tzinfo=ET)) == date(2026, 9, 29)
    assert last_session(datetime(2026, 9, 28, 9, 0, tzinfo=ET)) == date(2026, 9, 25)    # Monday morning -> Friday
    assert last_session(datetime(2026, 9, 27, 12, 0, tzinfo=ET)) == date(2026, 9, 25)   # Sunday


def test_regular_quotes(monkeypatch):
    from stockskill.data import yahoo_ext as Y
    monkeypatch.setattr(Y, "_v7", lambda t, chunk=100: [
        {"symbol": "aapl", "regularMarketPrice": 329.4, "regularMarketChangePercent": -3.05},
        {"symbol": "X", "regularMarketPrice": None}])
    assert Y.regular_quotes(["AAPL", "X"]) == {"AAPL": {"price": 329.4, "change_pct": -0.0305}}


def test_missed_quotes_filled_from_yahoo(monkeypatch):
    from stockskill.data import yahoo_ext as Y
    monkeypatch.setattr(B, "fill_missing_quotes", B._real_fill_missing_quotes)
    asked = []

    def fake(tks):
        asked.append(sorted(tks))
        return {t: {"price": 100.0, "change_pct": 0.01} for t in tks}
    monkeypatch.setattr(Y, "regular_quotes", fake)
    monkeypatch.setattr(B, "_QUOTES", {"AAPL": (1000.0, {"price": 329.4}), "MU": (10.0, {"price": 1.0})})
    assert B.fill_missing_quotes(["AAPL", "MU", "AMAT"], since=500.0) == 2
    assert asked == [["AMAT", "MU"]] and B._QUOTES["AMAT"][1]["price"] == 100.0
    assert B._QUOTES["AAPL"][1]["price"] == 329.4                      # a fresh quote is left alone
    assert B.fill_missing_quotes(["AAPL"], since=500.0) == 0 and len(asked) == 1
