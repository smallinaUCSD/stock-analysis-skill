import time
from stockskill.watchlist import pipeline as P
from stockskill.watchlist.pipeline import TickerData, _is_good


class _Snap:
    def __init__(self, name): self.name = name


def _td(closes, snap_name, error=None, ts=0.0):
    ohlcv = {"dates": [1]*len(closes), "close": closes, "open": closes,
             "high": closes, "low": closes, "volume": [1]*len(closes)}
    return TickerData("X", ohlcv, _Snap(snap_name) if snap_name else None, error=error, fetched_at=ts)


def test_is_good_requires_prices_and_fundamentals():
    assert _is_good(_td([10.0], "Acme Inc")) is True
    assert _is_good(_td([10.0], None)) is False          # prices but no fundamentals
    assert _is_good(_td([], "Acme Inc")) is False         # no price series
    assert _is_good(_td([10.0], "Acme", error="boom")) is False


def test_fetch_one_keeps_good_cache_on_bad_refetch(tmp_path, monkeypatch):
    import pickle, os
    d = str(tmp_path)
    good = _td([10.0, 11.0], "Acme Inc", ts=0.0)
    pickle.dump(good, open(os.path.join(d, "X.pkl"), "wb"))
    # simulate a rate-limited refetch: empty ohlcv + empty snapshot
    monkeypatch.setattr(P, "ohlcv", lambda t, p: {k: [] for k in
                        ("dates", "open", "high", "low", "close", "volume")})
    monkeypatch.setattr(P, "fetch_snapshot", lambda t: _Snap(None))
    out = P.fetch_one("X", cache_dir=d, ttl=0.001)   # expired -> refetch -> bad -> keep cached
    assert _is_good(out) and out.ohlcv["close"] == [10.0, 11.0]
