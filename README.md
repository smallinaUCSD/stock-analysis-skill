# stock-analysis-skill

A reproducible stock-analysis toolkit and dashboard for Claude. **The model
never does the math** — every number is produced by tested Python in the
`stockskill` package. Same inputs → same output, provable by re-running.

It combines what most tools keep separate:
- **Fundamental depth** — DCF valuation, portfolio look-through leverage, risk.
- **Factor investing** — cross-sectional value / quality / momentum / growth /
  low-vol scoring (sector-neutral), grounded in the research, with a backtest.
- **Technical breadth** — 30+ indicators, trading signals, alerts, trade setups,
  a market-pulse radar, and Monte Carlo simulation.
- **One live web app** (`serve`) — a multi-view watchlist board with a real-time
  price feed and factor scores, a per-account holdings dashboard, and every
  analysis tool reachable as a pop-up. Deployable as a **public, free web app**.

See [SKILL.md](SKILL.md) for how Claude uses this, [`references/`](references/)
for methodology (incl. [factor investing](references/factor-investing.md)),
[DEPLOYMENT.md](DEPLOYMENT.md) for the public deploy, and [ROADMAP.md](ROADMAP.md)
for what's built and next.

## Quickstart

```bash
uv run pytest -q                              # the tested math (~200 tests)

# the live app — this is the main way to use it
uv run stockskill serve --open                # live dashboard: watchlist board + holdings + tools

# analysis (CLI)
uv run stockskill value NVDA --growth 0.15    # fair value: DCF + reverse DCF + multiples
uv run stockskill factors --sector-neutral    # rank the board on value/quality/momentum/growth/low-vol
uv run stockskill backtest                     # backtest momentum: buckets, long-short spread, IC
uv run stockskill screen --lane core          # rank a universe into a shortlist
uv run stockskill pulse                        # market pulse: sectors, breadth, regime, sentiment
uv run stockskill evaluate NVDA buy --price 207 --stop 190 --target 250   # score a trade

# static / offline dashboards (for cron + GitHub Pages)
uv run stockskill smart-watchlist             # build a dynamic pinned + growth/value/sector list
uv run stockskill watchlist --open            # multi-ticker technical dashboard -> HTML file
uv run stockskill dashboard --open            # market pulse + your portfolio

# portfolio & holdings (CLI)
uv run stockskill portfolio                   # look-through leverage, concentration
uv run stockskill lookthrough                 # true underlying exposure of leveraged ETFs
uv run stockskill decay --multiplier 3        # leveraged-ETF volatility decay
uv run stockskill holdings buy AAPU 10 --price 45   # update holdings from a trade
```

## Commands

| Command | What it does |
|---|---|
| `value TICKER` | Fair value — two-stage DCF, reverse DCF (market-implied growth), relative multiples, dividend model; blended range + margin of safety. Assumption-sensitive names are flagged low-confidence instead of getting a false verdict. |
| `factors [--sector-neutral] [--by value\|…]` | Cross-sectional **factor scores** for the watchlist — value / quality / momentum / growth / low-vol, each a 0–100 percentile + a plain-English read, plus a coverage-gated composite. `--sector-neutral` ranks within sector (cheap-vs-peers, not a bet on cheap sectors). Weights via `STOCKSKILL_FACTOR_WEIGHTS`. |
| `backtest [--buckets N]` | **Backtest** a factor: monthly rebalance → buckets → forward returns → long-short spread, hit rate, and information coefficient (no look-ahead). Momentum today; value/quality once fundamentals history accrues. |
| `snapshot-fundamentals` | Record today's fundamentals as a dated point-in-time row (`data/fundamentals_history/`) — run daily to build the history a **value** backtest needs. Reuses the cache (no refetch). |
| `screen --lane core\|aggressive` | Rank a universe by percentile score (quality+value or growth+momentum). |
| `pulse` | Market radar: a market bar (indices/commodities/crypto), sector & factor rotation, breadth, a regime snapshot (VIX, yield curve, credit, leadership), CVR3, CNN Fear & Greed, rotation-leader detection, and a **commodity climate** read (copper = growth, gold = fear). |
| `evaluate TICKER buy\|sell\|short` | Score a **proposed trade** factor-by-factor (valuation, technical signal, trend, RSI, analyst consensus, risk/reward) into an alignment scorecard — analysis, not a yes/no. |
| `smart-watchlist` | Build a **dynamic** ticker list: pinned staples (always kept) + ~25 rotating picks by growth, undervaluation, and leading sectors — each with its 2x/3x leveraged ETF. |
| `watchlist` | Renders the multi-ticker dashboard to a **static HTML file** (for cron/Pages). The same board is served live by `serve` (see below). |
| `dashboard` | Self-contained HTML of the market pulse + your portfolio look-through, with a market-status badge and self-refresh. |
| `serve` | The **live web app** (Flask): the watchlist board at `/`, a holdings dashboard at `/holdings`, the ticker analyzer at `/analyze`, and Evaluate / Look-through / Monte Carlo tool pop-ups. |
| `portfolio` / `lookthrough` | Portfolio look-through: expands leveraged/basket ETFs into true underlying $ exposure, effective leverage, HHI concentration, factor groups. |
| `decay` | Leveraged-ETF volatility decay via Monte Carlo or a real price path. |
| `holdings buy\|sell\|list\|reprice` | Maintain `holdings.csv` from trades (shares-based, reprices to latest). |

