# Unified dashboard — build plan (execute top-to-bottom)

Goal: turn the tool into ONE interactive web app (served by Flask, always live)
that unifies the watchlist, holdings, and Monte Carlo, with every analysis
feature reachable as a pop-up. The static HTML generators stay for cron/offline.

## 1. Tickers (data) — quick wins
- [x] Add Oracle + its 2x (`ORCL`, `ORCX` = Defiance 2x ORCL) to the watchlist.
- [x] SpaceX is PRIVATE — add `DXYZ` (Destiny Tech100, holds SpaceX) as the proxy.
- [x] Add the requested names: memory (SNDK, WDC, STX, MU), PENG, ALAB, SEZL,
      CORT, CSCO, HOOD, SNPS, CDNS, AR, WFC, HSBC, TCEHY, BABA (+ existing AMD,
      DDOG, INTC, CRWD, QCOM, HD, LOW, MRVL, AMAT, AVGO, CVX, BAC).

## 2. Card view — expanded detail (static-render, applies everywhere)
- [x] Always show a **trade setup** when expanded (direction from trend on HOLD).
- [x] Color the valuation: **green undervalued / red overvalued / neutral fair**.
- [x] Render **fair value as a table** (bear/base/bull rows, each vs price).
- [x] **Interactive price chart** with timeframe toggle (1/3/6mo, 1/2/5y, Max) and
      a hover tooltip showing price + date at the hovered point. Slices by calendar
      date; recent ~6mo kept daily (crisp short views), older sampled weekly.
- [x] Make the **close (✕) button bigger / easier to hit**.

## 3. Layout (all views)
- [x] **Left panel**: condensed sector performance — always visible (no longer collapsible).
- [x] **Right panel**: Markets — indices/metals/crypto, refreshed with the page like stocks.
- [x] Move the **filter chips below** the two panels.

## 4. Serve the watchlist as THE live dashboard (architecture shift)
- [x] `serve` home `/` = the live watchlist (cards/table/heatmap) from Flask;
      analyzer moved to `/analyze`. Core build extracted to `watchlist/build.py`,
      shared by the CLI (static file) and the server (live).
- [x] Always live: `WatchlistService` caches the HTML with a market-aware TTL
      (60s open / 5m ext / 30m closed); the page polls via meta-refresh.
- [x] **Add-ticker** box with autocomplete (reuses `/api/search`): validates the
      symbol has data, adds it live, rebuilds the board. `/api/watchlist/add`,
      `/remove`, `/added`. Verified end-to-end (added TSLA + ORCL live).

## 5. Analysis tools as pop-ups on the dashboard
Buttons that open a small modal which runs the feature live and shows the result:
- [x] Pulse · [x] Evaluate trade · [x] Value a stock · [x] Look-through · [x] Monte Carlo.
      Toolbar in the add-bar (served mode); a shared #toolmodal fetches each tool
      live. New endpoints: /api/pulse, /api/lookthrough/<t>, /api/montecarlo/<t>
      (value/evaluate reuse /api/stock, /api/evaluate). All verified in-browser.

## 6. Holdings dashboard (centralized, part of the app)
- [ ] View holdings split by account: **brokerage / Roth IRA / 401k**.
- [ ] **Execute trades** (buy/sell) that update internal values (reuse `holdings`).
- [ ] **Deposit / withdraw cash** per account.

## 7. Monte Carlo dashboard
- [ ] A page/modal to simulate a stock: inputs (ticker, horizon, paths, method,
      thresholds) → distribution + probability cone + up/down odds. (ML deep-dive later.)

## Notes
- SpaceX / Oracle-2x handled via DXYZ / ORCX (verified live).
- The `--watch` static generation stays available for the cron/Pages path;
  the interactive app is the served version.
