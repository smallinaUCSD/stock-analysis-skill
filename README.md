# stock-analysis-skill

Reproducible stock and portfolio analysis for Claude. **The model never does
the math** — every number is produced by tested Python in the `stockskill`
package. Same inputs → same output, provable by re-running.

See [SKILL.md](SKILL.md) for how Claude uses this, and `references/` for
methodology.

## Quickstart

```bash
uv run pytest -q                       # 26 tests over the math
uv run stockskill value AAPL --growth 0.08 --peer-pe 28 --peer-ev-ebitda 20
uv run stockskill portfolio --holdings holdings.csv
uv run stockskill lookthrough --holdings holdings.csv
uv run stockskill decay --multiplier 3 --vol 0.45 --drift 0.08 --expense 0.0095
uv run stockskill screen --lane core --top 15 --cache-dir snaps
```

## What's here

| Capability | Command | Module |
|---|---|---|
| Fair value of a stock (DCF, reverse DCF, multiples, DDM) | `value` | `valuation/` |
| Rank a universe into a shortlist (core + aggressive lanes) | `screen` | `screener/` |
| True underlying exposure of leveraged/basket ETFs | `lookthrough` | `portfolio/lookthrough.py` |
| Concentration / factor / leverage review | `portfolio` | `portfolio/risk.py` |
| Leveraged-ETF volatility decay | `decay` | `portfolio/decay.py` |

## Design

- **Math and data are separate.** Pure, unit-tested functions take explicit
  numbers; the data layer (`data/`, free yfinance) feeds them. A saved snapshot
  makes any valuation reproducible offline.
- **Leverage is made visible.** The registry (`leverage/registry.py`) expands
  products like FNGU (3x basket) and AAPU (2x AAPL) into look-through exposure.
- **Guardrails:** analysis and trade-offs only, never personalized buy/sell
  advice; leveraged products always come with a decay check.

## Not yet built (roadmap)

Market Pulse (what's trending & why), Watchlist monitor, Regime/recession
playbook, Thesis journal. Market Pulse is next — it needs the live logged-in
browser sessions wired in.

## Data note

Free sources (yfinance/Yahoo) only, and paid sites (Morningstar/Barchart) are
read via your own logged-in browser when needed — no credentials are stored or
entered by the tool.
