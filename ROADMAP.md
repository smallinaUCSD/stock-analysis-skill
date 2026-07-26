# Feature-Parity Roadmap — matching Dad's `smi` dashboard

Goal: add the technical-trading, ML, and multi-ticker dashboard breadth of Dad's
`smi` on top of our valuation + portfolio-risk depth. Ordered by dependency:
each phase builds on the one before. All new math stays in **pure, tested
functions** (our core rule), same as the rest of `stockskill`.

## How the two projects differ (so we build, not duplicate)
- **smi** = technical/momentum **trading** signals + ML breakout/crash prediction
  over a big watchlist, in a rich multi-view dashboard. Short-horizon.
- **stockskill** = fundamental **valuation** (DCF/scenarios), portfolio
  **look-through leverage & concentration**, single-stock analyzer. Long-horizon.
- Plan: keep our depth, bolt on his breadth.

## Already have — reuse, don't rebuild
- Market clock (ET, regular/extended hours) → `marketclock.py`
- yfinance data layer: fundamentals, prices, options chain, symbol search
- Options snapshot (ATM call/put, IV, put/call skew) → `data/options.py`
- Regime/sector/factor rotation, breadth, VIX/curve/credit → `pulse/`
- Analyst consensus (reported) → `analyze.py`
- Self-contained HTML dashboard + theme-aware CSS + market-status badge → `dashboard/`
- Interactive Flask server + search → `server/`
- Portfolio look-through, HHI concentration, leveraged decay → `portfolio/`
- Valuation (DCF, reverse-DCF, scenarios, confidence gate) → `valuation/`
- Local cron scheduler → `scripts/`

## Two honesty flags before we build (our ethos)
- **ML "predict the next NVDA breakout"** cuts against our reproducible/humble
  stance. We'll build it — but treat outputs as *probabilities with tracked
  hit-rates*, never promises. Dad's performance-tracking (win rate / expected
  return) is the honest part; keep it front-and-center.
- **BUY/SHORT + trade-setup signals** are rule-based *indicator states*
  (like a charting tool), not personalized advice. Frame them as "the indicator
  says X" with entry/stop/target as an *informational* risk framework — the
  decision stays the user's. No synthesized "recommended action."

---

## Phase 1 — Technical-indicator foundation  ✅ DONE (`technicals/`, 18 tests)
`src/stockskill/technicals/` — pure functions over a price/volume series, tested.
- [x] RSI (14, EWM)
- [x] MACD (12/26/9) + signal + histogram + crossover state
- [x] Bollinger Bands: MA20±2σ, position %, width %, squeeze detection
- [x] ATR (14) + historical volatility (30d annualized)
- [x] Moving averages SMA50/SMA200 + Golden/Death cross detection
- [x] Stochastic %K/%D, ADX, CCI, MFI, Williams %R
- [x] ROC, Volume ROC, OBV, volume bias (up/down), volume spike vs avg
- [x] Ichimoku (Tenkan/Kijun/Senkou A-B), vectorized
- [x] Price-change metrics: Day / 5D / 1M / 6M / YTD / 1Y
- [x] Sparkline series
- [x] Denoised P/E: P/E relative to average, P/E volatility (std)
- [x] OHLCV fetcher in the data layer (`data.ohlcv`) to feed the indicators
- Note: 1Y change needs >252 bars; fetch >1y of history in Phase 3 so it fills.

## Phase 2 — Trading strategies, trend & signal confidence  ✅ DONE (`signals/`, 13 tests)
`src/stockskill/signals/` — deterministic signal states, configurable.
- [x] Per-strategy signals (BUY/SELL/SHORT/HOLD): BB, RSI, MACD, Ichimoku
- [x] Combined strategy: weighted voting + conflict resolution
- [x] BB+Ichimoku modes: CONFIRM / AND / OR
- [x] Multi-factor Trend Score + arrows (↑ ↗ → ↘ ↓)
- [x] Signal confidence via inter-strategy agreement (STRONG/MODERATE/WEAK)
- [x] Env-var config for thresholds & weights (SignalConfig.from_env)
- [x] IndicatorSnapshot built from OHLCV (bridges technicals -> signals)

## Phase 3 — Multi-ticker watchlist dashboard  (the big UI lift) — IN PROGRESS
`src/stockskill/watchlist/` (+ `stockskill watchlist` command). 5 tests.
- [x] Sectioned `tickers.csv` parser: `[MEME]` / `[M7]` / `[TICKERS]`, dedup
- [x] Category auto-detect: tech / leveraged / ETF / dividend (via leverage registry + fundamentals)
- [x] Multi-ticker pipeline: parallel fetch (ThreadPoolExecutor ~5 workers),
      per-ticker on-disk cache (`.cache/stock_cache/*.pkl`, TTL)
- [x] TickerRow: stitches technicals + signals + fundamentals + flags per ticker
- [x] **Table view**: sortable columns, sparklines, live ticker search,
      consolidated INDICATORS column (MACD, cloud, golden/death, squeeze, 52wH/L)
- [x] **Card view**: rich per-ticker cards (price/change, signal+trend, sparkline,
      indicators, 1M/1Y/RSI/PE, external links). [swipeable multi-page: later polish]
- [x] **Heatmap view**: color-intensity tiles (by day change) + signal/trend
- [x] Filter chips: faceted (signal / condition / category / section), OR-within +
      AND-between groups, live count; + live search + sortable table
