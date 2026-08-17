"""Point-in-time fundamentals store: record, load, and as-of lookup."""

from stockskill.data.fundamentals import FundamentalSnapshot
from stockskill.factors.history import record_snapshots, load_history, snapshot_at


def _snap(tk, price, eps):
    return FundamentalSnapshot(ticker=tk, as_of="x", name=tk, price=price, eps=eps)


def test_record_and_load_roundtrip(tmp_path):
    store = str(tmp_path / "hist")
    n = record_snapshots([_snap("AAPL", 100.0, 5.0), _snap("MSFT", 200.0, 8.0)],
                         store, as_of="2026-01-02")
    assert n == 2
    hist = load_history(store)
    assert "2026-01-02" in hist
    assert hist["2026-01-02"]["AAPL"]["price"] == 100.0
    assert hist["2026-01-02"]["MSFT"]["eps"] == 8.0


def test_record_skips_unnamed(tmp_path):
    store = str(tmp_path / "h")
    bad = FundamentalSnapshot(ticker="ZZZZ", as_of="x")     # name=None -> skipped
    n = record_snapshots([_snap("AAPL", 100.0, 5.0), bad], store, as_of="2026-01-03")
    assert n == 1
    assert "ZZZZ" not in load_history(store)["2026-01-03"]


def test_snapshot_at_picks_latest_on_or_before(tmp_path):
    store = str(tmp_path / "h")
    record_snapshots([_snap("AAPL", 100.0, 5.0)], store, as_of="2026-01-01")
    record_snapshots([_snap("AAPL", 120.0, 6.0)], store, as_of="2026-01-10")
    hist = load_history(store)
    assert snapshot_at(hist, "AAPL", "2026-01-05").price == 100.0   # on-or-before
    assert snapshot_at(hist, "AAPL", "2026-01-10").price == 120.0
    assert snapshot_at(hist, "AAPL", "2025-12-31") is None          # before history
