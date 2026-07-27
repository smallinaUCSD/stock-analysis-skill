from stockskill.server.holdings_service import HoldingsService


def _svc(tmp_path):
    p = tmp_path / "h.csv"
    p.write_text("ticker,market_value,account\n"
                 "AAPU,1000,brokerage\nCASH,500,brokerage\nFCNTX,2000,roth\n")
    return HoldingsService(str(p)), p


def test_snapshot_groups_by_account(tmp_path):
    svc, _ = _svc(tmp_path)
    snap = svc.snapshot()
    accts = {a["key"]: a for a in snap["accounts"]}
    assert accts["brokerage"]["total"] == 1500
    assert accts["brokerage"]["cash"] == 500
    assert accts["roth"]["total"] == 2000
    assert snap["grand_total"] == 3500
    assert snap["grand_cash"] == 500


def test_buy_debits_cash_and_persists(tmp_path):
    svc, _ = _svc(tmp_path)
    res = svc.trade("AAPU", "brokerage", "buy", 200, settle_cash=True)
    assert res["ok"]
    accts = {a["key"]: a for a in svc.snapshot()["accounts"]}
    pos = {p["ticker"]: p["market_value"] for p in accts["brokerage"]["positions"]}
    assert pos["AAPU"] == 1200
    assert accts["brokerage"]["cash"] == 300  # 500 - 200


def test_sell_more_than_held_closes_position(tmp_path):
    svc, _ = _svc(tmp_path)
    svc.trade("AAPU", "brokerage", "sell", 1000, settle_cash=True)
    accts = {a["key"]: a for a in svc.snapshot()["accounts"]}
    assert all(p["ticker"] != "AAPU" for p in accts["brokerage"]["positions"])
    assert accts["brokerage"]["cash"] == 1500  # 500 + 1000


def test_cannot_sell_absent_position(tmp_path):
    svc, _ = _svc(tmp_path)
    assert not svc.trade("ZZZ", "brokerage", "sell", 100)["ok"]


def test_deposit_and_withdraw_cash(tmp_path):
    svc, _ = _svc(tmp_path)
    assert svc.cash("roth", "deposit", 300)["balance"] == 300
    assert svc.cash("roth", "withdraw", 100)["balance"] == 200


def test_priced_buy_sets_shares_and_cost_basis(tmp_path):
    # a brand-new position with a price -> shares + cost basis recorded (no fetch)
    svc, _ = _svc(tmp_path)
    assert svc.trade("SOXL", "brokerage", "buy", 1000, settle_cash=False, price=25.0)["ok"]
    from stockskill.portfolio.manage import read_rows
    r = {(x.ticker, x.account): x for x in read_rows(svc._path)}[("SOXL", "brokerage")]
    assert r.shares == 40.0            # 1000 / 25
    assert r.cost_basis == 25.0
    assert r.market_value == 1000.0


def test_priced_buy_blends_cost_basis(tmp_path):
    svc, _ = _svc(tmp_path)
    svc.trade("SOXL", "brokerage", "buy", 1000, settle_cash=False, price=25.0)   # 40 sh @ 25
    svc.trade("SOXL", "brokerage", "buy", 1000, settle_cash=False, price=50.0)   # +20 sh @ 50
    from stockskill.portfolio.manage import read_rows
    r = {(x.ticker, x.account): x for x in read_rows(svc._path)}[("SOXL", "brokerage")]
    assert r.shares == 60.0
    assert abs(r.cost_basis - 2000 / 60) < 1e-3   # blended avg (persisted at 4dp)
