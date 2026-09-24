import pytest

from stockskill.data.politicians import _parse_date, _std_amount, match_member, parse_278t_line, ticker_for
from stockskill.signals import politician as P


def test_278t_rows_survive_ocr_noise():
    r = parse_278t_line("49 COMCAST CORP CL A lcurchaso 7/17/2026 No $15 001 -$50,000", "2026-09-08")
    assert r["type"] == "Buy" and r["traded"] == "2026-07-17" and (r["amount_low"], r["amount_high"]) == (15001, 50000)
    r2 = parse_278t_line("84 MOLINA HEALTHCARE INC salo 7/23/2026 No $1 001 • $15 000", "2026-09-08")
    assert r2["type"] == "Sell" and r2["amount_high"] == 15000
    r3 = parse_278t_line("51 INSMED INC PAR $.01 I Purchase 7/17/2026 No $15 001 - $50 000", "2026-09-08")
    assert r3["asset"].startswith("INSMED") and r3["amount_low"] == 15001
    r4 = parse_278t_line("4 MAIN STR GA GAS SPLY REV SER A B/E 4.00 % Due Jul 1, 2052 l ourchaso 7/812026 Vos "
                         "$1 000 001 - $5 000 000", "2026-09-08")
    assert r4["asset_type"] == "Bond" and r4["traded"] == "2026-07-08" and r4["amount_low"] == 1000001
    r5 = parse_278t_line("204 BLACKROCK INC NEW I ourchaso 7/31/2026 no $100 001 -$250 ODO", "2026-09-08")
    assert r5 and r5["amount_high"] == 250000
    assert parse_278t_line("Page 02 of 37", "2026-09-08") is None


def test_amount_and_date_helpers():
    assert _std_amount("$1 000 001 - $5 000 000") == (1000001, 5000000)
    assert _std_amount("$15 001-$50000") == (15001, 50000)
    assert _parse_date(["7/10/2026"], "2026-09-08") == "2026-07-10"
    assert _parse_date(["7/22/20", "26"], "2026-09-08") == "2026-07-22"


def test_ticker_for_fuzzy_names():
    idx = {"NETFLIX": "NFLX", "DATADOG": "DDOG", "COMCAST": "CMCSA"}
    assert ticker_for("NETFLIXINC", idx) == "NFLX"
    assert ticker_for("COMCAST CORP CL A", idx) == "CMCSA"
    assert ticker_for("OATADOG INC CL A", idx) == "DDOG"


def test_match_member_by_last_name_state_and_first():
    members = [{"id": "A1", "first": "Richard", "last": "Allen", "nickname": "Rick", "chamber": "House", "state": "GA"},
               {"id": "A2", "first": "Josh", "last": "Allen", "nickname": "", "chamber": "House", "state": "OH"},
               {"id": "M1", "first": "Mitch", "last": "McConnell", "nickname": "", "chamber": "Senate", "state": "KY"}]
    assert match_member("Richard W. Allen", "House", "GA12", members)["id"] == "A1"
    assert match_member("A. Mitchell McConnell, Jr.", "Senate", "", members)["id"] == "M1"


def _t(tk, kind, d, lo=15001, hi=50000, filed=None):
    return {"ticker": tk, "type": kind, "traded": d, "filed": filed or d, "amount_low": lo, "amount_high": hi,
            "owner": "Self", "asset": tk}


def test_stats_positions_and_lag():
    tr = [_t("AAA", "Buy", "2026-01-05", filed="2026-03-01"), _t("AAA", "Sell (partial)", "2026-02-01"),
          _t("BBB", "Buy", "2026-01-10"), _t("BBB", "Sell", "2026-03-01"), _t("CCC", "Buy", "2026-04-01")]
    s = P.stats(tr)
    assert s["buys"] == 3 and s["sells"] == 2 and s["late"] == 1
    pos = {p["ticker"]: p for p in P.positions(tr)}
    assert pos["BBB"]["open"] is False and pos["CCC"]["open"] and pos["AAA"]["cost"] == 0.0


def test_simulate_tracks_value_vs_benchmark():
    dates = [f"2026-01-{d:02d}" for d in range(1, 29)]
    up = [100 + i for i in range(28)]          # the stock rises 1/day
    flat = [100.0] * 28                          # the benchmark doesn't move
    sim = P.simulate([_t("AAA", "Buy", "2026-01-01", 10000, 10000)], {"AAA": (dates, up)}, (dates, flat), step=1)
    s = sim["summary"]
    assert s["invested"] == pytest.approx(10000) and s["gain"] == pytest.approx(127 / 100 - 1)
    assert s["bench_gain"] == pytest.approx(0.0)
    assert P.simulate([], {}, (dates, flat)) is None


def test_committee_overlap():
    tr = [_t("LMT", "Buy", "2026-01-01"), _t("AAPL", "Buy", "2026-01-01")]
    out = P.committee_overlap(tr, [{"name": "Committee on Armed Services"}],
                              {"LMT": "Industrials", "AAPL": "Technology"})
    assert [t["ticker"] for t in out] == ["LMT"]
