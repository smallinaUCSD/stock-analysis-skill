# Factor investing — methodology

How `stockskill`'s factor layer scores stocks, why each choice was made, and the
research it rests on. Everything here is computed by tested pure Python
(`src/stockskill/factors/`); the LLM never does the math.

## Why factors (not chart signals)

Technical signals (RSI, MACD, …) are functions of recent price, so they *react*
and flip whenever price flips — no independent information. **Factors** explain
returns by exposure to systematic, research-backed characteristics. They are
cross-sectional (rank the universe) and, for value especially, anchored to
fundamentals rather than price history. That's the defensible foundation.

## The factors

Each factor is a small basket of metrics. Every metric is **percentile-ranked
across the universe** (0–1), inverted when lower-is-better, then averaged into a
factor score. Percentile ranking (not z-scores) is robust to outliers and to
metrics on wildly different scales — a P/E of 400 can't blow up the score.

| Factor | Metrics (weight, direction) | Research |
|---|---|---|
| **Value** | earnings yield E/P (1, ↑), FCF yield (1, ↑), EV/EBITDA (1, ↓), sales yield (1, ↑), dividend yield (0.5, ↑) | Fama–French (1992, 1993) HML |
| **Quality** | ROE (1, ↑), profit margin (1, ↑), FCF margin (1, ↑), net-debt/EBITDA (1, ↓) | Novy-Marx (2013); Asness–Frazzini–Pedersen, *Quality Minus Junk* |
| **Momentum** | 12-1 month return (1, ↑) | Jegadeesh–Titman (1993); Carhart (1997) |
| **Growth** | revenue growth (1, ↑), earnings growth (1, ↑) | — |
| **Low-vol** | trailing-1y realized volatility (1, ↓), beta (0.5, ↓) | Frazzini–Pedersen, *Betting Against Beta* (2014) |

**12-1 momentum** = return from ~12 months ago to ~1 month ago; the most recent
month is skipped to avoid short-term reversal (Jegadeesh–Titman). Value ties to
the exact same fundamentals as `stockskill value`.

## Composite, coverage, weights

- **Composite** = weighted average of the available factor scores. Default
  weights: value 1.0, quality 1.0, momentum 1.0, growth 0.75, low-vol 0.75.
  Override with `STOCKSKILL_FACTOR_WEIGHTS="value:2,momentum:1,growth:0,…"`.
- **Coverage gate**: a name needs ≥ 50% of the composite's factor weight in data
  to receive a composite rank. Names below it (e.g. leveraged ETFs, which have
  only price-based factors) keep their individual scores but are withheld from
  the composite — a one-factor name can't spuriously top the board.
- **Missing inputs** are excluded from that name's average and reflected in
  coverage — never guessed.
- Each factor and the composite are re-expressed as **0–100 percentiles** within
  the universe for display, plus a plain-English read ("cheap · high quality").

## Sector-neutral scoring (`--sector-neutral`)

Naïve value is partly a *sector* bet — energy and telecom dominate "cheap".
Sector-neutral ranks each metric **within the name's own sector**, so "cheap"
means cheap-vs-peers. It surfaces the cheapest semiconductor, the cheapest
software name, etc., instead of a pile of energy stocks. Sectors thinner than
`min_group` (default 4) fall back to universe ranks so a lone name isn't handed a
spurious 0 or 100. The board uses sector-neutral scores.

## Backtest (`stockskill backtest`)

At each **monthly rebalance** we rank the universe by a factor, split into
buckets, and measure each bucket's **forward** return. Reported: the bucket
gradient, the **long-short spread** (top − bottom), the **hit rate** (share of
months positive), and the **information coefficient** (IC = rank correlation of
signal vs forward return). A real factor shows a monotonic gradient and a
positive IC. **No look-ahead**: the signal at date *d* uses prices up to *d*; the
return is measured strictly after *d*.

Honest finding: on the current 116-name large-cap-growth universe, momentum is
**weak** (IC ≈ 0, non-monotonic buckets, ~55% hit rate) — the universe is
survivorship-heavy (mostly winners). The tool reports that rather than
cherry-picking the headline spread. Costs and slippage are not modeled.

## The value-backtest gap (and the fix)

Momentum is price-derived, so it backtests from the 5y price history on hand.
**Value/quality can't be backtested yet** — they need *point-in-time* historical
fundamentals (what was AAPL's P/E in 2023?), and no free feed provides them.
Solution: `stockskill snapshot-fundamentals` records a dated fundamentals row
each day (`data/fundamentals_history/`), building a point-in-time panel going
forward. The backtest's `panel → run` split lets value/quality plug in unchanged
once the history accrues (or with a paid historical-fundamentals feed).

## Caveats

- **Factor decay / crowding** — published factors weaken as they're arbitraged
  (McLean & Pontiff 2016, *Does Academic Research Destroy Return Predictability?*;
  Arnott et al., *How Can "Smart Beta" Go Horribly Wrong?*). Treat scores as
  relative reads, not guarantees.
- **In-sample, fixed universe, no costs** — the backtest is illustrative, not a
  live strategy.
- **Not advice** — factor scores rank names relative to this universe; the
  decision is the user's.

## References

- Fama, E. & French, K. (1992) *The Cross-Section of Expected Stock Returns*; (1993) *Common Risk Factors*; (2015) *A Five-Factor Asset Pricing Model*.
- Jegadeesh, N. & Titman, S. (1993) *Returns to Buying Winners and Selling Losers*.
- Carhart, M. (1997) *On Persistence in Mutual Fund Performance* (momentum/4-factor).
- Novy-Marx, R. (2013) *The Other Side of Value: The Gross Profitability Premium*.
- Asness, C., Moskowitz, T. & Pedersen, L. (2013) *Value and Momentum Everywhere*.
- Asness, C., Frazzini, A. & Pedersen, L. (2019) *Quality Minus Junk*.
- Frazzini, A. & Pedersen, L. (2014) *Betting Against Beta*.
- McLean, R. D. & Pontiff, J. (2016) *Does Academic Research Destroy Stock Return Predictability?*
- **Kenneth R. French Data Library** — free daily/monthly factor return series (Mkt-RF, SMB, HML, RMW, CMA, Mom), for a future factor-exposure regression.
