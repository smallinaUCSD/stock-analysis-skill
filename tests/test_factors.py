"""Factor engine: metric extraction, momentum, and cross-sectional scoring.

Hand-constructed universes with known orderings pin the math (percentile
orientation, missing-data handling, composite blend, labels).
"""

from stockskill.data.fundamentals import FundamentalSnapshot
from stockskill.factors.model import (
    factor_metrics, momentum_12_1, annualized_vol, score_factors, weights_from_env,
)


def _snap(ticker, **kw):
    return FundamentalSnapshot(ticker=ticker, as_of="2026-01-01", **kw)


def test_factor_metrics_yields():
    s = _snap("AAA", price=10.0, eps=1.0, fcf=200.0, market_cap=1000.0,
              net_debt=500.0, ebitda=300.0, revenue=800.0, dividend_annual=0.5,
              roe=0.25, profit_margin=0.2)
    m = factor_metrics(s, momentum=0.3)
    assert m["earnings_yield"] == 0.1                 # 1/10
    assert m["fcf_yield"] == 0.2                      # 200/1000
    assert m["ev_ebitda"] == (1000 + 500) / 300       # EV/EBITDA = 5.0
    assert m["sales_yield"] == 0.8                     # 800/1000
    assert m["dividend_yield"] == 0.05
    assert m["fcf_margin"] == 0.25                     # 200/800
    assert m["net_debt_to_ebitda"] == 500 / 300
    assert m["momentum"] == 0.3


def test_momentum_12_1_skips_recent_month():
    # 300 days rising 0->? ; recent(-21) / old(-252) - 1
    closes = [100.0 + i for i in range(300)]           # linear ramp
    m = momentum_12_1(closes)
    expected = closes[-21] / closes[-252] - 1.0
    assert abs(m - expected) < 1e-9
    assert momentum_12_1([1.0] * 50) is None           # too short -> None


def test_value_orientation_cheap_ranks_top():
    # CHEAP: high earnings/fcf/sales yield, LOW ev/ebitda -> should top value.
    cheap = factor_metrics(_snap("CHP", price=10, eps=2.0, fcf=300, market_cap=1000,
                                 net_debt=0, ebitda=500, revenue=1200))
    mid = factor_metrics(_snap("MID", price=10, eps=1.0, fcf=100, market_cap=1000,
                               net_debt=0, ebitda=250, revenue=600))
    rich = factor_metrics(_snap("RCH", price=10, eps=0.2, fcf=20, market_cap=1000,
                                net_debt=0, ebitda=80, revenue=200))
    ranked = {s.ticker: s for s in score_factors([cheap, mid, rich])}
    assert ranked["CHP"].factor_pct["value"] == 100    # cheapest
    assert ranked["RCH"].factor_pct["value"] == 0       # richest
    assert "cheap" in ranked["CHP"].label
    assert "expensive" in ranked["RCH"].label


def test_composite_and_ranking_order():
    strong = factor_metrics(_snap("STR", price=10, eps=2.0, fcf=300, market_cap=1000,
                                  net_debt=0, ebitda=500, revenue=1200,
                                  roe=0.4, profit_margin=0.3), momentum=0.5)
    weak = factor_metrics(_snap("WEK", price=10, eps=0.2, fcf=10, market_cap=1000,
                                net_debt=800, ebitda=80, revenue=200,
                                roe=0.02, profit_margin=0.01), momentum=-0.4)
    ranked = score_factors([strong, weak])
    assert ranked[0].ticker == "STR"                    # best composite first
    assert ranked[0].composite_pct == 100
    assert ranked[-1].ticker == "WEK"


