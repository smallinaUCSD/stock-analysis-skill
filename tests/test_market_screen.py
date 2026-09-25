"""Market screener: Nasdaq listing parsing, SEC frame merging, metrics."""

from stockskill.data.market_screen import build_rows, compact, merge_frames, parse_listings


def _nasdaq():
    rows = [
        {"symbol": "AAA", "name": "Alpha Corp. Common Stock", "lastsale": "$50.00", "pctchange": "-1.50%",
         "marketCap": "5000000000.00", "volume": "1000", "sector": "Technology", "industry": "Software", "country": "United States"},
        {"symbol": "BRK/B", "name": "Berkshire Hathaway Inc. Class B Common Stock", "lastsale": "$500.00",
         "pctchange": "0.10%", "marketCap": "1000000000000", "volume": "5", "sector": "Finance", "industry": "", "country": ""},
        {"symbol": "AAAW", "name": "Alpha Corp. Warrants", "lastsale": "$0.10", "marketCap": "", "pctchange": ""},
        {"symbol": "BAC^K", "name": "Bank Preferred", "lastsale": "$25", "marketCap": "", "pctchange": ""},
        {"symbol": "ZZZ", "name": "No Price Inc.", "lastsale": "NA", "marketCap": "", "pctchange": ""},
    ]
    return {"data": {"rows": rows}}


def test_parse_listings_keeps_common_stock_only():
    ls = parse_listings(_nasdaq())
    assert [x["ticker"] for x in ls] == ["AAA", "BRK-B"]
    a = ls[0]
    assert a["name"] == "Alpha Corp." and a["price"] == 50.0 and a["mcap"] == 5e9 and a["chg"] == -0.015


def test_merge_frames_prefers_first_concept():
    frames = {"Revenues": [{"cik": 1, "val": 100, "end": "2025-12-31"}],
              "SalesRevenueNet": [{"cik": 1, "val": 999, "end": "2025-12-31"}, {"cik": 2, "val": 50, "end": "2025-06-30"}]}
    m = merge_frames(frames, {"revenue": ["Revenues", "SalesRevenueNet"]})
    assert m[1]["revenue"] == 100 and m[2]["revenue"] == 50 and m[2]["_end"] == "2025-06-30"


def test_build_rows_metrics():
    ls = parse_listings(_nasdaq())
    cur = {1: {"revenue": 1e9, "net_income": 2e8, "ocf": 3e8, "capex": 1e8, "equity": 1e9,
               "long_term_debt": 5e8, "cash": 2e8, "eps": 2.5, "gross_profit": 6e8, "_end": "2025-12-31"}}
    prev = {1: {"revenue": 8e8, "net_income": 1e8}}
    r = build_rows(ls, cur, prev, {"AAA": 1})
    a, b = r[0], r[1]
    assert abs(a["pe"] - 20.0) < 1e-9                  # price / EPS
    assert abs(a["ps"] - 5.0) < 1e-9 and abs(a["pb"] - 5.0) < 1e-9
    assert a["fcf"] == 2e8 and abs(a["fcf_yield"] - 0.04) < 1e-9
    assert abs(a["ev_sales"] - 5.3) < 1e-9             # (5B + 0.5B - 0.2B) / 1B
    assert abs(a["rev_growth"] - 0.25) < 1e-9 and abs(a["ni_growth"] - 1.0) < 1e-9
    assert abs(a["gross_margin"] - 0.6) < 1e-9 and abs(a["roe"] - 0.2) < 1e-9
    assert b["pe"] is None and b["revenue"] is None     # no SEC match -> blanks, still listed


def test_compact_is_column_oriented():
    c = compact([{"ticker": "AAA", "pe": 12.345678}])
    i = c["cols"].index("pe")
    assert c["data"][0][c["cols"].index("ticker")] == "AAA" and c["data"][0][i] == 12.3457


def test_screener_routes(tmp_path, monkeypatch):
    from stockskill.data import market_screen as M
    from stockskill.data import sec as SEC
    from stockskill.server import create_app
    c = create_app(tickers_path=str(tmp_path / "t.csv"), public=True).test_client()
    assert c.get("/screener").status_code == 200
    assert c.get("/api/screener").get_json()["ok"] is False        # no SEC access in tests
    monkeypatch.setattr(SEC, "has_sec", lambda: True)
    monkeypatch.setattr(M, "universe", lambda d, w: {"warming": True})
    assert c.get("/api/screener").get_json()["warming"] is True
    rows = build_rows(parse_listings(_nasdaq()), {}, {}, {})
    monkeypatch.setattr(M, "universe", lambda d, w: {"rows": rows, "year": 2025, "built": 1.0})
    d = c.get("/api/screener").get_json()
    assert d["ok"] and d["year"] == 2025 and len(d["table"]["data"]) == 2
