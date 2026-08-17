---
name: stock-analysis
description: >-
  Reproducible stock and portfolio analysis where all math runs in tested
  Python, never the model. Use when the user wants to value a stock ("what is
  X actually worth?", fair value, DCF, is it over/undervalued), review or
  stress-test a portfolio (concentration, true leverage, factor overlap),
  understand look-through exposure of leveraged/single-stock ETFs (FNGU, SOXL,
  AAPU, TSLL, etc.), or quantify leveraged-ETF volatility decay. Covers
  long-term quality/growth investing plus an aggressive leveraged sleeve.
---

# Stock Analysis

A skill for turning market data into reproducible, defensible analysis. The
core rule: **the model never does the math.** Every number comes from the
tested functions in the `stockskill` package. Claude's job is to gather inputs,
run the code, and interpret the output honestly.

## The one non-negotiable rule

Never compute valuations, returns, exposures, decay, or risk metrics in your
head or in prose. Always call the CLI or the library. If you catch yourself
about to state a number you didn't get from running the code, stop and run it.
The whole point of this skill is that results are reproducible: same inputs →
same numbers, provable by re-running.

## Boundaries (read before every session)

- **No personalized buy/sell/short advice.** Produce analysis, ranges, and
  trade-offs; the user decides and executes. Never tell the user to buy, sell,
  short, or size a specific position. You are not a licensed advisor — say so
  if asked for a recommendation.
- **Leveraged ETFs are not buy-and-hold.** Any time a leveraged product
  (registry hit, or a 2x/3x name) is discussed or valued, surface the decay
  risk and run the decay sim rather than assuming linear upside.
- **Snapshots and basket weights must be verified.** The leverage registry
  ships with dated snapshots flagged `verify=True`. Say so when you rely on
  them; refresh from issuer holdings when the analysis is high-stakes.
- **Data is best-effort.** Locally, free yfinance/Yahoo. The hosted app uses a
  data-provider seam (FMP stable API for fundamentals + Finnhub for live quotes,
  yfinance as fallback) because Yahoo blocks datacenter IPs. Free tiers can be
  delayed or gate some endpoints. Report the `as_of` date and any missing fields;
  never paper over a gap with a guessed number.

## Setup

The project is a uv package. Run everything through uv:

```bash
uv run stockskill --help
uv run pytest -q          # ~200 tests; run after any change to the math
```

## Commands (this is where the math lives)

### Value a stock — "what is it actually worth?"
Fetches fundamentals, runs DCF + reverse DCF + relative multiples + (for
payers) a dividend model, and reports a fair-value range, blended base, and
margin of safety. Recomputes from scratch every call.

```bash
uv run stockskill value NVDA --growth 0.15 --peer-pe 35 --peer-ev-ebitda 28 \
    --save nvda.json
uv run stockskill value --snapshot nvda.json   # reproduce offline, identical output
```

Always report the **reverse-DCF implied growth** — "the price implies ~X% FCF
growth for 10 years" is usually the most decision-useful line. Growth and peer
multiples are explicit, logged assumptions; state them, and vary them to show
sensitivity rather than presenting one number as truth.

### Look-through exposure — what you actually own
Collapses leveraged/basket ETFs into true underlying dollar exposure and
computes effective leverage. Reveals hidden overlap (a name living inside
several products at once).

```bash
uv run stockskill lookthrough --holdings holdings.csv
```

### Portfolio review
Look-through + concentration (HHI, effective number of bets, top-5 share) +
factor-group exposure + per-account breakdown.

```bash
uv run stockskill portfolio --holdings holdings.csv
```

### Leveraged decay
Quantifies volatility drag — either Monte Carlo (drift/vol assumptions) or by
replaying a real underlying's price path.

```bash
uv run stockskill decay --multiplier 3 --vol 0.45 --drift 0.08 --expense 0.0095
uv run stockskill decay --multiplier 2 --ticker TSLA --period 1y   # real path
```

### Screen — rank a universe into a shortlist (idea generation)
Scores every name in a universe cross-sectionally (percentile within the set)
under a lane preset, and ranks a shortlist. Two lanes: `core` (quality + value
+ growth) and `aggressive` (growth + momentum + beta). `--cache-dir` saves the
fetched snapshots so a screen is reproducible.

```bash
uv run stockskill screen --lane core --top 15 --cache-dir snaps
uv run stockskill screen --lane aggressive --momentum 1y --cache-dir snaps
```

Interpret honestly: scores are **relative ranks within that universe**, not
absolute buy signals — the top name is "best of this list," which is only as
good as the list. `coverage` shows how much of the scoring weight had data
(banks lack EBITDA metrics, etc.). Always run `value TICKER` on shortlisted
names for a real fair-value check before drawing conclusions.

### Factors — cross-sectional factor scores & backtest
Scores the watchlist on **value / quality / momentum / growth / low-vol** (each a
0–100 percentile within the universe) plus a coverage-gated composite and a
plain-English read. `--sector-neutral` ranks each metric *within sector* so
"cheap" means cheap-vs-peers, not a bet on cheap sectors. Value uses the same
fundamentals as `value`. Weights via `STOCKSKILL_FACTOR_WEIGHTS`.

```bash
uv run stockskill factors --sector-neutral --by value
uv run stockskill backtest                 # momentum: buckets, long-short spread, IC
uv run stockskill snapshot-fundamentals    # record today's fundamentals (run daily)
```

Interpret honestly, same discipline as `screen`: percentiles are **relative to
this universe**. A positive long-short spread with a **near-zero IC** and
non-monotonic buckets means the factor does *not* reliably sort returns here —
say that; don't sell the headline spread. Only **momentum** backtests today
(price-derived); value/quality need point-in-time fundamentals, which
`snapshot-fundamentals` accrues daily into `data/fundamentals_history/`. See
`references/factor-investing.md`.

### Pulse — what's trending and why
Reads the market from free ETF/macro data: sector rotation, factor/style
rotation, breadth, and a regime snapshot (VIX, yield curve, credit, leadership)
with rule-based flags. `--price-map` caches series for reproducibility.

```bash
uv run stockskill pulse --price-map pm.json
```

These are **computed facts, not signals** — no single number is a call. A
defensive lean is a *cluster* (rising VIX + inverted/flattening curve + narrow
breadth + credit risk-off + defensive leadership together). See
`references/regime-playbook.md`. The proprietary "why" (Morningstar/Barchart
analyst views) is a manual live read via the Claude-in-Chrome extension when
connected — deliberately not automated into the CLI.

### Dashboard — the visual view (+ scheduling)
Writes a self-contained, theme-aware HTML dashboard (pulse + portfolio) with a
market-status badge and self-refresh. Runs once, or loops with `--watch`.

```bash
uv run stockskill dashboard --open                 # generate + open
uv run stockskill dashboard --watch --interval 30  # live loop
./scripts/install_schedule.sh                       # cron: pre-open, every 30m, close (Mon-Fri)
```

The scheduler edits the user's crontab — a persistent change. Show them the
cadence and let them run the installer; don't modify crontab silently. See
`references/dashboard-and-scheduling.md`.

### Serve — interactive analyzer (search any ticker)
A local Flask app: search by company name or ticker (live dropdown resolves
"oracle" → ORCL) → live price, valuation signal, bear/base/bull fair value,
reverse-DCF implied growth, reported analyst consensus, and an options
snapshot. All math from the tested engine; base growth is data-driven
(reported revenue growth, clamped, overridable). FCF negative but earnings
positive (capex-heavy name like ORCL) → an earnings-based DCF proxy, flagged;
only a genuinely unprofitable name shows "no reliable fair-value basis" —
never invent a valuation.

```bash
uv run stockskill serve --open        # http://127.0.0.1:8787
```

**Boundary:** this emits *analysis*, never a personalized buy/sell/hold
instruction. The valuation signal (price vs. our DCF fair value) and the
reported analyst consensus are shown separately — they often disagree, and the
decision is the user's. Do not add a synthesized "recommended action" field.
See `references/stock-analyzer.md`.

## Holdings file

`holdings.csv`: `ticker,market_value,account`. Leveraged tickers are expanded
via the registry; everything else is treated as 1x exposure to itself. Lines
starting with `#` are comments. Keep market values current for the risk
numbers to mean anything.

## Extending

- New leveraged product → add to `src/stockskill/leverage/registry.py`.
- New factor/sector tag → `src/stockskill/config.py`.
- New screen lane / metric weights → `src/stockskill/screener/screen.py` (LANES).
- New factor / metric / weight → `src/stockskill/factors/model.py` (FACTORS, DEFAULT_WEIGHTS).
- New pulse sector/factor/regime ticker → `src/stockskill/pulse/universe.py`.
- New valuation method → add a pure function under `src/stockskill/valuation/`,
  wire it into `service.py`, and **add a test with a hand-checked value.**

## Reference material

- `references/valuation-methodology.md` — how each model works and when to
  trust it; the DDM-weight caveat for non-dividend payers.
- `references/leveraged-etf-rules.md` — decay mechanics and holding discipline.
- `references/portfolio-review-checklist.md` — what to look at and thresholds.
- `references/financial-red-flags.md` — accounting/quality warning signs.
- `references/screener-methodology.md` — how ranking, lanes, and coverage work.
- `references/factor-investing.md` — the factor formulas/weights, sector-neutral
  scoring, the backtest method, and the value-backtest data gap.
- `references/market-pulse.md` — what each pulse section means; the paid layer.
- `references/regime-playbook.md` — reading the macro regime; defensive rotation.
- `references/dashboard-and-scheduling.md` — the HTML dashboard and cron setup.
- `references/stock-analyzer.md` — the interactive `serve` app and its boundary.
