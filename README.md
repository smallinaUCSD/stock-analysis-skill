# stock-analysis-skill

A reproducible stock-analysis toolkit and dashboard for Claude. **The model
never does the math** — every number is produced by tested Python in the
`stockskill` package. Same inputs → same output, provable by re-running.

It combines two things most tools keep separate:
- **Fundamental depth** — DCF valuation, portfolio look-through leverage, risk.
- **Technical breadth** — 30+ indicators, trading signals, a multi-view
  watchlist dashboard, alerts, trade setups, and a market-pulse radar.

See [SKILL.md](SKILL.md) for how Claude uses this, [`references/`](references/)
for methodology, and [ROADMAP.md](ROADMAP.md) for what's built and what's next.

## Quickstart

```bash
uv run pytest -q                              # the tested math (108+ tests)

# analysis
uv run stockskill value NVDA --growth 0.15    # fair value: DCF + reverse DCF + multiples
uv run stockskill screen --lane core          # rank a universe into a shortlist
uv run stockskill pulse                        # market pulse: sectors, breadth, regime, sentiment
uv run stockskill evaluate NVDA buy --price 207 --stop 190 --target 250   # score a trade

# the dashboards
uv run stockskill smart-watchlist             # build a dynamic pinned + growth/value/sector list
uv run stockskill watchlist --open            # multi-ticker technical dashboard
uv run stockskill watchlist --watch           # ...live, refreshing during market hours
uv run stockskill dashboard --open            # market pulse + your portfolio
uv run stockskill serve --open                # interactive: search any ticker

# portfolio & holdings
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
| `watchlist` | The multi-ticker **dashboard** (see below). |
| `dashboard` | Self-contained HTML of the market pulse + your portfolio look-through, with a market-status badge and self-refresh. |
| `serve` | Local Flask app to **search any ticker** and get live valuation, bear/base/bull, analyst consensus, and an options snapshot. |
| `portfolio` / `lookthrough` | Portfolio look-through: expands leveraged/basket ETFs into true underlying $ exposure, effective leverage, HHI concentration, factor groups. |
| `decay` | Leveraged-ETF volatility decay via Monte Carlo or a real price path. |
| `holdings buy\|sell\|list\|reprice` | Maintain `holdings.csv` from trades (shares-based, reprices to latest). |

## The watchlist dashboard

`stockskill watchlist` builds a self-contained HTML dashboard over your
[`data/tickers.csv`](data/tickers.csv) (sectioned: `[M7]`, `[MEME]`, …). It
fetches every ticker **in parallel** (with an on-disk cache) and computes
everything from the tested indicator + signal libraries.

- **Three views** — Table (sortable, sparklines), **Cards**, Heatmap — with a
  view toggle, live search, and light/dark theme, all persisted.
- **Faceted filter chips** — signal / condition (oversold, squeeze, surge…) /
  category (tech, leveraged, ETF, dividend) / section (M7, MEME…).
- **Sector-performance strip** — 1-month diverging bars.
- **Alert banner** — 52w highs/lows, surges/crashes, volume spikes, squeezes,
  active signals, and your custom `data/alerts.json`. Dismissible.
- **Click a card → a modal mini-window** with the full detail: the trade setup
  (ATR entry/stop/target + position sizing, for BUY/SHORT), buy calls/puts
  options ideas, and the **stock-analyzer valuation** (fair value bear/base/bull,
  valuation signal, reverse-DCF implied growth, analyst consensus).
- **Realtime** — `--watch` regenerates on a market-aware cadence (~60s open,
  5m extended, 30m closed) and the page auto-refresh matches.

Signals are **rule-based indicator states, not investment advice** — the tool
shows analysis and trade-offs; the decision is yours.

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
  watchlist/    ticker parsing, parallel pipeline, row model, dashboard render
  dashboard/    pulse+portfolio HTML dashboard
  server/       Flask interactive analyzer + symbol search
  data/         yfinance adapters (fundamentals, OHLCV, options, search)
  leverage/     leveraged-ETF registry (look-through)
```

**Design:** math and data are separate — pure, unit-tested functions take
explicit numbers; the data layer feeds them. A saved snapshot makes any
valuation reproducible offline.

## Not investment advice

This is analysis tooling. It surfaces valuation, risk, and indicator states and
leaves the buy/sell/hold decision to you. Free data may be delayed or incomplete.
