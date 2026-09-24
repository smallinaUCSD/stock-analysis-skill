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
    monkeypatch.setattr(WatchlistService, "_start_bg_build", lambda self: None)


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch):
    """Tests never call the paid/keyed providers, even when run from a shell with
    the .env loaded; a test that needs a key sets a fake one itself."""
    for k in ("FMP_API_KEY", "FINNHUB_API_KEY", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
        monkeypatch.delenv(k, raising=False)
