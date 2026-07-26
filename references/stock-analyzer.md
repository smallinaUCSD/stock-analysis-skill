# Interactive stock analyzer (`stockskill serve`)

A local Flask app to search any ticker and get a live analysis. The server only
exposes the tested analysis engine over HTTP — it computes no numbers itself.

```bash
uv run stockskill serve --open          # http://127.0.0.1:8787
```

- **Search** any ticker (optional growth override, blank = data-driven).
- **Stock detail** (from `/api/stock/<ticker>`):
  - price, beta, dividend yield;
  - **valuation signal** — price vs. the tool's DCF-based fair value
    (deep discount / undervalued / fair / expensive / priced for perfection);
  - **bear / base / bull** fair values (growth ± and discount ± around base);
  - **reverse-DCF** implied growth ("the price assumes X% growth");
  - **analyst consensus** — reported third-party data (reco, mean, count, target);
  - **options snapshot** — nearest-expiry ATM call/put, implied vol, put−call skew.

## The advice boundary (important)
This tool produces **analysis, not a personalized buy/sell/hold instruction.**
- The *valuation signal* is a factual characterization of price vs. a
  transparently-computed fair value (assumptions are shown) — not "you should buy."
- The *consensus* is labeled reported third-party data, displayed as-is.
- The two often disagree (e.g. DCF "expensive" vs. Street "Strong Buy"); showing
  both, with the decision left to the user, is deliberate.
Do not add a synthesized "recommended action: BUY/SELL/HOLD" field.

## Data-driven base growth
Base-case stage-1 growth defaults to the company's reported revenue growth
(else earnings growth), clamped to 3–30%, so a hyper-grower like NVDA isn't
valued at a flat 8%. The growth used and its source are shown, and the user can
override it. Everything remains deterministic and reproducible.

## Notes
- Free data (yfinance) can be delayed/incomplete; missing fields drop the
  methods that need them.
- The market pulse + portfolio view is the separate `dashboard` command.
- Bind is localhost by default; treat it as a personal tool, not a public service.
