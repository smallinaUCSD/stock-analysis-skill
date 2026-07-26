# Interactive stock analyzer (`stockskill serve`)

A local Flask app to search any ticker and get a live analysis. The server only
exposes the tested analysis engine over HTTP — it computes no numbers itself.

```bash
uv run stockskill serve --open          # http://127.0.0.1:8787
```

- **Search** by company name *or* ticker — a live dropdown (via Yahoo symbol
  search, `data/search.py`) resolves "oracle" → ORCL; if an exact ticker
  lookup fails, it falls back to the best name match. Optional growth override.
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

## Valuation basis, and when it withholds
FCF is sourced from the summary and, failing that, the annual cash-flow
statement.
- **Positive FCF** → normal FCF-DCF.
- **FCF negative but earnings positive** (a profitable company in a heavy-capex
  phase, e.g. ORCL mid-AI-buildout) → an **earnings-based DCF** runs on net
  income as a cash-flow *proxy*, clearly flagged ("rougher, earnings-based").
- **Neither FCF nor earnings positive** (genuinely unprofitable) → it shows
  **"no reliable fair-value basis"** with the reason and withholds
  bear/base/bull rather than inventing a number; the analyst view and options
  are still shown.

A dividend model contributes only as a minor cross-check and is excluded for
sub-1% yielders (it understates buyback-heavy / growth names).

**Low-confidence signal.** For a hyper-grower whose growth had to be clamped
(e.g. LLY, NVDA — 30% cap) or a value that's >80% terminal, the signal is
softened to **"assumption-sensitive — read the range, not a single call"** with
the reason, and the bear/base/bull range + reverse-DCF + analyst view are shown
instead of a confident cheap/expensive verdict. The discount rate is floored at
8% so a low beta can't inflate the DCF. See `valuation-methodology.md`.

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
