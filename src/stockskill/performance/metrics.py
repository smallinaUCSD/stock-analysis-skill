"""Risk and performance statistics of one price series against a benchmark.

Deterministic, dependency-light (plain Python + math). Inputs are aligned daily
closes; every function returns None when there isn't enough data rather than
inventing a number.

* Beta uses Welch (2022), "Simply Better Market Betas" (Critical Finance
  Review 11:37-64): winsorize each daily stock return to the band between
  -2x and +4x the same day's market return, then fit a weighted regression
  whose weights halve every ~4 months (84 trading days). It forecasts future
  beta better than plain OLS, Vasicek or vendor (Bloomberg/Yahoo) betas. For
  leveraged/inverse funds the band is re-centered on a first-pass beta (see
  ``welch_beta``).
* Alpha is Jensen's alpha from an OLS regression of daily excess returns on
  the benchmark's, annualized, with its t-statistic. Over a year alpha is
  usually statistically indistinguishable from zero, and the t-stat says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TRADING_DAYS = 252
WELCH_HALF_LIFE = 84.0          # trading days (~4 months)


def simple_returns(closes) -> list[float]:
    """Daily simple returns (oldest -> newest). Skips non-positive prices."""
    c = list(closes or [])
    return [b / a - 1.0 for a, b in zip(c[:-1], c[1:]) if a and a > 0 and b is not None]


def align_closes(dates_a, closes_a, dates_b, closes_b):
    """Keep only the dates both series share. Returns (dates, a, b), oldest first.

    Dates may be date objects or ISO strings (they're compared as ISO strings)."""
    def key(d):
        return d.isoformat() if hasattr(d, "isoformat") else str(d)
    mb = {key(d): c for d, c in zip(dates_b or [], closes_b or []) if c is not None}
    dates, a, b = [], [], []
    for d, c in zip(dates_a or [], closes_a or []):
        k = key(d)
        if c is not None and k in mb:
            dates.append(k)
            a.append(float(c))
            b.append(float(mb[k]))
    return dates, a, b


def _wls(y, x, w):
    """Weighted least squares y = a + b x. Returns (a, b) or None."""
    sw = sum(w)
    if sw <= 0:
        return None
    mx = sum(wi * xi for wi, xi in zip(w, x)) / sw
    my = sum(wi * yi for wi, yi in zip(w, y)) / sw
    sxx = sum(wi * (xi - mx) ** 2 for wi, xi in zip(w, x))
    if sxx <= 0:
        return None
    sxy = sum(wi * (xi - mx) * (yi - my) for wi, xi, yi in zip(w, x, y))
    b = sxy / sxx
    return my - b * mx, b


def welch_beta(r, m, half_life: float = WELCH_HALF_LIFE) -> float | None:
    """Welch's slope-winsorized, age-decayed beta of returns ``r`` on market ``m``.

    Each stock return is clipped to the band (c - 3)m .. (c + 3)m for that day
    (Welch: c = 1, i.e. -2m .. +4m), then regressed on the market with weights
    decaying by half every ``half_life`` days (the newest day weighs most).

    Welch's band assumes a beta roughly between -2 and 4. Leveraged and inverse
    funds sit outside it (a -3x fund would be clipped to about -2), so when a
    first-pass OLS beta is outside [-1, 3] the band is centered on it instead."""
    n = min(len(r), len(m))
    if n < 20:
        return None
    r, m = r[-n:], m[-n:]
    first = _wls(r, m, [1.0] * n)
    c = 1.0
    if first and not (-1.0 <= first[1] <= 3.0):
        c = first[1]
    y = []
    for ri, mi in zip(r, m):
        lo, hi = min((c - 3.0) * mi, (c + 3.0) * mi), max((c - 3.0) * mi, (c + 3.0) * mi)
        y.append(min(max(ri, lo), hi))
    k = math.log(2.0) / half_life
    w = [math.exp(-k * (n - 1 - i)) for i in range(n)]
    fit = _wls(y, m, w)
    return fit[1] if fit else None


def ols_fit(y, x):
    """OLS y = a + b x. Returns dict(alpha, beta, alpha_se, r2) or None."""
    n = min(len(y), len(x))
    if n < 20:
        return None
    y, x = y[-n:], x[-n:]
    fit = _wls(y, x, [1.0] * n)
    if not fit:
        return None
    a, b = fit
    mx = sum(x) / n
    my = sum(y) / n
    resid = [yi - a - b * xi for xi, yi in zip(x, y)]
    sse = sum(e * e for e in resid)
    sst = sum((yi - my) ** 2 for yi in y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    s2 = sse / (n - 2)
    alpha_se = math.sqrt(s2 * (1.0 / n + mx * mx / sxx)) if sxx > 0 else float("nan")
    return {"alpha": a, "beta": b, "alpha_se": alpha_se,
            "r2": (1.0 - sse / sst) if sst > 0 else None}


def jensen_alpha(r, m, rf_annual: float = 0.0):
    """Annualized Jensen's alpha of ``r`` vs ``m`` on daily excess returns.

    Returns dict(alpha, t, beta, r2) or None. ``alpha`` is per year (0.05 = 5%)."""
    rf = rf_annual / TRADING_DAYS
    fit = ols_fit([x - rf for x in r], [x - rf for x in m])
    if not fit:
        return None
    se = fit["alpha_se"]
    t = fit["alpha"] / se if se and se == se and se > 0 else None
    return {"alpha": fit["alpha"] * TRADING_DAYS, "t": t,
            "beta": fit["beta"], "r2": fit["r2"]}


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def annual_vol(r) -> float | None:
    if len(r) < 2:
        return None
    mu = _mean(r)
    return math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(TRADING_DAYS)


def sharpe(r, rf_annual: float = 0.0) -> float | None:
    """Annualized Sharpe ratio of daily returns."""
    vol = annual_vol(r)
    if not vol:
        return None
    return (_mean(r) * TRADING_DAYS - rf_annual) / vol


def sortino(r, rf_annual: float = 0.0) -> float | None:
    """Annualized Sortino ratio: excess return over downside deviation (target rf)."""
    if len(r) < 2:
        return None
    rf = rf_annual / TRADING_DAYS
    down = [min(0.0, x - rf) ** 2 for x in r]
    dd = math.sqrt(sum(down) / len(down)) * math.sqrt(TRADING_DAYS)
    if dd <= 0:
        return None
    return (_mean(r) * TRADING_DAYS - rf_annual) / dd


def drawdown_series(closes) -> list[float]:
    """Drawdown from the running peak at each point (0 at a new high, -0.3 = 30% off)."""
    out, peak = [], None
    for c in closes or []:
        peak = c if peak is None or c > peak else peak
        out.append(c / peak - 1.0 if peak else 0.0)
    return out


def max_drawdown(closes) -> float | None:
    dd = drawdown_series(closes)
    return min(dd) if len(dd) > 1 else None


def capture_ratios(r, m):
    """(up_capture, down_capture): the average daily return on up-market days
    divided by the market's average on those days, and likewise for down days.
    1.2 / 0.8 = rises 20% more than the market on its up days, falls 20% less."""
    up = [(ri, mi) for ri, mi in zip(r, m) if mi > 0]
    dn = [(ri, mi) for ri, mi in zip(r, m) if mi < 0]

    def ratio(pairs):
        if len(pairs) < 10:
            return None
        mm = _mean([p[1] for p in pairs])
        return _mean([p[0] for p in pairs]) / mm if mm else None
    return ratio(up), ratio(dn)


def correlation(a, b) -> float | None:
    n = min(len(a), len(b))
    if n < 20:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = _mean(a), _mean(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if sa <= 0 or sb <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def cagr(closes, days: int) -> float | None:
    """Compound annual growth over ``days`` trading days of closes."""
    if len(closes) < 2 or days <= 0 or not closes[0] or closes[0] <= 0:
        return None
    return (closes[-1] / closes[0]) ** (TRADING_DAYS / days) - 1.0


@dataclass
class RiskStats:
    benchmark: str
    window_days: int              # trading days actually used
    beta: float | None            # Welch slope-winsorized, age-decayed
    beta_ols: float | None
    alpha: float | None           # annualized Jensen's alpha
    alpha_t: float | None
    r2: float | None
    vol: float | None             # annualized volatility
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None
    up_capture: float | None
    down_capture: float | None
    correlation: float | None

    @property
    def alpha_significant(self) -> bool:
        return self.alpha_t is not None and abs(self.alpha_t) >= 2.0

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["alpha_significant"] = self.alpha_significant
        return d


def risk_stats(dates, closes, bench_dates, bench_closes, benchmark: str = "SPY",
               window: int = TRADING_DAYS, rf_annual: float = 0.043) -> RiskStats | None:
    """Risk profile of a price series vs a benchmark over the last ``window``
    shared trading days. None when fewer than ~60 shared days exist."""
    d, a, b = align_closes(dates, closes, bench_dates, bench_closes)
    a, b = a[-(window + 1):], b[-(window + 1):]
    if len(a) < 61:
        return None
    r, m = simple_returns(a), simple_returns(b)
    n = min(len(r), len(m))
    r, m = r[-n:], m[-n:]
    ja = jensen_alpha(r, m, rf_annual)
    up, down = capture_ratios(r, m)
    return RiskStats(
        benchmark=benchmark, window_days=n,
        beta=welch_beta(r, m), beta_ols=ja["beta"] if ja else None,
        alpha=ja["alpha"] if ja else None, alpha_t=ja["t"] if ja else None,
        r2=ja["r2"] if ja else None, vol=annual_vol(r),
        sharpe=sharpe(r, rf_annual), sortino=sortino(r, rf_annual),
        max_drawdown=max_drawdown(a), up_capture=up, down_capture=down,
        correlation=correlation(r, m))