## The live app (`serve`)

`stockskill serve` is the main interface — one Flask app that unifies the
watchlist, holdings, and analysis tools. It builds the board over your
[`data/tickers.csv`](data/tickers.csv) (sectioned: `[M7]`, `[SEMIS]`, …),
fetching every ticker **in parallel** (with an on-disk cache) and computing
everything from the tested indicator + signal libraries.

**The board (`/`)**
- **Three views** — Table (sortable, sparklines, a frozen Ticker column when you
  scroll sideways), **Cards**, and a **Heatmap grouped by sector** (each group
  headed by its average day move + count) — with live search and light/dark theme.
- **Three always-on panels** — sector performance, a live Markets panel (indices,
  metals/energy/ag commodities, crypto), and a **Macro** panel (VIX, 10Y yield,
  the dollar, the next Fed decision countdown, and scanned market-event headlines)
  — with the **filter chips** below.
- **Add-ticker box** with live autocomplete (name or symbol) that fetches and
  adds a ticker to the board on the fly.
- **Faceted filter chips** — signal / condition (oversold, squeeze, earnings…)
  / category / section.
- **Alert banner** — a sliding marquee that cycles through *every* ticker alert
  (52w highs/lows, surges/crashes, volume spikes, squeezes, active signals, and
  your custom `data/alerts.json`); pauses on hover, dismissible. (Macro events
  live in the Macro panel, not the marquee.)
- **Factor scores** — each card carries a factor chip (e.g. "◆ cheap · high
  quality · factor 83") and the table has a sortable **Factor** column (the
  sector-neutral composite percentile). See [factor investing](references/factor-investing.md).
- **Earnings flag** on each card — today / tomorrow / in N days / next week.
- **Click a card → a modal** with the full detail: an **interactive price chart**
  (1M–5Y/Max, real axes, hover shows date + price), the trade setup (ATR
  entry/stop/target + position sizing), options ideas, the **stock-analyzer
  valuation** (fair value bear/base/bull, signal, reverse-DCF growth, consensus),
  and **recent news** headlines (clickable, publisher · age).
- **Live prices, updated in place** — a real-time quote feed refreshes the whole
  board on a market-aware cadence: **every 15 min** during regular hours, **30 min**
  in extended hours (pre-market 4:00 ET → after-hours 8:00 PM ET), and **static**
  overnight and on weekends. The page **swaps just the changing numbers** (no full
  reload — your scroll, view, filters and theme are kept). If a refetch is
  rate-limited or errors, the board keeps the **last good values** instead of
  blanking. The update time shows in **your local timezone**.

**Tools & pages** — Evaluate a trade, **Look-through** (leveraged baskets ×
multiplier *and* plain index/sector ETFs like VOO/QQQ — top holdings + sector
weights), and Monte Carlo run live in a pop-up; a **Technical-indicators page**
(`/indicators`) plots price with Bollinger Bands, SMAs and the Ichimoku cloud,
plus RSI, Stochastic, MACD, ADX, ATR and OBV subpanels for any ticker
(`/api/evaluate`, `/api/lookthrough`, `/api/montecarlo`, `/api/indicators`).

**Holdings dashboard (`/holdings`, local only)** — opens in a new tab; positions
split by account (Brokerage / Roth IRA / 401(k)) with shares, live price,
today's gain, net gain, cost basis, **dividend yield + est. annual income**, value
and % of account; cash as Fidelity
SPAXX; summary tiles (total, current value, cost basis, cash, day change).
Record trades (bookkeeping — buy/sell, optional price/share to track cost basis)
and deposit/withdraw cash. `holdings.csv` is gitignored and **never published**.

