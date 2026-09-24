"""FMP stays the primary source; a spent quota (HTTP 429) benches it for a cooldown
so callers fall straight through to Yahoo, and symbol search is cached."""

import stockskill.data.fmp as fmp
import stockskill.data.search as search


class _R:
    def __init__(self, code, payload=None):
        self.status_code = code
        self._p = payload if payload is not None else {}

    def json(self):
        return self._p


def test_quota_429_benches_fmp_then_reprobes(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "k")
    calls = []
    monkeypatch.setattr("requests.get", lambda *a, **k: calls.append(1) or _R(429))
    assert fmp._get("profile", symbol="NET") is None
    assert fmp.quota_exhausted()
    assert fmp._get("profile", symbol="OKTA") is None      # benched: no request made
    assert len(calls) == 1
    fmp._exhausted_until = 0.0                              # cooldown over -> re-probe
    monkeypatch.setattr("requests.get", lambda *a, **k: calls.append(1) or _R(200, [{"ok": 1}]))
    assert fmp._get("profile", symbol="NET") == [{"ok": 1}]
    assert len(calls) == 2 and not fmp.quota_exhausted()


def test_other_errors_do_not_bench_fmp(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "k")
    monkeypatch.setattr("requests.get", lambda *a, **k: _R(402))   # premium-only endpoint
    assert fmp._get("etf/holdings", symbol="QQQ") is None
    assert not fmp.quota_exhausted()


def test_search_is_cached_and_falls_back_to_yahoo(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "k")
    fmp_calls, yahoo_calls = [], []
    monkeypatch.setattr(fmp, "search", lambda q, limit=12: fmp_calls.append(q) or None)  # FMP empty
    monkeypatch.setattr(search, "_fetch_quotes", lambda q: yahoo_calls.append(q) or
                        [{"symbol": "NET", "shortname": "Cloudflare", "quoteType": "EQUITY",
                          "exchDisp": "NYSE"}])
    first = search.search_symbols("net")
    again = search.search_symbols("NET")                  # same query, any case
    assert first == again and first[0]["symbol"] == "NET"
    assert len(fmp_calls) == 1 and len(yahoo_calls) == 1   # FMP tried first, Yahoo backed it up
