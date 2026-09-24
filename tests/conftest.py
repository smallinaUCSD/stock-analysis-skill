import pytest


@pytest.fixture(autouse=True)
def _isolate_live_quote_cache():
    """The board keeps module-level caches (live quotes, failed-fetch backoff);
    clear them around every test so one test's mocks can never leak into another."""
    from stockskill.watchlist import build, pipeline
    build._QUOTES.clear()
    pipeline._FAIL_UNTIL.clear()
    yield
    build._QUOTES.clear()
    pipeline._FAIL_UNTIL.clear()
