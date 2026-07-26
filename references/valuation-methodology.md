# Valuation methodology

Every method below is implemented as a pure function in `stockskill.valuation`
and unit-tested against hand-checked numbers. This doc explains what each one
assumes and when to trust it.

## Two-stage DCF (`dcf.py`)
Projects free cash flow to the firm for an explicit window (default 10y) at a
growth rate, then a Gordon-growth perpetuity. Discounts at WACC (we approximate
with CAPM cost of equity). Equity value = enterprise value − net debt.

- **Trust it** for profitable, FCF-positive, moderate-growth businesses.
- **Distrust it** when the terminal value is >75% of EV (all the value is in
  unknowable far-future assumptions) — the report prints the terminal %.
- Garbage in, garbage out: the growth and discount rate dominate the answer.
  Always show a sensitivity grid (`sensitivity_grid`) rather than one point.

## Reverse DCF (`reverse_dcf.py`)
The most honest use of a DCF: instead of guessing growth to get a value, take
the current price as given and solve for the growth the market is implying.
Then ask: is that growth realistic vs. history and the size of the company?
This reframes "is it cheap?" as "what has to be true?" — much harder to fool
yourself with.

## Relative multiples (`multiples.py`)
Applies peer multiples (P/E, EV/EBITDA, P/S, P/FCF) to the company's own
metrics. Returns the median across methods (robust to one bad multiple). The
judgement — which peers, which multiple — is an input you must justify, not
something the code invents. EV/EBITDA is enterprise-level (nets out debt);
P/E and P/S are equity-level.

## Dividend discount (`ddm.py`)
Gordon growth and a two-stage variant. **Caveat:** for companies that return
capital mostly via buybacks (e.g. large-cap tech with a token dividend), the
DDM massively understates value and should get little or zero weight. In the
blended report, drop or down-weight DDM for sub-~1% yielders. This is a known
limitation to state out loud, not hide.

## Blending (`engine.py`)
The report weights methods (default DCF 45 / multiples 35 / DDM 20) into a
base case, and reports the min–max of individual methods as the range. Margin
of safety = (base − price) / base. Positive = discount, negative = premium.
The weights are assumptions — adjust them per company and say that you did.

## Cost of equity
CAPM: `k = risk_free + beta × equity_risk_premium`. Defaults: risk-free 4.3%,
ERP 5.0%. These are macro assumptions; update the risk-free to the current
10y Treasury when it matters.
