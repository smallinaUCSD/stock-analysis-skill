"""Speed fixes: page calls get priority over background quote work, each
person's board carries only their stocks, responses are gzipped, and local
time stays fast in forked workers on macOS."""

import gzip
import os
import re
import sys
import threading
import time

import pytest


def test_background_leaves_a_reserve_for_pages():
    from stockskill.data import finnhub as F
    lim = F._RateLimiter(10, 60.0)
    assert lim.reserve == 2
    F.foreground(False)
    for _ in range(8):
        lim.acquire()                                   # background may use 8 of 10
    got = []
    t = threading.Thread(target=lambda: (lim.acquire(), got.append(1)), daemon=True)
    t.start()
    t.join(0.3)
    assert not got                                      # a 9th background call waits
    F.foreground(True)
    t0 = time.monotonic()
    lim.acquire()
    lim.acquire()                                       # a page gets the reserve at once
    assert time.monotonic() - t0 < 0.1
    F.foreground(False)


def test_batch_quotes_threads_inherit_priority(monkeypatch):
    from stockskill.data import finnhub as F
    seen = []
    monkeypatch.setattr(F._LIMITER, "acquire", lambda: seen.append(getattr(F._FG, "on", False)))
    monkeypatch.setattr(F, "quote", lambda s: {"price": 1.0})
    F.foreground(True)
    F.batch_quotes(["AAA", "BBB"])
    F.foreground(False)
    F.batch_quotes(["CCC"])
    assert seen[:2] == [True, True] and seen[2] is False


def test_board_for_one_person_has_only_their_stocks(monkeypatch):
    from stockskill.server.watchlist_service import WatchlistService
    from stockskill import watchlist as W
    from stockskill.alerts.engine import Alert

    class Row:
        def __init__(self, t):
            self.ticker = t
    drawn = []
    monkeypatch.setattr(W, "render_watchlist", lambda rows, **kw: drawn.append((rows, kw)) or
                        "<b>" + ",".join(r.ticker for r in rows) + "</b>")
    svc = WatchlistService()
    monkeypatch.setattr(svc, "html", lambda force=False: "FULL")
    assert svc.html_for(["AAA"]) == "FULL"                     # before the first build
    alerts = [Alert("AAA", "surge", "up", "!"), Alert("BBB", "surge", "up", "!")]
    svc._parts = ([Row("AAA"), Row("BBB"), Row("CCC")], {"alerts": alerts, "title": "x"})
    assert svc.html_for(["ccc", "AAA"]) == "<b>AAA,CCC</b>"    # board order, case-insensitive
    assert [a.ticker for a in drawn[-1][1]["alerts"]] == ["AAA"]
    svc.html_for(["ccc", "AAA"])
    assert len(drawn) == 1                                     # cached until the next build
    assert svc.html_for(["ZZZ"]) == "FULL"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKSKILL_AUTH", "1")
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    tk = tmp_path / "t.csv"
    tk.write_text("[M7]\nAAPL\n")
    from stockskill.server import create_app
    a = create_app(tickers_path=str(tk), public=True)
    a.config["ACCT"]["board"] = None
    return a


def test_text_responses_are_gzipped(app):
    c = app.test_client()
    plain = c.get("/terms")
    z = c.get("/terms", headers={"Accept-Encoding": "gzip, br"})
    assert "Content-Encoding" not in plain.headers
    assert z.headers["Content-Encoding"] == "gzip" and "Accept-Encoding" in z.headers["Vary"]
    assert gzip.decompress(z.data) == plain.data and len(z.data) < len(plain.data) / 2
    assert "Content-Encoding" not in c.get("/healthz", headers={"Accept-Encoding": "gzip"}).headers   # tiny


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_local_time_rule_on_macos(monkeypatch):
    from stockskill.server.app import _fast_local_time
    monkeypatch.delenv("TZ", raising=False)
    try:
        _fast_local_time()
        assert re.fullmatch(r"[A-Za-z<].{2,60}", os.environ.get("TZ", ""))
    finally:
        monkeypatch.undo()
        time.tzset()
