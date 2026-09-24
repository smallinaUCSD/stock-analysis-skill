"""Portfolio market risk and hedge sizing.

Beta-weighted exposure: each position's dollars times its beta against an index
(S&P 500 or Nasdaq-100) gives "index-equivalent dollars": how many dollars of the
index it moves like. Summed, that's the portfolio's market exposure; divided by
the portfolio value, its beta. A leveraged fund's measured beta already carries
its leverage (a 3x Nasdaq fund shows a beta near 3 against the Nasdaq).

Hedge sizing is the arithmetic of offsetting part of that exposure with an
instrument of known beta: dollars = fraction * exposure / |instrument beta|.
Inverse funds reset daily, so held for weeks they drift from their multiple;
``reset_drag`` measures how much that cost over a past window.

Analysis only: nothing here places or recommends a trade.
"""

from __future__ import annotations


def portfolio_beta(positions: list[tuple[str, float]], betas: dict[str, float | None],
                   cash: float = 0.0) -> dict:
    """Beta-weighted exposure of ``positions`` [(ticker, dollars)] plus cash (beta 0).

    Positions without a beta are listed in ``missing`` and left out of the
    exposure (never guessed). Returns {total, invested, exposure, beta, rows,
    missing}; rows are sorted by the size of their exposure."""
    merged: dict[str, float] = {}
    for t, v in positions:
        if v:
            merged[t] = merged.get(t, 0.0) + float(v)
    invested = sum(merged.values())
    total = invested + (cash or 0.0)
    rows, missing, exposure = [], [], 0.0
    for t, v in merged.items():
        b = betas.get(t)
        if b is None:
            missing.append(t)
            continue
        exp = v * b
        exposure += exp
        rows.append({"ticker": t, "value": v, "beta": b, "exposure": exp})
    gross = sum(abs(r["exposure"]) for r in rows) or 1.0
    for r in rows:
        r["share"] = abs(r["exposure"]) / gross
    rows.sort(key=lambda r: abs(r["exposure"]), reverse=True)
    return {"total": total, "invested": invested, "cash": cash or 0.0,
            "exposure": exposure, "beta": (exposure / total) if total else None,
            "rows": rows, "missing": sorted(missing)}


def hedge_plan(exposure: float, fraction: float, instruments: list[dict]) -> list[dict]:
    """Size each instrument to offset ``fraction`` of ``exposure`` (index dollars).

    ``instruments``: [{ticker, label, beta, price}] with betas measured against
    the same index. A negative-beta (inverse) fund is BOUGHT; a positive-beta
    index fund is SHORTED. Returns [{ticker, label, action, dollars, shares}]."""
    target = max(0.0, min(1.0, fraction)) * max(0.0, exposure)
    out = []
    for ins in instruments:
        b = ins.get("beta")
        if not b:
            continue
        dollars = target / abs(b)
        price = ins.get("price")
        out.append({"ticker": ins["ticker"], "label": ins.get("label", ""),
                    "action": "Buy" if b < 0 else "Short", "beta": b,
                    "dollars": dollars,
                    "shares": (dollars / price) if price else None})
    return out


def put_contracts(exposure: float, fraction: float, index_price: float,
                  delta: float = 0.5) -> float | None:
    """How many index put contracts (100 shares each) offset ``fraction`` of the
    exposure at a given put delta (0.5 = at the money). Approximate: delta
    changes as the index moves."""
    if not index_price or index_price <= 0 or delta <= 0:
        return None
    target = max(0.0, min(1.0, fraction)) * max(0.0, exposure)
    return target / (delta * index_price * 100.0)


def reset_drag(fund_closes, index_closes, multiplier: float) -> dict | None:
    """What a daily-reset fund actually returned vs ``multiplier`` times the
    index's return over the same (aligned) window: {actual, naive, drag}.
    ``drag`` = actual - naive (negative = the reset cost you)."""
    f, i = list(fund_closes or []), list(index_closes or [])
    n = min(len(f), len(i))
    if n < 20 or not f[-n] or not i[-n]:
        return None
    actual = f[-1] / f[-n] - 1.0
    naive = multiplier * (i[-1] / i[-n] - 1.0)
    return {"actual": actual, "naive": naive, "drag": actual - naive}
