"""Factor backtest: bucketing, IC, and the momentum panel (no look-ahead)."""

from datetime import date, timedelta

from stockskill.factors.backtest import (
    bucket_returns, spearman, momentum_panel, run_backtest, _month_ends, _asof,
)


def test_asof_returns_last_on_or_before():
    dates = [date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 5)]
    closes = [10.0, 11.0, 12.0]
    assert _asof(dates, closes, date(2024, 1, 4)) == 11.0    # on-or-before
    assert _asof(dates, closes, date(2024, 1, 5)) == 12.0
    assert _asof(dates, closes, date(2023, 12, 31)) is None  # before history


def test_month_ends():
    me = _month_ends(date(2024, 1, 15), date(2024, 4, 10))
    assert me == [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)]


def test_spearman_monotonic():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) > 0.99   # perfectly monotone
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) < -0.99


def test_bucket_returns_sorts_and_spreads():
    # signal perfectly predicts forward return -> top bucket beats bottom, IC ~1
    signals = {f"T{i}": float(i) for i in range(10)}
    fwd = {f"T{i}": float(i) / 100 for i in range(10)}
    r = bucket_returns(signals, fwd, n_buckets=5)
    assert r["buckets"] == sorted(r["buckets"])              # monotonic gradient
    assert r["long_short"] > 0
    assert r["ic"] > 0.99


def test_bucket_returns_too_thin():
    assert bucket_returns({"A": 1.0}, {"A": 0.1}, n_buckets=5) is None


def _ramp(start_price, daily, n, start=date(2021, 1, 1)):
    dates = [start + timedelta(days=i) for i in range(n)]
    closes = [start_price * (1 + daily) ** i for i in range(n)]
    return dates, closes


def test_momentum_backtest_end_to_end():
    # 12 names with monotonically different drifts: higher-momentum names keep
    # winning, so the long-short spread and IC should be clearly positive.
    price_data = {}
    for i in range(12):
        price_data[f"T{i}"] = _ramp(100.0, 0.0002 * (i + 1), 900)
    sig, fwd = momentum_panel(price_data)
    assert sig and fwd
    res = run_backtest(sig, fwd, n_buckets=4)
    assert res is not None and res.n_periods > 6
    assert res.long_short_avg > 0            # momentum sorts forward returns
    assert res.ic_avg is not None and res.ic_avg > 0
    assert res.bucket_avg[-1] > res.bucket_avg[0]
