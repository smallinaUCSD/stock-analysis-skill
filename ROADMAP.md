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

## Phase 1 — Technical-indicator foundation  (everything below depends on this)
`src/stockskill/technicals/` — pure functions over a price/volume series, tested.
- [ ] RSI (14, EWM)
- [ ] MACD (12/26/9) + signal + histogram + crossover state
- [ ] Bollinger Bands: MA20±2σ, position %, width %, squeeze detection
- [ ] ATR (14) + historical volatility (30d annualized)
- [ ] Moving averages SMA50/SMA200 + Golden/Death cross detection
- [ ] Stochastic %K/%D, ADX, CCI, MFI, Williams %R
- [ ] ROC, Volume ROC, OBV, volume bias (up/down), volume spike vs avg
- [ ] Ichimoku (Tenkan/Kijun/Senkou A-B/Chikou), vectorized
- [ ] Price-change metrics: Day / 5D / 1M / 6M / YTD / 1Y
- [ ] Sparkline series (30d/5d/1m/6m/ytd/1y + volume)
- [ ] Denoised P/E: P/E relative to 5Y average, P/E volatility (1Y std)

## Phase 2 — Trading strategies, trend & signal confidence
`src/stockskill/signals/` — deterministic signal states, configurable.
- [ ] Per-strategy signals (BUY/SELL/SHORT/HOLD): BB, RSI, MACD, Ichimoku
- [ ] Combined strategy: weighted voting + conflict resolution
- [ ] BB+Ichimoku modes: CONFIRM / AND / OR
- [ ] Multi-factor Trend Score + arrows (↑ ↗ → ↘ ↓)
- [ ] Signal confidence via inter-strategy agreement (STRONG/MODERATE/WEAK)
- [ ] Env-var config for all thresholds & weights (BB_*, RSI_*, MACD_PERIOD,
      WEIGHT_*, TRADING_STRATEGY, …)

## Phase 3 — Multi-ticker watchlist dashboard  (the big UI lift)
Extend `dashboard/` + `server/` from single-stock to a watchlist grid.
- [ ] Sectioned `tickers.csv` parser: `[MEME]` / `[M7]` / `[TICKERS]`, dedup
- [ ] Category auto-detect: tech / leveraged / ETF / emerging-tech / speculative / dividend
- [ ] Multi-ticker pipeline: parallel fetch (ThreadPoolExecutor ~5 workers),
      per-ticker on-disk cache (`data/stock_cache/*.pkl`), rate limiting
- [ ] **Table view**: sortable columns, sparklines, live ticker search,
      consolidated INDICATORS column (signals, golden/death, ML scores)
- [ ] **Card view**: 3 swipeable pages (price/technicals · fundamentals/earnings/trade-setup · range charts)
- [ ] **Heatmap view**: color-intensity tiles + external links (Barchart/Yahoo/Finviz/Zacks/StockAnalysis)
- [ ] Filter chips: signals, oversold/overbought, surge/crash, volume, squeeze,
      earnings-week, dividend, category filters
- [ ] Theme toggle + view persistence (localStorage)
- [ ] Corporate events: next-earnings date + earnings-week badge, dividend ex-date

## Phase 4 — Market-indicators bar & rotation  (extends `pulse/`)
- [ ] Indices strip: Dow / S&P 500 / Nasdaq with live change
- [ ] Commodities (gold/silver/copper), crypto (BTC)  *(gold/dollar already in pulse)*
- [ ] Fear & Greed index (CNN), AAII bull/bear sentiment, CVR3 market signal
- [ ] TTL caching (~30 min) for VIX / sentiment / F&G
- [ ] Early rotation detection: 3d/5d momentum inflection → leading index/sector

## Phase 5 — Alerts
`src/stockskill/alerts/`
- [ ] Alert engine: 52w high/low, surge/crash (>10%), volume spike, BB squeeze,
      active signals, ML breakout (≥70%) / crash-risk (≥50%)
- [ ] Custom alerts via `data/alerts.json` (price/%-change/RSI/volume/signal conditions)
- [ ] Alert banner in dashboard + click-to-dismiss (localStorage)

## Phase 6 — Trade setup & risk (informational framing)  &  options strategy
- [ ] ATR-based trade setup: entry / stop (2×ATR) / target (4×ATR, 2:1 R:R)
- [ ] Position sizing: risk 2%/trade, 25% max position (env-configurable)
- [ ] Rule-based options-strategy suggestions (calls/puts/straddle/strangle
      from technicals + implied move + earnings timing) — extend `data/options.py`

## Phase 7 — ML breakout/crash predictor
`src/stockskill/ml/` (+ `ML_GUIDE.md`)
- [ ] Feature engineering: 28–30 technical + fundamental features (incl. denoised P/E)
- [ ] Gradient Boosting classifier, StandardScaler, model persistence (`data/ml_models/`)
- [ ] Training pipeline: stratified sampling, 2y history, per-ticker cache, verbose/quiet
- [ ] Predict: breakout score, crash risk, class (BREAKOUT/CRASH/NEUTRAL), confidence
- [ ] Crash filter: only flag CRASH when technicals **and** high/volatile P/E agree
- [ ] Performance tracking: record predictions, rolling win-rate / expected-return / sample-size
- [ ] Surface in dashboard INDICATORS (color-coded) + alerts

## Phase 8 — Automation (decision: local vs cloud)
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