def test_missing_data_excluded_not_guessed():
    # BLANK has no fundamentals at all -> value/quality None, low coverage.
    full = factor_metrics(_snap("FUL", price=10, eps=1.0, fcf=100, market_cap=1000,
                                net_debt=0, ebitda=200, revenue=500, roe=0.2,
                                profit_margin=0.15, revenue_growth=0.1), momentum=0.1,
                          volatility=0.3)
    blank = factor_metrics(_snap("BLK"), momentum=None)
    by_t = {s.ticker: s for s in score_factors([full, blank])}
    assert by_t["BLK"].factors["value"] is None
    assert by_t["BLK"].factors["momentum"] is None
    assert by_t["BLK"].coverage == 0.0
    assert by_t["FUL"].coverage > 0.9


def test_annualized_vol():
    # constant daily +1% -> zero dispersion -> ~0 vol
    steady = [100.0 * (1.01 ** i) for i in range(60)]
    assert annualized_vol(steady) < 1e-6
    assert annualized_vol([1.0] * 5) is None            # too thin


def test_low_coverage_name_withheld_from_composite():
    # A leveraged-ETF-like name: only momentum + volatility (price-based), no
    # fundamentals -> below the coverage floor -> composite withheld, but its
    # momentum score still ranks.
    lev = factor_metrics(_snap("LEV"), momentum=0.9, volatility=1.2)
    full = factor_metrics(_snap("FUL", price=10, eps=1.0, fcf=100, market_cap=1000,
                                net_debt=0, ebitda=200, revenue=500, roe=0.2,
                                profit_margin=0.15, revenue_growth=0.1,
                                earnings_growth=0.1, beta=1.0), momentum=0.1,
                          volatility=0.3)
    by_t = {s.ticker: s for s in score_factors([lev, full], min_coverage=0.5)}
    assert by_t["LEV"].composite_pct is None            # withheld
    assert by_t["LEV"].factor_pct["momentum"] is not None  # still scored on momentum
    assert by_t["FUL"].composite_pct is not None


def test_weights_from_env_override(monkeypatch):
    monkeypatch.setenv("STOCKSKILL_FACTOR_WEIGHTS", "value:3,growth:0,low_vol:0")
    w = weights_from_env()
    assert w["value"] == 3.0 and w["growth"] == 0.0 and w["quality"] == 1.0


def test_sector_neutral_flips_within_sector():
    # Energy names all have higher abs earnings-yield than Tech names, so GLOBAL
    # value ranks every Energy name above every Tech name. Sector-neutral instead
    # ranks each name against its own sector.
    def m(tk, sector, ey):
        return {"ticker": tk, "sector": sector, "earnings_yield": ey}
    rows = [m(f"E{i}", "Energy", 0.10 + i * 0.01) for i in range(5)] + \
           [m(f"T{i}", "Tech", 0.01 + i * 0.01) for i in range(5)]

    glob = {s.ticker: s for s in score_factors(rows, sector_neutral=False)}
    neut = {s.ticker: s for s in score_factors(rows, sector_neutral=True)}

    # T4 is the cheapest Tech name but globally cheaper-ranked than the richest
    # Energy name E0; sector-neutral flips that (T4 tops Tech, E0 bottoms Energy).
    assert glob["T4"].factor_pct["value"] < glob["E0"].factor_pct["value"]
    assert neut["T4"].factor_pct["value"] > neut["E0"].factor_pct["value"]


def test_sector_neutral_thin_sector_falls_back():
    # A lone name in its sector (< min_group) is ranked globally, not handed 50.
    def m(tk, sector, ey):
        return {"ticker": tk, "sector": sector, "earnings_yield": ey}
    rows = [m(f"B{i}", "Big", 0.05 + i * 0.01) for i in range(5)] + \
           [m("LONE", "Tiny", 0.20)]                      # richest overall, alone
    neut = {s.ticker: s for s in score_factors(rows, sector_neutral=True, min_group=4)}
    # LONE is ranked globally (not handed a degenerate mid-rank), so its overall
    # cheapness lands it in the top tier alongside the cheapest Big name.
    assert neut["LONE"].factor_pct["value"] > 50
    assert neut["LONE"].factor_pct["value"] >= neut["B4"].factor_pct["value"]
    assert neut["LONE"].factor_pct["value"] > neut["B0"].factor_pct["value"]
