"""SEC extraction, normalized inputs, peers, and the point-in-time backtest."""

from types import SimpleNamespace

import pytest

from stockskill.data.sec import extract_annual
from stockskill.valuation import backtest as BT
from stockskill.valuation.normalize import normalized_cash_flow, owner_cash_flow, revenue_cagr
from stockskill.valuation.peers import group_of, multiples_of, peer_context


def _fact(end, val, filed, start=None, form="10-K"):
    f = {"end": end, "val": val, "filed": filed, "form": form, "fp": "FY", "fy": int(end[:4])}
    if start:
        f["start"] = start
    return f


def _facts():
    def yr(y, rev, ocf, capex, sbc, filed):
        s, e = f"{y}-01-01", f"{y}-12-31"
        return {"Revenues": _fact(e, rev, filed, s), "Ocf": _fact(e, ocf, filed, s),
                "Capex": _fact(e, capex, filed, s), "Sbc": _fact(e, sbc, filed, s)}
    rows = [yr(2023, 100, 30, 10, 5, "2024-02-01"), yr(2024, 110, 33, 11, 5, "2025-02-01"),
            yr(2025, 121, 36, 12, 6, "2026-02-01")]
    # a later 10-K restates 2024 revenue (the restatement should win, first filed date kept)
    restated = _fact("2024-12-31", 111, "2026-02-01", "2024-01-01")
    return {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [r["Revenues"] for r in rows] + [restated]}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [r["Ocf"] for r in rows]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [r["Capex"] for r in rows]}},
        "ShareBasedCompensation": {"units": {"USD": [r["Sbc"] for r in rows]
                                             + [_fact("2025-06-30", 99, "2025-08-01", "2025-04-01", "10-Q")]}},
        "Assets": {"units": {"USD": [_fact("2025-12-31", 500, "2026-02-01")]}},
    }}}


def test_extract_annual_takes_restatements_and_first_filed_date():
    ys = extract_annual(_facts())
    assert [y["end"] for y in ys] == ["2023-12-31", "2024-12-31", "2025-12-31"]
    y24 = ys[1]
    assert y24["revenue"] == 111 and y24["filed"] == "2025-02-01"
    assert ys[2]["sbc"] == 6 and ys[2]["total_assets"] == 500     # quarterly SBC ignored
    assert extract_annual({}) == []


def test_normalized_cash_flow_and_cagr():
    ys = extract_annual(_facts())
    assert owner_cash_flow(ys[0]) == 30 - 10 - 5
    n = normalized_cash_flow(ys, 3)
    assert n["value"] == pytest.approx(((30 - 10 - 5) + (33 - 11 - 5) + (36 - 12 - 6)) / 3)
    assert revenue_cagr(ys, 2) == pytest.approx((121 / 100) ** 0.5 - 1)
    # point in time: as of mid-2025 only FY2023 and FY2024 were public
    assert normalized_cash_flow(ys, 3, asof="2025-06-01")["years"] == [("2023-12-31", 15), ("2024-12-31", 17)]
    assert revenue_cagr(ys[:1], 3) is None


def _snap(price, eps, mc, nd, ebitda, rev):
    return SimpleNamespace(price=price, eps=eps, market_cap=mc, net_debt=nd, ebitda=ebitda, revenue=rev)


def test_peer_groups_multiples_and_relevered_beta():
    sics = {"A": "3674", "B": "3674", "C": "3674", "D": "3672", "E": "7372", "F": "3711"}
    assert group_of("A", sics)[1] == "3674" and group_of("D", sics)[1] == "367"
    assert group_of("E", sics) == ([], None)
    assert group_of("F", {**sics, "G": "3721", "H": "3760"}) == ([], None)   # no 2-digit lumping
    snaps = {t: _snap(100, 5, 1000, 0, 100, 500) for t in "ABCD"}
    snaps["A"] = _snap(100, 5, 1000, 500, 100, 500)          # A carries debt
    assert multiples_of(snaps["B"]) == {"pe": 20, "ev_ebitda": 10, "ps": 2}
    ctx = peer_context("A", sics, snaps, {"A": 1.5, "B": 1.2, "C": 1.2, "D": 1.2})
    assert ctx["peers"] == ["B", "C"] and ctx["pe"] == 20
    unlev_a = 1.5 / (1 + 0.79 * 0.5)
    med = sorted([unlev_a, 1.2, 1.2])[1]
    assert ctx["beta"] == pytest.approx(med * (1 + 0.79 * 0.5))


def test_backtest_evaluate_ranks_cheap_vs_rich():
    obs = [{"ticker": f"T{i}", "cohort": "2024", "gap": g, "fwd": g / 10} for i, g in enumerate(range(-6, 6))]
    ev = BT.evaluate(obs)
    assert ev["ic"] == pytest.approx(1.0) and ev["spread"] > 0 and ev["hit"] == 1.0
    assert BT.evaluate(obs[:5]) is None
