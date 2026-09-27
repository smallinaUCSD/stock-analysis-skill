"""The whole-market crawl: biggest first, skips fresh caches, backs off when
the data provider refuses, and records progress. No network (fake fetcher)."""

import os
import time

from stockskill.data import market_crawl as C
from stockskill.watchlist.pipeline import TickerData


def _good(t):
    return TickerData(t, {"dates": ["2026-09-25"], "open": [1], "high": [1], "low": [1], "close": [1.0], "volume": [1]},
                      {"name": t}, fetched_at=time.time())


def test_order_biggest_first_once():
    rows = [{"ticker": "SMALL", "mcap": 1e9, "price": 5}, {"ticker": "BIG", "mcap": 3e12, "price": 200},
            {"ticker": "big", "mcap": 3e12, "price": 200}, {"ticker": "NOPRICE", "mcap": 5e11, "price": None},
            {"ticker": "MID", "mcap": 5e10, "price": 40}]
    assert C.order(rows) == ["BIG", "MID", "SMALL"]


def test_pass_skips_fresh_and_records_progress(tmp_path, monkeypatch):
    import stockskill.watchlist.pipeline as P
    monkeypatch.setattr(P, "_is_good", lambda td: bool(td and td.snapshot))
    (tmp_path / "AAA.pkl").write_bytes(b"x")                        # cached just now: skipped
    old = tmp_path / "BBB.pkl"
    old.write_bytes(b"x")
    t = time.time() - 30 * 86400
    os.utime(old, (t, t))                                           # a month old: refetched
    got, naps = [], []
    st = C.one_pass(str(tmp_path), ["AAA", "BBB", "CCC"], "5y", pace=6.0,
                    fetch=lambda tk: got.append(tk) or _good(tk), sleep=naps.append, is_open=lambda: True)
    assert got == ["BBB", "CCC"] and st["cached"] == 1 and st["fetched"] == 2 and st["state"] == "resting"
    assert naps == [12.0, 12.0]                                     # slower while the market is open
    assert C.status(str(tmp_path))["done"] == 3


def test_backs_off_after_a_run_of_failures(tmp_path):
    naps = []
    st = C.one_pass(str(tmp_path), [f"T{i}" for i in range(C.FAILS_BEFORE_BACKOFF + 2)], "5y", pace=1.0,
                    fetch=lambda tk: None, sleep=naps.append)
    assert C.BACKOFF in naps and st["failed"] == C.FAILS_BEFORE_BACKOFF + 2
