"""Risk statistics vs a benchmark: known-answer checks for each function."""

import math
import random
from datetime import date, timedelta

import pytest

from stockskill.performance import metrics as M


def _market(n=300, seed=1):
    rnd = random.Random(seed)
    return [rnd.gauss(0.0004, 0.01) for _ in range(n)]


def _prices(rets, start=100.0):
    out = [start]
    for r in rets:
        out.append(out[-1] * (1 + r))
    return out


def test_exact_multiple_of_market_has_that_beta_and_zero_alpha():
    m = _market()
    r = [1.5 * x for x in m]                    # inside the -2x..+4x band: no clipping
    assert M.welch_beta(r, m) == pytest.approx(1.5, abs=1e-9)
    ja = M.jensen_alpha(r, m, rf_annual=0.0)
    assert ja["beta"] == pytest.approx(1.5, abs=1e-9)
    assert ja["alpha"] == pytest.approx(0.0, abs=1e-9)
    assert ja["r2"] == pytest.approx(1.0)
    # with a risk-free rate, r - rf = 1.5 (m - rf) + 0.5 rf  ->  alpha = 0.5 rf per year
    assert M.jensen_alpha(r, m, rf_annual=0.04)["alpha"] == pytest.approx(0.02, abs=1e-9)


def test_welch_beta_clips_outlier_days_ols_does_not():
    m = _market()
    r = list(m)                                 # true beta 1
    for i in (50, 150, 250):
        r[i] = 0.40 if m[i] > 0 else -0.40      # three freak jump days
    ols = M.ols_fit(r, m)["beta"]
    welch = M.welch_beta(r, m)
    assert abs(welch - 1.0) < abs(ols - 1.0)
    assert abs(welch - 1.0) < 0.25


def test_welch_beta_handles_leveraged_and_inverse_funds():
    m = _market()
    assert M.welch_beta([-3 * x for x in m], m) == pytest.approx(-3.0, abs=1e-9)
    assert M.welch_beta([5 * x for x in m], m) == pytest.approx(5.0, abs=1e-9)
    assert M.welch_beta([-1 * x for x in m], m) == pytest.approx(-1.0, abs=1e-9)


def test_welch_beta_weights_recent_days_more():
    m = _market(400)
    r = [0.5 * x for x in m[:200]] + [2.0 * x for x in m[200:]]   # beta rose 0.5 -> 2
    assert M.welch_beta(r, m) > M.ols_fit(r, m)["beta"]
    assert M.welch_beta(r, m) > 1.5


def test_alpha_t_stat_flags_noise_vs_real_edge():
    m = _market(252)
    rnd = random.Random(7)
    noisy = [x + rnd.gauss(0, 0.01) for x in m]
    assert abs(M.jensen_alpha(noisy, m)["t"]) < 2          # a year of noise: not significant
    edge = [x + 0.002 for x in m]                           # +0.2%/day, no noise
    assert M.jensen_alpha(edge, m)["alpha"] == pytest.approx(0.002 * 252, rel=1e-6)


def test_drawdown_and_max_drawdown():
    assert M.drawdown_series([100, 120, 90, 130]) == pytest.approx([0, 0, -0.25, 0])
    assert M.max_drawdown([100, 120, 90, 130]) == pytest.approx(-0.25)
    assert M.max_drawdown([100]) is None


def test_sharpe_sortino_and_degenerate_inputs():
    assert M.sharpe([0.001] * 50) is None                  # zero volatility
    assert M.sortino([0.01] * 50) is None                  # no downside at all
    r = _market(252)
    s = M.sharpe(r, 0.0)
    mu, vol = sum(r) / len(r) * 252, M.annual_vol(r)
    assert s == pytest.approx(mu / vol)
    assert M.sortino(r) is not None


def test_capture_ratios_and_correlation():
    m = _market()
    up, down = M.capture_ratios([2 * x for x in m], m)
    assert up == pytest.approx(2.0) and down == pytest.approx(2.0)
    assert M.correlation([2 * x for x in m], m) == pytest.approx(1.0)
    assert M.correlation([-x for x in m], m) == pytest.approx(-1.0)


def test_cagr():
    assert M.cagr([100, 121], 504) == pytest.approx(0.10)
    assert M.cagr([100], 252) is None


def test_align_closes_keeps_shared_dates_only():
    d0 = date(2026, 1, 1)
    da = [d0 + timedelta(days=i) for i in range(5)]
    db = [d.isoformat() for d in da[1:]] + ["2026-02-01"]
    dates, a, b = M.align_closes(da, [1, 2, 3, 4, 5], db, [10, 20, 30, 40, 99])
    assert dates == [d.isoformat() for d in da[1:]]
    assert a == [2, 3, 4, 5] and b == [10, 20, 30, 40]


def test_risk_stats_end_to_end_and_too_short():
    m = _market(300)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(301)]
    mk = _prices(m)
    st = _prices([1.2 * x for x in m])
    rs = M.risk_stats(dates, st, dates, mk, benchmark="SPY")
    assert rs.window_days == 252
    assert rs.beta == pytest.approx(1.2, abs=1e-9)
    assert rs.correlation == pytest.approx(1.0)
    assert rs.max_drawdown <= 0
    assert not rs.alpha_significant or abs(rs.alpha_t) >= 2
    d = rs.to_dict()
    assert d["benchmark"] == "SPY" and "alpha_significant" in d
    assert M.risk_stats(dates[:40], st[:40], dates[:40], mk[:40]) is None
    assert not math.isnan(rs.vol)


# ---------------------------------------------------------------- compare
from stockskill.performance import compare as C


