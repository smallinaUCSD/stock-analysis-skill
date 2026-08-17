import pytest

from stockskill.watchlist import (parse_tickers, parse_tickers_text,
                                  detect_categories, build_row)
from stockskill.watchlist.pipeline import TickerData
from stockskill.data.fundamentals import FundamentalSnapshot
from stockskill.signals import SignalConfig


def test_parse_tickers_text_matches_file(tmp_path):
    text = "[M7]\nAAPL, MSFT\n\n[ADDED]\nNVDA, AAPL\n"
    p = parse_tickers_text(text)
    assert p["sections"]["M7"] == ["AAPL", "MSFT"]
    assert p["sections"]["ADDED"] == ["NVDA", "AAPL"]
    # dedup across sections, first-seen order
    assert p["all"] == ["AAPL", "MSFT", "NVDA"]
    # parse_tickers(file) is just parse_tickers_text(read())
    f = tmp_path / "t.csv"
    f.write_text(text)
    assert parse_tickers(str(f)) == p


def test_parse_tickers_sectioned(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("# comment\n[M7]\nAAPL, MSFT, GOOGL\n[MEME]\nGME\nAAPL\n[TICKERS]\nNVDA\n")
    p = parse_tickers(str(f))
    assert p["sections"]["M7"] == ["AAPL", "MSFT", "GOOGL"]
    assert p["sections"]["MEME"] == ["GME", "AAPL"]
    # deduped across sections, first-seen order
    assert p["all"] == ["AAPL", "MSFT", "GOOGL", "GME", "NVDA"]


def test_parse_tickers_simple(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("AAPL\nMSFT, GOOGL\nAAPL\n")
    p = parse_tickers(str(f))
    assert p["all"] == ["AAPL", "MSFT", "GOOGL"]


def test_detect_categories():
    assert "leveraged" in detect_categories("FNGU")                       # registry hit
    assert "leveraged" in detect_categories("SOXL", name="Direxion Daily Semi Bull 3X")
    assert "etf" in detect_categories("SPY", quote_type="ETF")
    assert "leveraged" not in detect_categories("SPY", quote_type="ETF")
    cats = detect_categories("AAPL", sector="Technology", quote_type="EQUITY", dividend=1.0)
    assert {"tech", "dividend"} <= cats


def _rising_data(ticker="TST", n=260):
    closes = [float(x) for x in range(1, n + 1)]
    o = {"dates": [], "open": closes, "high": closes, "low": closes,
         "close": closes, "volume": [1_000_000.0] * n}
    snap = FundamentalSnapshot(
        ticker=ticker, as_of="2026-01-01", price=float(n), market_cap=1e9,
        eps=5.0, beta=1.1, dividend_annual=2.0, sector="Technology",
        quote_type="EQUITY", fifty_two_week_high=float(n), fifty_two_week_low=1.0,
        name="Test Corp")
    return TickerData(ticker, o, snap)


def test_build_row_rising_series():
    row = build_row(_rising_data(), SignalConfig())
    assert row.price == pytest.approx(260.0)
    assert row.rsi == pytest.approx(100.0)                # strictly rising
    assert row.changes["1d"] == pytest.approx(260 / 259 - 1)
    assert row.pe == pytest.approx(260 / 5)               # price/eps
    assert row.dividend_yield == pytest.approx(2 / 260)
    assert {"tech", "dividend"} <= row.categories
    assert "near_52w_high" in row.flags                   # price == 52w high
    assert row.trend_score > 0                            # uptrend
    assert len(row.sparkline) == 30


def test_build_row_error():
    td = TickerData("BAD", {"close": []}, None, error="boom")
    row = build_row(td, SignalConfig())
    assert row.error == "boom"
    assert row.price is None


def _boom(*a, **k):
    raise RuntimeError("network called during fast build")


def test_fast_build_is_network_free(monkeypatch):
    """live=False must render the cached-snapshot board without touching Yahoo
    (price_map) or Finnhub (the overlay) — that's what makes cold start instant."""
    import stockskill.watchlist.build as build_mod

    monkeypatch.setattr("stockskill.data.prices.price_map", _boom)
    monkeypatch.setattr(build_mod, "_overlay_live_prices", _boom)

    # Fast path: booby-trapped network fns are never called -> no error.
    html, meta = build_mod.build_watchlist_html(
        "[T]\nAAPL, MSFT\n", cache_dir="data/cache", served=True, ttl=2592000, live=False)
    assert "card-price" in html and meta["n"] == 2

    # Live path WOULD call price_map -> the booby trap fires, proving the
    # difference is real (not that the fns were simply absent).
    with pytest.raises(RuntimeError):
        build_mod.build_watchlist_html(
            "[T]\nAAPL\n", cache_dir="data/cache", served=True, ttl=2592000, live=True)


def test_factor_chip_and_cell_render():
    from types import SimpleNamespace
    from stockskill.watchlist.render import _factor_chip, _factor_cell
    r = SimpleNamespace(factor={"label": "cheap · high quality", "composite": 83,
                                "value": 90, "quality": 78, "momentum": 40})
    chip = _factor_chip(r)
    assert "cheap · high quality" in chip and "factor 83" in chip
    cell = _factor_cell(r)
    assert 'data-sort="83"' in cell and ">83<" in cell
    # a 2-line read lives inside a fixed-height slot (keeps cards aligned)
    assert 'class="fchip"' in chip and 'class="fpill"' in chip
    # no factor data -> empty slot (still reserves height), muted dash cell (sorts last)
    blank = SimpleNamespace(factor={})
    assert _factor_chip(blank) == '<div class="fchip"></div>'
    assert 'data-sort="-1"' in _factor_cell(blank)


def test_analysis_page_and_trimmed_modal():
    import pickle
    from stockskill.watchlist import build_row
    from stockskill.signals import SignalConfig
    from stockskill.server.analysis_page import analysis_html
    from stockskill.watchlist.render import _card_detail
    td = pickle.load(open("data/cache/GOOGL.pkl", "rb"))
    row = build_row(td, SignalConfig.from_env())
    # full analysis page has the dense sections
    page = analysis_html(row)
    assert "Stock analyzer" in page and "Trade setup" in page
    # modal is trimmed: no full method table, but has the button to the page
    modal = _card_detail(row)
    assert "analysis-btn" in modal and "/analysis/GOOGL" in modal
    assert modal.count("fvtable") == 0            # dense valuation moved off the modal
