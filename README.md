# stock-analysis-skill

A reproducible stock-analysis toolkit and dashboard for Claude. **The model
never does the math** — every number is produced by tested Python in the
`stockskill` package. Same inputs → same output, provable by re-running.

It combines three things most tools keep separate:
- **Fundamental depth** — DCF valuation, portfolio look-through leverage, risk.
- **Technical breadth** — 30+ indicators, trading signals, alerts, trade setups,
  a market-pulse radar, and Monte Carlo simulation.
- **One live web app** (`serve`) — a multi-view watchlist board, a per-account
  holdings dashboard, and every analysis tool reachable as a pop-up.

See [SKILL.md](SKILL.md) for how Claude uses this, [`references/`](references/)
for methodology, and [ROADMAP.md](ROADMAP.md) for what's built and what's next.

## Quickstart

```bash
uv run pytest -q                              # the tested math (135 tests)

# the live app — this is the main way to use it
uv run stockskill serve --open                # live dashboard: watchlist board + holdings + tools

# analysis (CLI)
uv run stockskill value NVDA --growth 0.15    # fair value: DCF + reverse DCF + multiples
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
- **Two always-on panels** — sector performance (left) and a live Markets panel
  (right: indices, metals/energy/ag commodities, crypto) — **filter chips** below.
- **Add-ticker box** with live autocomplete (name or symbol) that fetches and
  adds a ticker to the board on the fly.
- **Faceted filter chips** — signal / condition (oversold, squeeze, earnings…)
  / category / section.
- **Alert banner** — a sliding marquee that cycles through *every* alert (52w
  highs/lows, surges/crashes, volume spikes, squeezes, active signals, and your
  custom `data/alerts.json`); pauses on hover. Dismissible.
- **Earnings flag** on each card — today / tomorrow / in N days / next week — plus
  a **pre/after-hours** price line when an extended session is live.
- **Click a card → a modal** with the full detail: an **interactive price chart**
  (1M–5Y/Max, real axes, hover shows date + price), the trade setup (ATR
  entry/stop/target + position sizing), options ideas, and the **stock-analyzer
  valuation** (fair value bear/base/bull, signal, reverse-DCF growth, consensus).
- **Live** — the server caches on a market-aware cadence (~60s open, 5m extended,
  30m closed); the page refreshes to match and shows the update time in **your
  local timezone**.

**Tool pop-ups** — Evaluate a trade, leverage Look-through (basket constituents ×
multiplier, with the verified as-of date), and Monte Carlo run live in a modal
(`/api/evaluate`, `/api/lookthrough`, `/api/montecarlo`).

**Holdings dashboard (`/holdings`, local only)** — opens in a new tab; positions
split by account (Brokerage / Roth IRA / 401(k)) with shares, live price,
today's gain, net gain, cost basis, value and % of account; cash as Fidelity
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

## Data, scheduling & config

- **Free data** (yfinance/Yahoo). Paid sources (Morningstar/Barchart) are read
  via your own logged-in browser when needed — no credentials handled by the tool.
- **Scheduling** — `./scripts/install_schedule.sh` adds a cron entry (pre-open,
  every 30 min intraday, close; weekdays) that regenerates the dashboard **and**
  watchlist. See [`references/dashboard-and-scheduling.md`](references/dashboard-and-scheduling.md).
- **Cloud automation** — GitHub Actions (`.github/workflows/`) run the tests on
  every push and publish the **watchlist** to GitHub Pages during market hours
  (public tickers only — the portfolio dashboard is never published). See
  [`references/github-actions.md`](references/github-actions.md).
- **Config** — trading strategy and thresholds via env vars
  (`TRADING_STRATEGY`, `BB_*`, `RSI_*`, `WEIGHT_*`, `ACCOUNT_SIZE`, …).

## Architecture

```
src/stockskill/
  technicals/   RSI, MACD, Bollinger, ATR, Ichimoku, Stochastic, ADX, OBV, …
  signals/      BB/RSI/MACD/Ichimoku/Combined strategies, trend score, confidence
  valuation/    DCF, reverse DCF, multiples, DDM, scenarios, engine
  portfolio/    look-through leverage, concentration, decay, holdings management
  pulse/        sector/factor rotation, breadth, regime, market bar, sentiment
  trade/        ATR trade setup, position sizing, options-strategy suggestions
  alerts/       auto + custom alert engine
  montecarlo/   GBM + bootstrap price simulation (E[r], probability cone, VaR)
  watchlist/    ticker parsing, parallel pipeline, row model, board build + render
  dashboard/    pulse+portfolio HTML dashboard
  server/       Flask live app: board + holdings services/pages, analyzer, tool APIs
  data/         yfinance adapters (fundamentals, OHLCV, options, search)
  leverage/     leveraged-ETF registry (look-through)
```

**Design:** math and data are separate — pure, unit-tested functions take
explicit numbers; the data layer feeds them. A saved snapshot makes any
valuation reproducible offline.

## Not investment advice

This is analysis tooling. It surfaces valuation, risk, and indicator states and
leaves the buy/sell/hold decision to you. Free data may be delayed or incomplete.
