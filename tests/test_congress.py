from stockskill.data.congress import (_amount_range, parse_house_index, parse_house_ptr_text,
                                     parse_senate_ptr_html)

# shape of pypdf's text from an electronic House PTR (labels lose their glyphs -> NULs)
HOUSE_TEXT = """Name: Hon. Test Member
State/District: GA12
ID Owner Asset Transaction
Type
Date Notification
Date
Amount Cap.
Gains >
$200?
SP Broadcom Inc. - Common Stock
(AVGO) [ST]
P 08/12/2026 09/15/2026 $1,001 - $15,000
F\x00\x00\x00\x00\x00 S\x00\x00\x00\x00\x00: New
S\x00\x00\x00\x00\x00\x00 O\x00: Brokerage > Account
Rollins, Inc. Common Stock (ROL)
[ST]
S (partial) 08/12/2026 09/15/2026 $15,001 -
$50,000
F\x00\x00\x00\x00\x00 S\x00\x00\x00\x00\x00: New
JT Some Private Fund LP [HN] E 08/01/2026 08/20/2026 Over $50,000,000
* For the complete list of asset type abbreviations, please visit https://fd.house.gov/
"""

SENATE_HTML = """<table><thead><tr><th>#</th><th>Transaction Date</th><th>Owner</th><th>Ticker</th>
<th>Asset Name</th><th>Asset Type</th><th>Type</th><th>Amount</th><th>Comment</th></tr></thead>
<tbody><tr><td>1</td><td>09/01/2026</td><td>Spouse</td><td>WFC</td><td>Wells Fargo &amp; Company</td>
<td>Stock</td><td>Purchase</td><td>$15,001 - $50,000</td><td>--</td></tr>
<tr><td>2</td><td>09/02/2026</td><td>Self</td><td>--</td><td>Muni bond</td><td>Municipal Security</td>
<td>Sale (Full)</td><td>$1,001 - $15,000</td><td>--</td></tr></tbody></table>"""

HOUSE_XML = b"""<?xml version="1.0"?><FinancialDisclosure>
<Member><First>Richard</First><Last>Allen</Last><FilingType>P</FilingType><StateDst>GA12</StateDst>
<Year>2026</Year><FilingDate>9/22/2026</FilingDate><DocID>20035492</DocID></Member>
<Member><First>A</First><Last>B</Last><FilingType>C</FilingType><StateDst>MN02</StateDst>
<Year>2026</Year><FilingDate>6/11/2026</FilingDate><DocID>1</DocID></Member></FinancialDisclosure>"""


def test_amount_range():
    assert _amount_range("$1,001 - $15,000") == (1001, 15000)
    assert _amount_range("Over $50,000,000") == (50_000_000, None)
    assert _amount_range("") == (None, None)


def test_parse_house_ptr_text():
    rows = parse_house_ptr_text(HOUSE_TEXT)
    assert [(r["owner"], r["ticker"], r["type"]) for r in rows] == [
        ("Spouse", "AVGO", "Buy"), ("Self", "ROL", "Sell (partial)"), ("Joint", None, "Exchange")]
    assert rows[0]["asset"] == "Broadcom Inc. - Common Stock"
    assert rows[0]["traded"] == "2026-08-12" and rows[1]["amount_high"] == 50000
    assert rows[2]["amount_low"] == 50_000_000 and rows[2]["amount_high"] is None
    assert parse_house_ptr_text("") == []


def test_parse_senate_ptr_html():
    rows = parse_senate_ptr_html(SENATE_HTML)
    assert rows[0] == {"owner": "Spouse", "asset": "Wells Fargo & Company", "ticker": "WFC",
                       "asset_type": "Stock", "type": "Buy", "traded": "2026-09-01", "notified": None,
                       "amount": "$15,001 - $50,000", "amount_low": 15001, "amount_high": 50000}
    assert rows[1]["ticker"] is None and rows[1]["type"] == "Sell"
    assert parse_senate_ptr_html("<p>no table</p>") == []


def test_parse_house_index_keeps_only_ptrs():
    f = parse_house_index(HOUSE_XML)
    assert f == [{"chamber": "House", "member": "Richard Allen", "state": "GA12",
                  "filed": "2026-09-22", "doc": "20035492", "year": "2026"}]


def test_trades_routes(tmp_path, monkeypatch):
    from stockskill.server import create_app
    trades = [{"chamber": "House", "member": "Pat Doe", "ticker": "NVDA", "type": "Buy", "filed": "2026-09-20"},
              {"chamber": "Senate", "member": "Sam Roe", "ticker": "AAPL", "type": "Sell", "filed": "2026-09-19"}]
    monkeypatch.setattr("stockskill.data.congress.recent_trades",
                        lambda cache_dir=None, **k: {"trades": trades, "as_of": "x", "days": 90, "loading": False})
    monkeypatch.setattr("stockskill.data.funds13f.holders_of", lambda t, cache_dir=None: [{"fund": "F"}])
    monkeypatch.setattr("stockskill.data.funds13f.warm_all", lambda cache_dir=None: None)
    c = create_app(tickers_path=str(tmp_path / "t.csv"), public=True).test_client()
    d = c.get("/api/congress?type=buy").get_json()
    assert d["total"] == 1 and d["trades"][0]["ticker"] == "NVDA" and d["most_bought"] == [["NVDA", 1]]
    assert c.get("/api/congress?chamber=Senate&member=roe").get_json()["total"] == 1
    h = c.get("/api/holders/NVDA").get_json()
    assert h["funds"] == [{"fund": "F"}] and len(h["congress"]) == 1
    assert len(c.get("/api/funds").get_json()["funds"]) >= 20
    assert "Politicians" in c.get("/trades?q=NVDA").get_data(as_text=True)


def test_refresh_failure_keeps_previous_trades(tmp_path, monkeypatch):
    import json
    import os
    from stockskill.data import congress as C
    d = C._dir(str(tmp_path))
    good = {"as_of": "2026-09-01T10:00", "days": 730, "trades": [{"ticker": "NVDA", "filed": "2026-08-30"}]}
    with open(os.path.join(d, "trades.json"), "w") as f:
        json.dump(good, f)

    def boom(*a):
        raise RuntimeError("offline")
    monkeypatch.setattr(C, "_house", boom)
    monkeypatch.setattr(C, "_senate", boom)
    monkeypatch.setattr(C, "_http", lambda: None)
    import stockskill.data.politicians as P
    monkeypatch.setattr(P, "trump_trades", lambda cache_dir=None: [{"ticker": "X", "filed": "2026-09-01"}])
    monkeypatch.setitem(C._STATE, "retry_after", 0)
    C._refresh(730, str(tmp_path))
    assert json.load(open(os.path.join(d, "trades.json"))) == good          # not overwritten
    assert "offline" in C._STATE["error"] and C._STATE["retry_after"] > 0
    C._STATE.update(error=None, retry_after=0)
