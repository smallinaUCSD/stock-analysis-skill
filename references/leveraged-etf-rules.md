# Leveraged & single-stock ETF rules

These products (FNGU, BULZ, SOXL, AAPU, MSFU, METU, TSLL, CONL, PTIR, …)
deliver a multiple of the **daily** return, then reset. Over more than one day
the outcome is path-dependent, and the math is unforgiving in choppy markets.

## Why they decay (run `stockskill decay` to quantify, don't assert)
Because leverage compounds daily, a flat-but-volatile underlying still bleeds
the fund. Example (from the model): 3x, 45% vol, 0% drift over a year →
underlying roughly flat, but the **median leveraged return is deeply negative**
and P(losing money) is well above 50%. Leverage only compounds *for* you in a
smooth, strong uptrend. Sideways-and-violent is the worst case, and mega-cap
tech has plenty of violent stretches.

## Practical discipline (frameworks, not instructions to execute)
- **Size for the drawdown, not the dream.** A 3x fund can fall 60–90% in a bad
  year even if the underlying only falls 20–30%. Position so that outcome is
  survivable.
- **These are trades, not holdings.** The "buy and hold forever" logic that
  works for index funds actively works *against* you here. Have an exit and
  re-entry rule.
- **Watch look-through leverage, not position count.** Ten leveraged single-
  stock funds on correlated mega-cap tech is one leveraged bet, not ten. Use
  `stockskill lookthrough`.
- **Expense + financing drag is real.** These carry ~1% expense ratios plus
  embedded financing cost; feed `--expense` to the decay model.
- **ETN vs ETF.** FNGU/BULZ are ETNs — unsecured notes carrying issuer credit
  risk and call/acceleration features, on top of the leverage risk.

## Concentration reality
When a large share of net worth sits in correlated leveraged tech, the whole
portfolio behaves like a single high-beta position. The portfolio review
exists to make that impossible to ignore; look at effective leverage and the
factor-group table, not the comfort of a long ticker list.
