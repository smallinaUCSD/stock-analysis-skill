"""The shared board: session-aware freshness, build ordering, stuck builds."""

import time
from types import SimpleNamespace

from stockskill.server import watchlist_service as WS


def _svc(tmp_path):
    return WS.WatchlistService(tickers_path=str(tmp_path / "t.csv"), cache_dir=str(tmp_path), public=True)


def test_board_built_premarket_is_stale_once_the_market_opens(tmp_path, monkeypatch):
    import stockskill.marketclock as MC
    s = _svc(tmp_path)
    s._html, s._ts, s._refresh, s._session = "<b>", time.time(), 1800, "pre-market"
    monkeypatch.setattr(MC, "market_status", lambda now=None: SimpleNamespace(label="pre-market"))
    assert s.is_fresh()
    monkeypatch.setattr(MC, "market_status", lambda now=None: SimpleNamespace(label="open"))
    assert not s.is_fresh()
    s._session = "open"
    assert s.is_fresh()
    s._ts = time.time() - 2000                                   # past its refresh interval
    assert not s.is_fresh()


def test_an_older_build_never_replaces_a_newer_board(tmp_path, monkeypatch):
    s = _svc(tmp_path)
    monkeypatch.setattr(WS, "build_watchlist_html", lambda *a, **k: (k["period"] + "-html", {"refresh": 900}))
    s._period = "new"
    s._rebuild(serial=5)
    s._period = "old"
    s._rebuild(serial=3)                                         # started earlier, finished later
    assert s._html == "new-html" and s._html_serial == 5 and s._session


def test_a_stuck_build_lets_a_new_one_start(tmp_path, monkeypatch):
    s = _svc(tmp_path)
    started = []
    monkeypatch.setattr(WS.threading, "Thread", lambda target, daemon: SimpleNamespace(start=lambda: started.append(1)))
    s._building, s._build_started = True, time.time()
    WS.WatchlistService._real_start_bg_build(s)
    assert started == []                                         # a recent build is left alone
    s._build_started = time.time() - 1000
    WS.WatchlistService._real_start_bg_build(s)
    assert started == [1] and s._build_serial == 1
