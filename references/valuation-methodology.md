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
CAPM: `k = risk_free + beta × equity_risk_premium`, **floored at 8%**. Defaults:
risk-free 4.3%, ERP 5.0%. The floor matters: a low beta (e.g. LLY at 0.51)
otherwise implies a sub-7% equity discount rate, which — combined with high
growth — massively inflates the DCF. The floor was the single fix that brought
LLY's fair value from an absurd ~$2,050 down into the analyst-consensus range.

## Growth: data-driven, and optionally fading
Base-case stage-1 growth defaults to the company's reported revenue growth
(clamped to 3–30%), so a hyper-grower isn't valued at a flat 8%. Growth is held
constant across the explicit window by default — a plain two-stage DCF, which
(with the discount floor) tracks analyst targets well across most names. An
opt-in `fade` tapers growth toward a mature rate; it's off by default because
fading on top of a conservative terminal rate pushes fair values ~50% too low.

## Confidence gate (the analyzer)
A forward DCF is only as good as its assumptions. The analyzer downgrades a
bold verdict to **"assumption-sensitive — read the range"** when the estimate
is fragile: growth had to be clamped (a hyper-grower we can't extrapolate for a
decade), or the terminal value is >80% of EV. It still shows the bear/base/bull
range and the reverse-DCF; it just refuses to call "cheap" or "expensive" with
false confidence. Banks and negative-FCF names are handled separately (see
`stock-analyzer.md`).
