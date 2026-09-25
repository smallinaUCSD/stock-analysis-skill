"""Financial statements from XBRL: split adjustment, derived lines, ratios."""

from stockskill.data.financials import (_clean_ratio, build_statements, cagr, derive,
                                         split_adjust, split_events)


def _fact(val, end, filed, start=None, form="10-K"):
    f = {"val": val, "end": end, "filed": filed, "form": form, "fy": int(end[:4])}
    if start:
        f["start"] = start
    return f


def _facts():
    # a 10-for-1 split between the 2023 and 2024 annual reports: the 2024
    # report restates FY2022/FY2023 shares x10 and EPS /10
    yrs = [("2021-01-01", "2021-12-31"), ("2022-01-01", "2022-12-31"),
           ("2023-01-01", "2023-12-31"), ("2024-01-01", "2024-12-31")]
    rev = [_fact(v, e, f"{e[:4]}-02-15".replace(e[:4], str(int(e[:4]) + 1)), s)
           for (s, e), v in zip(yrs, [100e9, 120e9, 150e9, 200e9])]
    ni = [_fact(v, e, f"{int(e[:4]) + 1}-02-15", s) for (s, e), v in zip(yrs, [10e9, 12e9, 15e9, 30e9])]
    sh = [_fact(1e9, "2021-12-31", "2022-02-15", "2021-01-01"),
          _fact(1e9, "2022-12-31", "2023-02-15", "2022-01-01"),
          _fact(1e9, "2023-12-31", "2024-02-15", "2023-01-01"),
          _fact(10e9, "2022-12-31", "2025-02-15", "2022-01-01"),
          _fact(10e9, "2023-12-31", "2025-02-15", "2023-01-01"),
          _fact(10e9, "2024-12-31", "2025-02-15", "2024-01-01")]
    eps = [_fact(10.0, "2021-12-31", "2022-02-15", "2021-01-01"),
           _fact(12.0, "2022-12-31", "2023-02-15", "2022-01-01"),
           _fact(15.0, "2023-12-31", "2024-02-15", "2023-01-01"),
           _fact(1.2, "2022-12-31", "2025-02-15", "2022-01-01"),
           _fact(1.5, "2023-12-31", "2025-02-15", "2023-01-01"),
           _fact(3.0, "2024-12-31", "2025-02-15", "2024-01-01")]
    ocf = [_fact(v, e, f"{int(e[:4]) + 1}-02-15", s) for (s, e), v in zip(yrs, [20e9, 25e9, 30e9, 40e9])]
    capex = [_fact(v, e, f"{int(e[:4]) + 1}-02-15", s) for (s, e), v in zip(yrs, [5e9, 5e9, 6e9, 8e9])]
    eq = [_fact(v, e, f"{int(e[:4]) + 1}-02-15") for (_, e), v in zip(yrs, [50e9, 60e9, 70e9, 90e9])]
    return {"entityName": "Test Co", "facts": {"us-gaap": {
        "Revenues": {"units": {"USD": rev}},
        "NetIncomeLoss": {"units": {"USD": ni}},
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": sh}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": eps}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": ocf}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": capex}},
        "StockholdersEquity": {"units": {"USD": eq}},
    }}}


def test_clean_ratio_snaps_to_split_ratios():
    assert _clean_ratio(10.02) == 10
    assert _clean_ratio(0.2) == 0.2          # 1-for-5 reverse split
    assert _clean_ratio(1.07) is None        # ordinary restatement, not a split


def test_split_events_found_once_from_restatements():
    ev = split_events(_facts())
    assert ev == [("2025-02-15", 10.0)]


def test_statements_are_split_adjusted():
    d = build_statements(_facts())
    ys = d["years"]
    assert [y["end"][:4] for y in ys] == ["2021", "2022", "2023", "2024"]
    # FY2021 was only ever filed pre-split: shares x10, EPS /10
    assert ys[0]["shares"] == 10e9 and abs(ys[0]["eps"] - 1.0) < 1e-9
    assert [round(y["eps"], 2) for y in ys] == [1.0, 1.2, 1.5, 3.0]
    assert d["splits"] == [{"filed": "2025-02-15", "ratio": 10.0}]


def test_derived_lines_and_ratios():
    d = build_statements(_facts())
    last = d["years"][-1]
    assert last["fcf"] == 32e9
    assert abs(last["net_margin"] - 0.15) < 1e-9
    assert abs(last["rev_growth"] - (200 / 150 - 1)) < 1e-9
    assert abs(last["roe"] - 30e9 / 80e9) < 1e-9          # average equity
    assert abs(last["eps_growth"] - 1.0) < 1e-9           # split-adjusted 1.5 -> 3.0
    assert abs(d["cagr"]["revenue"][3] - (2 ** (1 / 3) - 1)) < 1e-9


def test_split_adjust_leaves_post_split_values():
    rows = [{"end": "2024-12-31", "shares": 5e9, "_f_shares": "2025-03-01", "eps": 2.0, "_f_eps": "2025-03-01"}]
    assert split_adjust(rows, [("2025-02-15", 10.0)])[0]["eps"] == 2.0


def test_derive_fills_gross_profit_and_liabilities():
    r = derive([{"end": "2024-12-31", "revenue": 100.0, "cost_of_revenue": 60.0,
                 "liab_and_equity": 500.0, "equity": 200.0}])[0]
    assert r["gross_profit"] == 40.0 and r["gross_margin"] == 0.4
    assert r["total_liabilities"] == 300.0 and "liab_and_equity" not in r


def test_cagr_needs_positive_endpoints():
    rows = [{"x": -1.0}, {"x": 2.0}, {"x": 4.0}]
    assert cagr(rows, "x", 2) is None
    assert abs(cagr(rows, "x", 1) - 1.0) < 1e-9


def test_financials_routes(tmp_path, monkeypatch):
    from stockskill.data import financials as FIN
    from stockskill.data import sec as SEC
    from stockskill.server import create_app
    c = create_app(tickers_path=str(tmp_path / "t.csv"), public=True).test_client()
    page = c.get("/financials?t=nvda")
    assert page.status_code == 200 and b'"NVDA"' in page.data
    assert c.get("/api/financials/../x").status_code in (400, 404)
    # no SEC_USER_AGENT in tests: a clear message, not an error
    assert c.get("/api/financials/NVDA").get_json()["ok"] is False
    monkeypatch.setattr(SEC, "has_sec", lambda: True)
    monkeypatch.setattr(FIN, "statements", lambda t, d=None: {"cik": 1, **build_statements(_facts())})
    d = c.get("/api/financials/TEST").get_json()
    assert d["ok"] and d["name"] == "Test Co" and len(d["years"]) == 4
    assert set(d["layout"]) == {"income", "balance", "cashflow", "ratios"}
