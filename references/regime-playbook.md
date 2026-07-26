# Regime & recession playbook

A framework for reading the macro regime and thinking through a defensive
rotation — **options and trade-offs, never an instruction to trade.** Timing
regime shifts is genuinely hard; being early is expensive and being wrong is
worse. The point is preparation, not prediction.

## The dashboard (from `stockskill pulse`)
Watch these together, not individually:
- **Yield curve (10Y-3M).** Inversion (<0) has preceded most recessions, but
  with long and variable lead times (often 6-18 months), and the *re-steepening*
  after inversion is often the nearer warning. A positive curve is not an
  all-clear by itself.
- **VIX.** <15 calm, >20 elevated, >30 stressed. Rising VIX with falling
  breadth is the combination that matters.
- **Breadth.** Narrowing leadership (few sectors above their 50d MA; cap-weight
  outrunning equal-weight) means the index is being held up by a handful of
  names — fragile.
- **Credit (HY vs IG).** High-yield underperforming investment-grade is risk
  appetite draining out; credit usually cracks before equities capitulate.
- **Sector leadership.** Rotation into staples/utilities/health care and out of
  discretionary/tech is a late-cycle tell.

## No single trigger
A defensive posture is warranted when *several* of these lean the same way at
once — e.g. inverted/re-steepening curve **and** rising VIX **and** narrowing
breadth **and** credit risk-off **and** defensive sector leadership. One flag is
noise.

## Defensive rotation candidates (to evaluate, not auto-buy)
The user's stated recession hedges — consumer staples and low-beta quality:
AAPL (arguable), COST, PEP, PG, KO, WMT, plus utilities (XLU) and health care
(XLV). These are grouped as "defensive staples" in `config.py` so the portfolio
review shows current defensive exposure.

Trade-offs to weigh before rotating:
- **Leverage first.** For this portfolio, the highest-impact defensive move is
  trimming the daily-reset leverage (its decay and drawdown dominate the risk),
  not adding staples around it. Run `lookthrough` and `decay`.
- **You will be early or late.** Rotating defensively gives up upside if the
  expansion continues; staying gives up capital if it doesn't. Size the move to
  how strong the cluster of signals is, not to a single scary headline.
- **Taxes.** Rotating in the taxable brokerage realizes gains; the Roth/401k are
  the cheaper places to change allocation.

## Workflow
`pulse` (read the regime) → if the cluster leans defensive, `portfolio` (see
current defensive vs high-beta exposure) → `value`/`screen` (vet specific
defensive names) → decide. The tools inform; you pull the trigger.
