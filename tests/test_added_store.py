"""Added-ticker persistence: the Upstash-backed store and its wiring."""

import json

import pytest

from stockskill.server import added_store


def test_store_disabled_without_env(monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    monkeypatch.delenv("STOCKSKILL_ADDED_FILE", raising=False)
    assert not added_store.enabled()
    assert added_store.load_added() is None       # unavailable -> caller keeps in-memory
    assert added_store.save_added(["NVDA"]) is False


def test_file_backend_round_trips_and_wins(monkeypatch, tmp_path):
    """Local-file backend (for ngrok/local dev): persists to disk, no network,
    and takes precedence over Upstash when both are set."""
    path = tmp_path / "added.json"
    monkeypatch.setenv("STOCKSKILL_ADDED_FILE", str(path))
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://ex.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "tok")

    def boom(*a, **k):
        raise AssertionError("hit the network though a local file was configured")

    monkeypatch.setattr("requests.get", boom)
    monkeypatch.setattr("requests.post", boom)
    assert added_store.enabled()
    assert added_store.load_added() == []            # missing file -> empty
    assert added_store.save_added(["nvda", "tsla"]) is True
    assert added_store.load_added() == ["NVDA", "TSLA"]   # persisted + upper-cased


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def _configured(monkeypatch):
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://ex.upstash.io/")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "tok")


def test_load_round_trips_json(monkeypatch):
    _configured(monkeypatch)
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["auth"] = headers["Authorization"]
        return _Resp(200, {"result": json.dumps(["nvda", "tsla"])})

    monkeypatch.setattr("requests.get", fake_get)
    assert added_store.enabled()
    assert added_store.load_added() == ["NVDA", "TSLA"]   # upper-cased
    assert captured["url"].endswith("/get/stockskill:added")  # no double slash
    assert captured["auth"] == "Bearer tok"


def test_load_empty_key_is_empty_list(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(200, {"result": None}))
    assert added_store.load_added() == []


def test_load_error_status_is_none(monkeypatch):
    _configured(monkeypatch)
    monkeypatch.setattr("requests.get", lambda *a, **k: _Resp(500, {}))
    assert added_store.load_added() is None

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("requests.get", boom)
    assert added_store.load_added() is None            # never raises to the caller


def test_save_posts_json_value(monkeypatch):
    _configured(monkeypatch)
    sent = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        sent["url"] = url
        sent["data"] = data
        return _Resp(200, {"result": "OK"})

    monkeypatch.setattr("requests.post", fake_post)
    assert added_store.save_added(["NVDA", "TSLA"]) is True
    assert sent["url"].endswith("/set/stockskill:added")
    assert json.loads(sent["data"]) == ["NVDA", "TSLA"]


def test_init_never_blocks_on_the_store(monkeypatch):
    """__init__ must NOT touch the network (a slow store would 502 boot)."""
    from stockskill.server.watchlist_service import WatchlistService

    def boom():
        raise AssertionError("store hit during __init__ (blocks worker boot)")

    monkeypatch.setattr(added_store, "load_added", boom)
    monkeypatch.setattr(added_store, "enabled", lambda: True)
    svc = WatchlistService(cache_dir="data/cache")   # no exception -> no boot-path I/O
    assert svc.added() == []


def test_service_restores_persisted_added(monkeypatch):
    """A restarted host restores its adds from the store on the first load."""
    from stockskill.server.watchlist_service import WatchlistService
    monkeypatch.setattr(added_store, "enabled", lambda: True)
    monkeypatch.setattr(added_store, "load_added", lambda: ["NVDA", "TSLA"])
    svc = WatchlistService(cache_dir="data/cache")
    svc._ensure_loaded()                              # runs in the bg build on the host
    assert svc.added() == ["NVDA", "TSLA"]
    # and they flow into the ticker spec used to build the board
    assert "[ADDED]" in svc._spec() and "NVDA, TSLA" in svc._spec()


def test_ensure_loaded_retries_after_transient_failure(monkeypatch):
    """A None (failed) load leaves the service unloaded so the next build retries."""
    from stockskill.server.watchlist_service import WatchlistService
    monkeypatch.setattr(added_store, "enabled", lambda: True)
    monkeypatch.setattr(added_store, "load_added", lambda: None)
    svc = WatchlistService(cache_dir="data/cache")
    svc._ensure_loaded()
    assert svc._loaded is False                       # not marked done -> will retry
    monkeypatch.setattr(added_store, "load_added", lambda: ["NVDA"])
    svc._ensure_loaded()
    assert svc._loaded is True and svc.added() == ["NVDA"]
