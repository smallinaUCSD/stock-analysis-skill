import pytest

from stockskill.portfolio.manage import (
    HoldingRow, apply_trade, reprice, read_rows, write_rows, find,
)


def test_buy_new_and_add():
    rows = []
    r = apply_trade(rows, "AAPU", "brokerage", 10, 45.0)
    assert r.shares == pytest.approx(10) and r.market_value == pytest.approx(450)
    r = apply_trade(rows, "AAPU", "brokerage", 5, 50.0)      # add at a new price
    assert r.shares == pytest.approx(15) and r.market_value == pytest.approx(750)  # 15*50


def test_sell_partial_and_close():
    rows = [HoldingRow("X", "brokerage", 15.0, 750.0)]
    r = apply_trade(rows, "X", "brokerage", -5, 50.0)
    assert r.shares == pytest.approx(10) and r.market_value == pytest.approx(500)
    closed = apply_trade(rows, "X", "brokerage", -10, 50.0)
    assert closed is None and find(rows, "X", "brokerage") is None


def test_sell_nonexistent_raises():
    with pytest.raises(ValueError):
        apply_trade([], "NOPE", "brokerage", -1, 10.0)


def test_legacy_dollar_row_infers_shares():
    rows = [HoldingRow("Y", "brokerage", None, 1000.0)]   # dollar-only, no shares
    r = apply_trade(rows, "Y", "brokerage", 10, 50.0)     # infer 1000/50=20, +10=30
    assert r.shares == pytest.approx(30) and r.market_value == pytest.approx(1500)


def test_reprice():
    rows = [HoldingRow("A", "b", 10.0, 100.0), HoldingRow("CASH", "b", None, 5000.0)]
    n = reprice(rows, lambda tk: 12.0 if tk == "A" else None)
    assert n == 1
    assert rows[0].market_value == pytest.approx(120.0)   # 10 * 12
    assert rows[1].market_value == pytest.approx(5000.0)  # cash untouched (no shares)


def test_read_write_roundtrip(tmp_path):
    f = tmp_path / "h.csv"
    write_rows(f, [HoldingRow("AAPU", "brokerage", 10.0, 450.0),
                   HoldingRow("CASH", "brokerage", None, 1000.0)])
    rows = read_rows(f)
    assert rows[0].ticker == "AAPU" and rows[0].shares == pytest.approx(10)
    assert rows[1].shares is None and rows[1].market_value == pytest.approx(1000)
