# Market pulse methodology

`stockskill pulse` reads the market from free data (sector/factor ETFs + a few
macro tickers via yfinance). All arithmetic is pure and tested
(`pulse/metrics.py`); the CLI only fetches and formats. `--price-map` caches
the fetched series so a pulse reproduces exactly.

## What each section means
- **Sector rotation** — trailing returns of the 11 SPDR sector ETFs over
  1d/1w/1m/3m, sorted. Leadership rotating from cyclicals (XLK, XLY) toward
  defensives (XLP, XLU, XLV) is a classic late-cycle / risk-off tell; the
  reverse is risk-on.
- **Factor / style rotation** — relative strength (return difference) of style
  pairs. Growth>Value and High-beta>Low-vol and Small>Large and
  Cyclicals>Defensives all leaning positive = risk-on; leaning negative =
  risk-off. Semis vs market is a useful AI/cycle bellwether.
- **Breadth** — share of sectors positive over 1m and above their 50-day MA.
  Strong index + weak breadth = narrow, fragile leadership.
- **Regime snapshot** — VIX, 10Y and 3M yields, the 10Y-3M curve, cap-weight
  vs equal-weight (SPY vs RSP), high-yield vs investment-grade credit, gold,
  dollar. Threshold flags (VIX>20, curve<0, narrow leadership, credit risk-off)
  are rule-based, not opinions.

## How to read it honestly
- These are **computed facts, not signals.** No single number is a call. A
  defensive lean is a *cluster*: rising VIX + inverted or flattening curve +
  narrow leadership + credit underperforming, together.
- Free ETF data reflects price only; it misses fundamentals and news. Use pulse
  to see *where* attention is flowing, then `value`/`screen` for *whether* it's
  justified.
- Short windows are noisy. Weight 1m/3m over 1d for rotation calls.

## The paid-session layer (manual, not in the CLI)
When the Claude-in-Chrome extension is connected, the proprietary layer
(Morningstar sector outlooks, Barchart unusual activity, analyst revisions) is
read live in-session to add the "why" behind the moves and to sanity-check the
free numbers. That stays a hand-driven, occasional read — deliberately not
automated into the CLI, to avoid industrialized scraping of paid sites.