The `watchlist` command renders the same board to a **static HTML file** for the
cron/GitHub-Pages path. Signals are **rule-based indicator states, not investment
advice** — the tool shows analysis and trade-offs; the decision is yours.

### Dynamic (smart) watchlist

`stockskill smart-watchlist` builds the ticker list automatically:
- **Pinned staples** (COST, AAPL, META, …) are always kept — never rotated out.
- **~25 rotating picks** from a curated candidate pool: top **growth** (revenue
  growth), top **undervalued** (positive DCF margin of safety), and the leading
  **sectors** (by 1-month performance).
- Each selected company/sector also gets its **2x/3x leveraged ETF** where one
  exists (AAPL→AAPU, semis→SOXL, energy→ERX, …).

It writes a sectioned `data/smart_tickers.csv`; render it with
`watchlist --tickers data/smart_tickers.csv`.

## Data, deployment & config

- **Data sources** — locally, free **yfinance/Yahoo**. For the **hosted** app
  (where Yahoo blocks datacenter IPs), a data-provider seam uses licensed,
  server-friendly APIs: **FMP** (stable API) for fundamentals + on-demand fetches,
  and **Finnhub** for the real-time board quote feed — each with yfinance as the
  automatic fallback. Keys live in host env vars (`FMP_API_KEY`, `FINNHUB_API_KEY`),
  never in the repo; verify with `stockskill fmp-check` / `finnhub-check`. Paid
  sources (Morningstar/Barchart) are read via your own logged-in browser — no
  credentials handled by the tool.
- **Deploy it (public, free)** — ship the safe public board as a web app on a
  container host (Render blueprint + `Dockerfile` included). Public mode excludes
  holdings; a committed data snapshot paints the board **instantly on cold start**
  while live prices fill in; the quote feed keeps it current on a market-aware
  cadence. See [DEPLOYMENT.md](DEPLOYMENT.md).
- **Scheduling** — `./scripts/install_schedule.sh` adds a cron entry (pre-open,
  every 30 min intraday, close; weekdays) that regenerates the dashboard **and**
  watchlist. See [`references/dashboard-and-scheduling.md`](references/dashboard-and-scheduling.md).
- **Cloud automation** — GitHub Actions (`.github/workflows/`) run the tests on
  every push and publish the **watchlist** to GitHub Pages during market hours
  (public tickers only — the portfolio dashboard is never published). See
  [`references/github-actions.md`](references/github-actions.md).
- **Config** — strategy/thresholds and factor weights via env vars
  (`TRADING_STRATEGY`, `BB_*`, `RSI_*`, `WEIGHT_*`, `ACCOUNT_SIZE`,
  `STOCKSKILL_FACTOR_WEIGHTS`, …).

## Architecture

```
src/stockskill/
  technicals/   RSI, MACD, Bollinger, ATR, Ichimoku, Stochastic, ADX, OBV, …
  signals/      BB/RSI/MACD/Ichimoku/Combined strategies, trend score, confidence
  factors/      value/quality/momentum/growth/low-vol scoring, sector-neutral, backtest, history
  valuation/    DCF, reverse DCF, multiples, DDM, scenarios, engine
  portfolio/    look-through leverage, concentration, decay, holdings management
  pulse/        sector/factor rotation, breadth, regime, market bar, sentiment
  trade/        ATR trade setup, position sizing, options-strategy suggestions
  alerts/       auto + custom alert engine
  montecarlo/   GBM + bootstrap price simulation (E[r], probability cone, VaR)
  watchlist/    ticker parsing, parallel pipeline, row model, board build + render
  dashboard/    pulse+portfolio HTML dashboard
  server/       Flask live app: board + holdings services/pages, analyzer, tool APIs
  data/         data-provider seam: FMP (stable) + Finnhub + yfinance (fundamentals,
                OHLCV, live quotes, options, search, news)
  leverage/     leveraged-ETF registry (look-through)
```

**Design:** math and data are separate — pure, unit-tested functions take
explicit numbers; the data layer feeds them. A saved snapshot makes any
valuation reproducible offline.

## Not investment advice

This is analysis tooling. It surfaces valuation, risk, and indicator states and
leaves the buy/sell/hold decision to you. Free data may be delayed or incomplete.
