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
- [ ] **Left panel**: condensed sector performance — always visible.
- [ ] **Right panel**: commodities (indices/metals/crypto), live-updating like stocks.
- [ ] Move the **filter chips below** the two panels.

## 4. Serve the watchlist as THE live dashboard (architecture shift)
- [ ] `serve` home = the watchlist (cards/table/heatmap), served from Flask.
- [ ] Always live: server refreshes data on a market-aware cadence; page polls.
      (No `--watch` flag needed; the input/static file goes away for the app.)
- [ ] **Add-ticker** box with autocomplete (reuse `/api/search`) that adds a
      ticker to the board live and fetches its data.

## 5. Analysis tools as pop-ups on the dashboard
Buttons that open a small modal which runs the feature live and shows the result:
- [ ] Pulse · [ ] Evaluate trade · [ ] Value a stock · [ ] Look-through · [ ] Monte Carlo.

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
