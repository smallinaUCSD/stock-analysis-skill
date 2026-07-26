# Portfolio review checklist

Run `stockskill portfolio --holdings holdings.csv` and read the output against
these. Thresholds are rules of thumb to prompt thought, not hard limits.

## 1. True (look-through) leverage
- `effective_leverage` = economic exposure / equity. 1.0 is unlevered.
- Anything meaningfully above 1.2–1.3x across the *whole* portfolio means a
  down market hits harder than the account balance suggests.

## 2. Concentration
- **HHI**: <0.10 fairly diversified; 0.15–0.25 concentrated; >0.25 very
  concentrated.
- **Effective number of bets** (1/HHI): a portfolio of 15 tickers with an
  effective count of 3 is really 3 bets wearing a costume.
- **Top-5 exposure share**: >50% concentrated; >70% is a few names deciding
  your net worth.

## 3. Factor / sector overlap
- Look at the factor-group table. If one group (e.g. mega-cap platform) is a
  large share across *every* account, your accounts aren't diversifying each
  other — a growth-factor drawdown hits all of them at once.

## 4. Account / asset location
- Highest-expected-return, highest-tax-drag assets are usually best in a Roth
  (tax-free growth); tax-inefficient or high-turnover holdings least suited to
  taxable. Flag when the aggressive sleeve sits in taxable while tax-free space
  holds conservative funds — that's location working against you.
- This is an observation to surface, not an instruction to move anything.

## 5. Cash & regime
- Note dry powder (cash %) available to deploy on drawdowns.
- If the user tracks a recession playbook, this is where defensive-rotation
  candidates (staples, low-beta) would enter — as options with trade-offs.

## What NOT to do
- Don't produce a "sell this, buy that" list. Quantify the risks and let the
  user decide.
- Don't trust the numbers if market values are stale — they're only as real as
  the holdings file.
