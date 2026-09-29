import pytest


@pytest.fixture(autouse=True)
def _isolate_live_quote_cache():
    """Module-level caches (live quotes, failed-fetch backoff, symbol search, news, the
    FMP quota cooldown) are cleared around every test so mocks never leak."""
    from stockskill.watchlist import build, pipeline
    from stockskill.data import fmp, news, search

    def reset():
        build._QUOTES.clear()
        pipeline._FAIL_UNTIL.clear()
        search._CACHE.clear()
        news._CACHE.clear()
        fmp._exhausted_until = 0.0

    reset()
    yield
    reset()


@pytest.fixture(autouse=True)
def _no_network_board_builds(monkeypatch):
    """create_app() kicks off a background board build that fetches every ticker in
    data/tickers.csv from Yahoo. In tests that was hundreds of real requests per run
    (enough to get a home IP throttled) and could write into the real cache, for
    nothing: no test needs it. Tests drive builds directly instead."""
    from stockskill.server.watchlist_service import WatchlistService
    if not hasattr(WatchlistService, "_real_start_bg_build"):      # for the tests of the method itself
        WatchlistService._real_start_bg_build = WatchlistService._start_bg_build
    monkeypatch.setattr(WatchlistService, "_start_bg_build", lambda self: None)


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch):
    """Tests never call the paid/keyed providers, even when run from a shell with
    the .env loaded; a test that needs a key sets a fake one itself."""
    for k in ("FMP_API_KEY", "FINNHUB_API_KEY", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
              "SEC_USER_AGENT", "NTFY_TOPIC", "STOCKSKILL_ALERTS_FILE", "STOCKSKILL_PUBLIC_URL"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _analytics_to_tmp(tmp_path, monkeypatch):
    """Analytics from the accounts tests go to a throwaway file, never data/."""
    monkeypatch.setenv("STOCKSKILL_ANALYTICS_DB", str(tmp_path / "analytics.db"))
    monkeypatch.delenv("STOCKSKILL_ADMINS", raising=False)
    # texts never reach a real Messages helper from a test
    monkeypatch.setenv("STOCKSKILL_IMESSAGE_DIR", str(tmp_path / "imessage"))


@pytest.fixture(autouse=True)
def _no_yahoo_price_fallback(monkeypatch):
    """The board fills quotes the feed missed from Yahoo; tests that drive the
    overlay must never reach the network for that. Tests of the fallback stub
    it themselves."""
    from stockskill.watchlist import build
    if not hasattr(build, "_real_fill_missing_quotes"):
        build._real_fill_missing_quotes = build.fill_missing_quotes
    monkeypatch.setattr(build, "fill_missing_quotes", lambda tickers, since: 0)
