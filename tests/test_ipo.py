from datetime import date

from stockskill.data.ipo import _price_range, normalize, split

ROWS = [
    {"date": "2026-09-30", "symbol": "oura", "name": "Oura Inc.", "exchange": "NASDAQ",
     "numberOfShares": 50_000_000, "price": "40.00-44.00", "status": "expected", "totalSharesValue": None},
    {"date": "2026-09-26", "symbol": "BIG", "name": "Big Co", "exchange": "NYSE",
     "numberOfShares": 10_000_000, "price": "20", "status": "expected", "totalSharesValue": 200_000_000},
    {"date": "2026-09-10", "symbol": "NEW", "name": "New Co", "price": "15", "status": "priced"},
    {"date": "2026-09-28", "symbol": "WD", "name": "Pulled Co", "price": "10-12", "status": "withdrawn"},
    {"date": "2026-09-23", "symbol": "LOVIU", "name": "Live Oak Acquisition Corp. V", "price": "10", "status": "priced"},
]


def test_price_range():
    assert _price_range("40.00-44.00") == (40.0, 44.0)
    assert _price_range("$18") == (18.0, 18.0)
    assert _price_range(None) == (None, None) and _price_range("tbd") == (None, None)


def test_normalize_and_split():
    rows = normalize(ROWS)
    oura = rows[0]
    assert oura["symbol"] == "OURA" and oura["value"] == 50_000_000 * 42.0
    s = split(rows, date(2026, 9, 24))
    assert [r["symbol"] for r in s["upcoming"]] == ["BIG", "OURA"]      # soonest first
    assert [r["symbol"] for r in s["recent"]] == ["LOVIU", "NEW"]
    assert [r["spac"] for r in s["recent"]] == [True, False] and not oura["spac"]
    assert all(r["symbol"] != "WD" for r in s["upcoming"] + s["recent"])  # withdrawn dropped


def test_ipo_routes(tmp_path, monkeypatch):
    from stockskill.server import create_app
    monkeypatch.setattr("stockskill.data.ipo.calendar",
                        lambda **k: {"upcoming": [{"symbol": "OURA"}], "recent": [], "as_of": "2026-09-24"})
    c = create_app(tickers_path=str(tmp_path / "t.csv"), public=True).test_client()
    d = c.get("/api/ipos").get_json()
    assert d["ok"] and d["upcoming"][0]["symbol"] == "OURA"
    assert "page-x" in c.get("/ipos").get_data(as_text=True)
    monkeypatch.setattr("stockskill.data.ipo.calendar", lambda **k: None)
    assert c.get("/api/ipos").status_code == 503