- [x] View toggle (table/card/heatmap) + theme toggle + persistence (localStorage)
- [x] **Combined dashboard**: watchlist cards expand on click to reveal the stock
      analyzer (valuation bear/base/bull, signal, reverse-DCF, consensus) + trade
      setup (BUY/SHORT only) + options ideas; collapsed card is clean; trend shown
      as a meaningful descriptor ("Strong uptrend · trend +7") instead of an arrow.
      Valuation embedded per card from the fetched snapshot (no extra network).
- [x] Card detail opens as a **modal mini-window** (no adjacent-card reflow) with
      an obvious "🔎 Click for full analysis" affordance + hover highlight.
- [x] **Sector performance** strip on the watchlist (collapsible diverging bars).
- [x] **Realtime**: `watchlist --watch` regenerates on a market-aware cadence
      (~60s open / 5m extended / 30m closed) and the page auto-refresh matches.
- [x] **Holdings from trades**: `stockskill holdings buy/sell/list/reprice`
      (shares-based, infers shares from legacy dollar rows, reprices at latest).
- [x] **Dynamic (smart) watchlist** (`watchlist/dynamic.py` + `smart-watchlist`):
      pinned staples (never rotated out) + ~25 rotating picks by growth /
      undervaluation (DCF margin of safety) / leading sectors, each with its
      2x/3x leveraged ETF. Writes a sectioned `data/smart_tickers.csv`.
- [ ] Corporate events: next-earnings date + earnings-week badge, dividend ex-date
- [ ] Polish: external links also on heatmap tiles; multi-page swipeable cards

## Phase 4 — Market-indicators bar & rotation  ✅ DONE (extends `pulse/`, 5 tests)
- [x] Indices strip: Dow / S&P 500 / Nasdaq with live change
- [x] Commodities (gold/silver/copper), crypto (BTC)
- [x] Fear & Greed index (CNN, Referer header clears the 418), CVR3 (computed from VIX)
- [x] Early rotation detection: 3d/5d momentum inflection → leading index (RSP/QQQ/…)
- [x] Wired into both `stockskill pulse` and the HTML dashboard (market bar strip)
- [ ] AAII bull/bear sentiment (stubbed — no stable free API; degrades to None)
- [ ] TTL caching (~30 min) for sentiment / F&G — pending (fetch is fast enough for now)

## Phase 5 — Alerts  ✅ DONE (`alerts/`, 5 tests)
`src/stockskill/alerts/`
- [x] Alert engine: 52w high/low, surge/crash (>10%), volume spike, BB squeeze,
      active BUY/SELL/SHORT signals (ML breakout/crash alerts deferred to Phase 7)
- [x] Custom alerts via `data/alerts.json` (price/%-change/RSI/volume/signal conditions)
- [x] Alert banner in the watchlist dashboard + click-to-dismiss (localStorage,
      re-shows when the alert set changes)

## Phase 6 — Trade setup & risk (informational framing)  &  options strategy  ✅ DONE (`trade/`, 6 tests)
- [x] ATR-based trade setup: entry / stop (2×ATR) / target (2:1 R:R)
- [x] Position sizing: risk 2%/trade, 25% max position (ACCOUNT_SIZE env)
- [x] Rule-based options suggestions (calls/puts + earnings straddle/strangle
      from trend/RSI/momentum/golden-death + implied move + earnings timing)
- [x] Trade-setup box + options ideas in the watchlist card view (for BUY/SHORT)
- Note: earnings straddle/pre-earnings ideas need per-ticker options data +
  earnings date — surface in the analyzer (which fetches options) as a follow-on.

## Phase 7 — Monte Carlo simulation (the "ML" step)  ← IN PROGRESS (`montecarlo/`, 7 tests)
The modeling step is **Monte Carlo simulation** (not a classifier).
- [x] Price-path simulation: **GBM** (fit drift & vol) + **bootstrap** (resample
      historical daily returns) over an N-day horizon. `stockskill montecarlo TICKER`.
- [x] Outcome distribution: P(gain ≥ X) / P(loss ≥ Y), expected & median return,
      percentile bands (p5/p25/p50/p75/p95), VaR(95%).
- [x] "Training" = param estimation from 2y history; `--climate` nudges drift by
      the commodity climate score (known macro trends baked in).
- [ ] Surface in the analyzer / watchlist card (probability cone + up/down odds).
- [ ] Optional portfolio-level MC (correlated paths) for drawdown odds.
- Honesty: outputs are probabilities from an explicit model, never predictions.

## Phase 8 — Automation (Dad's GitHub Actions)
- [ ] GitHub Actions `build.yml`: rebuild dashboard every ~30 min during market hours
- [ ] GitHub Actions `mlbuild.yml`: retrain ML daily Mon–Fri, commit model+cache
- [ ] Decide: keep our **local cron** (private, no cloud) vs Dad's **GitHub Actions**
      (always-on, but pushes data to a repo). Could do both.

---

## Suggested order
1 → 2 → 3 give a working multi-ticker technical dashboard (the visible bulk of `smi`).
4 → 5 → 6 add market context, alerts, and trade framing.
7 → 8 add ML and automation last (highest effort, most caveats).
Reassess after Phase 3 — that's where it starts to *look* like Dad's tool.
