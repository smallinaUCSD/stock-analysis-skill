# Trading & valuation models — research-grounded upgrades

A sourced plan for improving the **DCF valuation** and the **entry / stop / target**
models, plus complementary strategies worth having on the dashboard. Every model
here stays true to the project's rules: the math is tested pure Python, data is
fetched separately, outputs are **probabilities and ranges, never advice**, and
we say plainly where a model's estimates are fragile.

> Two different "Kellys": **Bryan Kelly** (Kelly-Malamud-Zhou, *Virtue of
> Complexity*) is about predicting the *market's* return — a timing overlay.
> **John Kelly's criterion** is a *position-sizing* rule. Both appear below, in
> different places.

---

## 1. DCF — from a point estimate to a distribution

### Monte Carlo DCF (probabilistic valuation)  ·  Damodaran
**Today:** point inputs (growth, margin, discount rate, terminal) → one fair
value, plus a discrete bear/base/bull range and a confidence gate.

**Upgrade:** treat the key inputs as **distributions** and simulate:

- Draw each path's inputs: revenue growth `g ~ D_g` (clamped, fading toward a
  terminal), FCF margin `m ~ D_m`, discount rate `r ~ D_r` (or fixed with a
  floor), terminal growth / exit multiple `~ D_T`.
- Project FCF over the horizon → terminal value → discount → **equity value per
  share** for that path.
- Repeat K times → a **fair-value distribution**. Report expected & median fair
  value, p5/p25/p75/p95 bands, and **P(undervalued) = P(fair value > price)**.

This generalizes the current 3-point scenarios (which are three discrete draws)
into a full distribution, and reuses the existing Monte Carlo machinery. It turns
"worth $X" into "worth **$X ± range**, with an **N% chance** it's above today's
price." Surface it in the analyzer and the card modal alongside the existing
bear/base/bull table.

**Caveats:** the output is only as honest as the input distributions — show them.
Inputs correlate (high growth ↔ margin pressure or capex); model that or note it.
Garbage in, garbage out; this quantifies *assumed* uncertainty, not truth.

**Secondary (lower priority):** re-tune the opt-in **growth fade** toward a
GDP/risk-free terminal (currently off — an over-aggressive fade pushed values
~50% low); a bottom-up **cost of capital** instead of the CAPM + 8% floor.

---

## 2. Entry / stop / target

### 2a. Position sizing: fractional Kelly + volatility targeting
**Today:** fixed **2%-risk** per trade, 25% position cap (`ACCOUNT_SIZE`).

**Kelly criterion** — the fraction of capital that maximizes long-run growth:
- Discrete bet: `f* = (p·b − (1−p)) / b = edge / odds`, where `p` = win
  probability and `b` = reward/risk (your target/stop R:R).
- Continuous returns: `f* = μ / σ²` (the Merton fraction).
- **Use half-Kelly** (`0.5·f*`) and cap it — full Kelly is very high-variance.

**Volatility targeting** — Moreira & Muir, *Volatility-Managed Portfolios*
(J. Finance 2017): scale exposure `∝ target_vol / realized_vol`, i.e. take *less*
risk when the name's vol is high. Raises Sharpe because vol is more forecastable
than return. Combine: Kelly sets the base fraction, vol-targeting modulates it.

**Upgrade:** show **three sizes side by side** — fixed 2%-risk, half-Kelly, and
vol-targeted — so the user sees the trade framed three ways rather than one.

**Caveats:** `p` and `μ` are *estimates*; a wrong edge makes Kelly dangerous.
If the estimated edge is ≤ 0, Kelly says **don't take the trade** — surface that.
Vol targeting delevers into crashes and relevers after (path-dependent).

### 2b. Evidence-based stops  ·  Kaminski & Lo
*When Do Stop-Loss Rules Stop Losses?* (J. Financial Markets 2014): a stop
**adds value under momentum but subtracts it under a random walk / mean
reversion** — a fixed 2×ATR stop applied blindly can quietly cost return by
locking in noise and missing the rebound.

**Today:** a fixed 2×ATR stop, always.

**Upgrade:** make the stop **evidence-based** — report the name's momentum/trend
state and whether a stop is likely to *help or hurt* there, and **backtest the
stop** on the name's own history (buy-hold vs stop-and-reenter, risk-adjusted).
Reuses the `factors/backtest.py` engine. Offer a trailing-stop variant.

**Caveats:** in-sample; ignores transaction costs and whipsaw — state both.