def _series(rets, start=date(2021, 1, 4), p0=100.0):
    closes = _prices(rets, p0)
    return {"dates": [start + timedelta(days=i) for i in range(len(closes))], "closes": closes}


def test_trailing_returns_windows_and_annualization():
    closes = [100.0 * (1.001 ** i) for i in range(1300)]
    dates = [date(2021, 1, 1) + timedelta(days=i) for i in range(1300)]
    tr = C.trailing_returns(dates, closes)
    assert tr["1M"] == pytest.approx(1.001 ** 21 - 1)
    assert tr["1Y"] == pytest.approx(1.001 ** 252 - 1)
    assert tr["5Y"] == pytest.approx(1.001 ** 252 - 1)      # annualized = the 1y rate
    assert C.trailing_returns(dates[:100], closes[:100])["1Y"] is None


def test_ytd_uses_last_close_of_prior_year():
    dates = [date(2025, 12, 30), date(2025, 12, 31), date(2026, 1, 2), date(2026, 3, 1)]
    assert C._ytd(dates, [90, 100, 101, 110]) == pytest.approx(0.10)
    assert C._ytd(dates[2:], [101, 110]) is None


def test_compare_aligns_to_common_history_and_scores_each_ticker():
    m = _market(600)
    spy = _series(m)
    lev = _series([3 * x for x in m])
    young = _series([2 * x for x in m[200:]], start=date(2021, 1, 4) + timedelta(days=200))
    out = C.compare({"SPY": spy, "LEV": lev, "NEW": young}, period="max",
                    bench=spy, bench_name="SPY")
    assert out["ok"] and out["limited_by"] == "NEW"
    assert out["start"] == young["dates"][0].isoformat()
    rows = {r["ticker"]: r for r in out["rows"]}
    assert rows["LEV"]["growth"][0] == 10000.0
    assert rows["LEV"]["beta"] == pytest.approx(3.0, abs=1e-6)
    assert rows["SPY"]["beta"] == 1.0
    assert rows["LEV"]["max_drawdown"] <= rows["SPY"]["max_drawdown"]
    assert out["correlation"][0][1] == pytest.approx(1.0)
    assert len(out["dates"]) == len(rows["LEV"]["growth"]) == len(rows["LEV"]["drawdown"])


def test_compare_period_cap_and_too_little_history():
    m = _market(600)
    out = C.compare({"A": _series(m), "B": _series(m)}, period="1y")
    assert out["days"] == 252 and out["limited_by"] is None
    same = C.compare({"A": _series(m), "B": _series(m[:300])}, period="max")
    assert same["limited_by"] is None               # same start, one just ends earlier
    short = C.compare({"A": _series(m[:10]), "B": _series(m[:10])})
    assert not short["ok"]


def test_sample_idx_keeps_ends():
    idx = C._sample_idx(1000, 100)
    assert idx[0] == 0 and idx[-1] == 999 and len(idx) <= 101
    assert C._sample_idx(5) == [0, 1, 2, 3, 4]


def test_holdings_overlap_is_sum_of_min_weights():
    w = {"QQQ": {"AAPL": 0.09, "MSFT": 0.08, "NVDA": 0.08},
         "FNGU": {"AAPL": 0.10, "NVDA": 0.10, "META": 0.10},
         "AAPL": {"AAPL": 1.0}}
    ov = C.holdings_overlap(w)
    assert ov[0][1] == pytest.approx(0.09 + 0.08) and ov[1][0] == ov[0][1]
    assert ov[0][2] == pytest.approx(0.09)          # AAPL's weight inside QQQ
    assert ov[2][2] == 1.0


def test_board_rows_get_welch_beta_and_risk_block():
    from types import SimpleNamespace
    from stockskill.watchlist.build import _attach_risk
    from stockskill.watchlist.render import _risk_summary
    m = _market(300)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(301)]
    spy = SimpleNamespace(ticker="SPY", ohlcv={"dates": dates, "close": _prices(m)})
    stk = SimpleNamespace(ticker="XYZ", ohlcv={"dates": dates, "close": _prices([1.3 * x for x in m])})
    from stockskill.performance.benchmarks import risk_vs_benchmarks
    row = SimpleNamespace(ticker="XYZ", beta=0.9, risk={})
    _attach_risk([row], {"XYZ": risk_vs_benchmarks(stk, {"SPY": spy})})
    assert row.beta == pytest.approx(1.3, abs=1e-9)          # vendor beta replaced
    html = _risk_summary(row)
    assert "Risk vs the market" in html and "1.30" in html
    assert _risk_summary(SimpleNamespace(risk={})) == ""


def test_dcf_discounts_with_the_measured_beta_when_given():
    from stockskill.analyze import analyze_ticker
    from stockskill.data.fundamentals import FundamentalSnapshot
    snap = FundamentalSnapshot(ticker="XYZ", as_of="2026-09-23", price=100.0, shares=1e9,
                               fcf=5e9, eps=5.0, beta=1.0, revenue_growth=0.08, name="XYZ")
    vendor = analyze_ticker("XYZ", snapshot=snap, with_options=False)["valuation"]
    welch = analyze_ticker("XYZ", snapshot=snap, with_options=False, beta=2.0)["valuation"]
    assert vendor["beta_source"] == "vendor" and vendor["beta_used"] == 1.0
    assert welch["beta_source"].startswith("Welch") and welch["beta_used"] == 2.0
    assert welch["discount_rate"] == pytest.approx(0.043 + 2.0 * 0.05)
    assert welch["base"] < vendor["base"]            # riskier -> higher rate -> lower value
