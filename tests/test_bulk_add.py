"""Bulk add runs in the background, reports per-ticker results, and never lets a
stale rebuild drop newly added tickers; the quote cache keeps add-rebuilds cheap."""

import time
from types import SimpleNamespace

import pytest

from stockskill.server import watchlist_service as ws
from stockskill.server.watchlist_service import WatchlistService, parse_ticker_list


def test_parse_ticker_list_splits_dedupes_uppercases():
    assert parse_ticker_list("IBIT MSTR, ftnet;S\n  spaceX mstr") == \
        ["IBIT", "MSTR", "FTNET", "S", "SPACEX"]
    assert parse_ticker_list(["net", " okta ", "NET", ""]) == ["NET", "OKTA"]
    assert parse_ticker_list("") == []


def _svc(tmp_path, monkeypatch, good=("NET", "OKTA")):
    """A service over a tiny ticker file, with network/rebuild stubbed out."""
    tf = tmp_path / "t.csv"
    tf.write_text("[T]\nAAPL, MSFT\n")
    monkeypatch.delenv("STOCKSKILL_ADDED_FILE", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    svc = WatchlistService(tickers_path=str(tf), cache_dir=str(tmp_path))
    good = set(good)
    svc._verify = lambda t: t in good
    monkeypatch.setattr(ws, "_providers_up", lambda: True)
    monkeypatch.setattr(ws, "_suggest", lambda t: {"symbol": "FTNT", "name": "Fortinet"})
    svc.rebuilds = 0

    def quick():
        svc.rebuilds += 1
        return ""

    svc._quick_rebuild = quick
    return svc


def _wait(svc, job_id, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        st = svc.job_status(job_id)
        if st["state"] == "done":
            return st
        time.sleep(0.02)
    raise AssertionError("add job did not finish")


def test_add_bulk_returns_immediately_then_reports_per_ticker(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    res = svc.add_bulk("net, OKTA ftnet aapl bad$sym")
    assert res["ok"] and res["queued"] == ["NET", "OKTA", "FTNET"]
    reasons = {s["ticker"]: s["reason"] for s in res["skipped"]}
    assert reasons == {"AAPL": "already on the board", "BAD$SYM": "not a valid symbol"}

    st = _wait(svc, res["job"])
    assert st["total"] == 3 and st["done"] == 3
    assert sorted(st["added"]) == ["NET", "OKTA"]
    assert st["failed"] == [{"ticker": "FTNET", "error": "no data (unknown ticker?)",
                             "suggest": {"symbol": "FTNT", "name": "Fortinet"},
                             "retry": False}]
    assert svc.added() == ["NET", "OKTA"]          # in the order the user typed
    assert svc.rebuilds == 1                         # ONE rebuild for the whole batch
    assert svc._gen == 1


def test_add_bulk_nothing_new_finishes_without_a_job_thread(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    res = svc.add_bulk("AAPL msft")
    assert res["ok"] and res["queued"] == []
    assert svc.job_status(res["job"])["state"] == "done"
    assert svc.rebuilds == 0


def test_add_bulk_limits_and_unknown_job(tmp_path, monkeypatch):
    svc = _svc(tmp_path, monkeypatch)
    assert not svc.add_bulk("")["ok"]
    too_many = " ".join(f"T{i}" for i in range(ws.MAX_BULK + 1))
    assert "max" in svc.add_bulk(too_many)["error"]
    assert svc.job_status("nope") is None


def test_stale_rebuild_never_replaces_a_newer_board(tmp_path, monkeypatch):
    tf = tmp_path / "t.csv"
    tf.write_text("[T]\nAAPL\n")
    svc = WatchlistService(tickers_path=str(tf), cache_dir=str(tmp_path))
    monkeypatch.setattr(ws, "build_watchlist_html",
                        lambda spec, **kw: (f"board:{spec.count(',')}", {"refresh": 900}))
    svc._rebuild()                                   # gen 0 board
    assert svc._html_gen == 0
    svc._html, svc._html_gen = "NEW", 2              # a board from a later add landed
    svc._gen = 1                                     # ...then a build from gen 1 finishes
    svc._rebuild()
    assert svc._html == "NEW" and svc._html_gen == 2  # not regressed


def test_quote_cache_fetches_only_new_tickers(monkeypatch):
    from stockskill.data import finnhub
    from stockskill.watchlist.build import _overlay_live_prices
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    calls = []

    def fake(tks):
        calls.append(list(tks))
        return {t: {"price": 100.0 + len(t), "change_pct": 0.01} for t in tks}

    monkeypatch.setattr(finnhub, "batch_quotes", fake)

    def rows(*tks):
        return [SimpleNamespace(ticker=t, price=1.0, changes={}) for t in tks]

    _overlay_live_prices(rows("AAPL", "MSFT"), SimpleNamespace(label="open"))
    # an add-triggered rebuild reuses fresh quotes: only the NEW ticker is fetched
    r = rows("AAPL", "MSFT", "NET")
    _overlay_live_prices(r, SimpleNamespace(label="open"), max_age=900)
    assert calls == [["AAPL", "MSFT"], ["NET"]]
    assert [x.price for x in r] == [104.0, 104.0, 103.0]
    # the scheduled refresh (max_age=0) re-quotes everything
    _overlay_live_prices(rows("AAPL", "MSFT", "NET"), SimpleNamespace(label="open"))
    assert calls[-1] == ["AAPL", "MSFT", "NET"]


def test_quote_cache_keeps_last_live_price_when_a_fetch_fails(monkeypatch):
    from stockskill.data import finnhub
    from stockskill.watchlist.build import _overlay_live_prices
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    monkeypatch.setattr(finnhub, "batch_quotes",
                        lambda tks: {"AAPL": {"price": 250.0, "change_pct": 0.02}})
    _overlay_live_prices([SimpleNamespace(ticker="AAPL", price=1.0, changes={})],
                         SimpleNamespace(label="open"))
    monkeypatch.setattr(finnhub, "batch_quotes", lambda tks: {})   # outage
    r = SimpleNamespace(ticker="AAPL", price=190.0, changes={})
    _overlay_live_prices([r], SimpleNamespace(label="open"))
    assert r.price == 250.0                           # last live, not the stale snapshot


def test_bulk_routes(tmp_path, monkeypatch):
    from stockskill.server import create_app
    import stockskill.server.watchlist_service as mod
    # A throwaway cache and NO startup build: the app must never refetch into the
    # real data/cache from a test (it once overwrote AAPL/MSFT/NVDA with 1y data).
    monkeypatch.setenv("STOCKSKILL_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(mod.WatchlistService, "_start_bg_build", lambda self: None)
    app = create_app(tickers_path=str(tmp_path / "missing.csv"), public=True)
    c = app.test_client()
    # stub the service method the route calls, so no network is touched
    monkeypatch.setattr(mod.WatchlistService, "add_bulk",
                        lambda self, t: {"ok": True, "job": "abc", "queued": parse_ticker_list(t),
                                         "skipped": []})
    monkeypatch.setattr(mod.WatchlistService, "job_status",
                        lambda self, j: {"state": "done", "added": ["NET"]} if j == "abc" else None)
    r = c.post("/api/watchlist/add_bulk", json={"tickers": "net okta"})
    assert r.status_code == 200 and r.get_json()["queued"] == ["NET", "OKTA"]
    assert c.get("/api/watchlist/add_status/abc").get_json()["added"] == ["NET"]
    assert c.get("/api/watchlist/add_status/zzz").status_code == 404


def test_provider_outage_is_reported_as_retryable_not_unknown(tmp_path, monkeypatch):
    """When NOTHING can be fetched (quota exhausted / IP throttled) real tickers
    must not be called 'not found' - they're flagged retryable, no suggestion."""
    svc = _svc(tmp_path, monkeypatch, good=())
    monkeypatch.setattr(ws, "_providers_up", lambda: False)
    st = _wait(svc, svc.add_bulk("NET OKTA")["job"])
    assert st["added"] == [] and [f["ticker"] for f in st["failed"]] == ["NET", "OKTA"]
    assert all(f["retry"] and f["suggest"] is None and "rate-limited" in f["error"]
               for f in st["failed"])
    assert svc.rebuilds == 0 and svc.added() == []


def test_fetch_backs_off_after_an_empty_fetch(tmp_path, monkeypatch):
    """A background build must not re-hammer providers for a name it just failed
    to fetch; an explicit refresh (ttl=0) still tries."""
    from stockskill.watchlist import pipeline as P
    calls = []

    def empty(t, p):
        calls.append(t)
        return {k: [] for k in ("dates", "open", "high", "low", "close", "volume")}

    monkeypatch.setattr(P, "ohlcv", empty)
    monkeypatch.setattr(P, "fetch_snapshot", lambda t: None)
    P.fetch_one("ZZZ", cache_dir=str(tmp_path), ttl=1800.0)      # fails -> backoff set
    P.fetch_one("ZZZ", cache_dir=str(tmp_path), ttl=1800.0)      # backed off: no call
    assert calls == ["ZZZ"]
    P.fetch_one("ZZZ", cache_dir=str(tmp_path), ttl=0.0)         # explicit: tries again
    assert calls == ["ZZZ", "ZZZ"]
