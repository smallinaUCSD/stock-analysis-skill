# Screener methodology

`stockskill screen` turns a universe into a ranked shortlist. The ranking math
(`screener/criteria.py`) is pure and unit-tested; the only judgement is which
metrics and weights each lane uses (`screener/screen.py`, `LANES`).

## How scoring works
1. For each metric, every name gets a **percentile rank** within the universe
   (0 = worst, 1 = best). Percentile ranking is used deliberately: it's robust
   to outliers and puts metrics on different scales onto common footing.
2. "Lower is better" metrics (EV/EBITDA, net debt/EBITDA) are inverted so 1
   always means "good."
3. The composite is a **weighted average over the metrics that are present**
   for that name. Missing data is excluded, and `coverage` reports the share of
   weight that had data.

## The two lanes
- **core** (quality + value + growth): fcf_yield, earnings_yield,
  EV/EBITDA (cheap), profit_margin, ROE, revenue_growth, low net_debt/EBITDA,
  dividend_yield. For the buy-and-hold sleeve.
- **aggressive** (growth + momentum + beta): revenue_growth, earnings_growth,
  price momentum, beta, with light quality (profit_margin, fcf_yield). For the
  high-octane satellite. Momentum needs `--momentum <period>`.

## Reading the output honestly
- Scores are **relative to this universe only.** The #1 name is "best of this
  list," which is only as good as the list you fed it. Screening a bucket of
  expensive names still returns a "top" pick.
- A score is a *filter to shortlist*, never a buy signal. Always run
  `value TICKER` on the shortlist to check absolute valuation, and the
  red-flags checklist for quality.
- Watch `coverage`: a high score built on 50% coverage (e.g. a bank missing
  EV/EBITDA) is less trustworthy than a fully-covered one.
- Free data is noisy. Growth/margin fields from yfinance can be stale or on
  different definitions across names; treat close scores as ties.

## Reproducibility
`--cache-dir` writes one snapshot JSON per name. Re-running with the same cache
(and without `--refresh`) reproduces the ranking exactly, with no network.