### 2c. Principled entry/exit: the Dai–Zhang–Zhu trend rule
*Trend Following Trading under a Regime-Switching Model* (SIAM J. Fin. Math 2010)
/ *Optimal Trend Following Trading Rules* (Math. of OR 2016). Model the price as
`dS/S = μ(t)dt + σ dW` where the drift `μ` switches between a **bull** state
(`μ₁ > 0`) and a **bear** state (`μ₂ < 0`) via a hidden 2-state Markov chain. The
bull probability `p(t)` given the price path comes from the Wonham filter, and
the **optimal rule buys when `p` rises through an upper threshold and sells when
it falls through a lower one** — catch the trend early, exit at the first real
evidence of reversal. Thresholds come from a free-boundary (HJB) solve and depend
on `μ₁, μ₂, σ`, the transition rates, and transaction cost.

**Today:** ad-hoc ATR-based entry; direction from the trend score.

**Upgrade:** fit a 2-state regime (means/vols + transition, via EM/HMM on
returns), run the filter for **P(bull)**, and surface entry/exit thresholds — a
real trend-following rule instead of an ad-hoc trigger. Pair it with a
**time-series-momentum** sanity check (Moskowitz-Ooi-Pedersen, *Time Series
Momentum*, JFE 2012: `signal = sign(trailing-12m return)`, vol-scaled) so a single
model isn't the only voice.

**Caveats:** the regime is *inferred*, not observed — estimation risk is the whole
game; parameters drift and thresholds are sensitive to the assumed cost. Frame
`P(bull)` and the thresholds as a **model read**, not a signal to obey. The full
free-boundary thresholds may be approximated at first (e.g. p-crossing a
calibrated band).

---

## 3. Market-level, later:  Virtue of Complexity  ·  Kelly-Malamud-Zhou
*The Virtue of Complexity in Return Prediction* (J. Finance 2024): a **complex**
model — a ridge regression over many nonlinear random features, with more
parameters than observations — predicts the **market's** next return better than
simple models, and times the market with a higher Sharpe. Would live as a
market-exposure overlay in the `pulse`/regime layer.

**Caveats:** market timing is hard; the result is **debated** (replication and
data-snooping concerns). This needs rigorous out-of-sample validation before it's
trustworthy — a later R&D item, honestly caveated, not a quick win.

---

## Build order & module map

| # | Model | Where it lands | Effort |
|---|---|---|---|
| 1 | **Monte Carlo DCF** | `valuation/` (+ montecarlo engine), analyzer + card | Medium |
| 2 | **Kelly + vol-targeted sizing** | `trade/` (extend position sizing) | Low |
| 3 | **Evidence-based stops** (Kaminski-Lo) | `trade/` + `factors/backtest.py` | Low–Med |
| 4 | **TS-momentum signal** (MOP) | `signals/` or `factors/` (building block for #5) | Low |
| 5 | **Dai-Zhang-Zhu trend rule** | new `regime/` (2-state filter) → `trade/` | High |
| 6 | **Virtue of Complexity** timing | `pulse/` overlay (R&D) | High |

Recommended: **1 → 2 → 3** (they directly upgrade the named models and reuse
engines we have), then **4 → 5** (the principled entry model), with **6** as later
research.

## References
- Damodaran, A. — *Probabilistic Approaches in Valuation* (Monte Carlo / scenario / decision trees). [stern.nyu.edu](https://pages.stern.nyu.edu/~adamodar/pdfiles/ovhds/inv2E/probabilistic.pdf)
- Kelly, J. L. (1956) — *A New Interpretation of Information Rate* (the Kelly criterion).
- Moreira, A. & Muir, T. (2017) — *Volatility-Managed Portfolios*, Journal of Finance. [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513)
- Kaminski, K. & Lo, A. (2014) — *When Do Stop-Loss Rules Stop Losses?*, Journal of Financial Markets. [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S138641811300030X)
- Dai, M., Zhang, Q. & Zhu, Q. J. (2010) — *Trend Following Trading under a Regime-Switching Model*, SIAM J. Financial Math. [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1762118)
- Dai, M., Yang, Z., Zhang, Q. & Zhu, Q. J. (2016) — *Optimal Trend Following Trading Rules*, Mathematics of Operations Research. [INFORMS](https://pubsonline.informs.org/doi/10.1287/moor.2015.0743)
- Moskowitz, T., Ooi, Y. H. & Pedersen, L. (2012) — *Time Series Momentum*, Journal of Financial Economics. [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463)
- Kelly, B., Malamud, S. & Zhou, K. (2024) — *The Virtue of Complexity in Return Prediction*, Journal of Finance. [Wiley](https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13298) · [NBER w30217](https://www.nber.org/papers/w30217)
