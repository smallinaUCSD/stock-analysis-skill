"""Industry peer groups from SEC industry codes (SIC): peer valuation multiples
and a bottom-up industry beta.

Peers are the other watchlist companies sharing the most specific SIC prefix
(4, then 3 digits) that has at least ``min_group`` members. A single
stock's beta is noisy; Damodaran's bottom-up approach averages the peers'
betas with each one's debt stripped out ("unlevered"), then adds back this
company's own debt:

    beta_unlevered = beta / (1 + (1 - tax) * debt / equity)
    beta_company   = median(peers' beta_unlevered) * (1 + (1 - tax) * debt / equity)

Pure functions; debt is net debt floored at zero, equity is market cap.
"""

from __future__ import annotations

from statistics import median

TAX = 0.21


def group_of(ticker: str, sics: dict, min_group: int = 3) -> tuple[list[str], str | None]:
    """(peers including ``ticker``, SIC prefix used) or ([], None)."""
    code = str(sics.get(ticker) or "")
    if len(code) < 2:
        return [], None
    for n in (4, 3):                    # 2-digit groups are too broad (cars with aircraft)
        if len(code) < n:
            continue
        pre = code[:n]
        members = sorted(t for t, c in sics.items() if str(c or "").startswith(pre))
        if len(members) >= min_group:
            return members, pre
    return [], None


def _de(snap) -> float:
    mc = getattr(snap, "market_cap", None)
    nd = getattr(snap, "net_debt", None) or 0.0
    return max(nd, 0.0) / mc if mc else 0.0


def multiples_of(snap) -> dict:
    """P/E, EV/EBITDA and price/sales for one company (None when not meaningful)."""
    price, eps = getattr(snap, "price", None), getattr(snap, "eps", None)
    mc, nd = getattr(snap, "market_cap", None), getattr(snap, "net_debt", None) or 0.0
    ebitda, rev = getattr(snap, "ebitda", None), getattr(snap, "revenue", None)
    pe = price / eps if (price and eps and eps > 0) else None
    ev_e = (mc + nd) / ebitda if (mc and ebitda and ebitda > 0) else None
    ps = mc / rev if (mc and rev and rev > 0) else None
    return {"pe": pe if pe and pe < 200 else None,
            "ev_ebitda": ev_e if ev_e and 0 < ev_e < 100 else None,
            "ps": ps if ps and ps < 50 else None}


def peer_context(ticker: str, sics: dict, snaps: dict, betas: dict,
                 min_group: int = 3) -> dict | None:
    """Peer multiples (medians, excluding the company itself) and the relevered
    industry beta for ``ticker``. None when it has no peer group."""
    members, pre = group_of(ticker, sics, min_group)
    if not members:
        return None
    others = [t for t in members if t != ticker and snaps.get(t) is not None]
    out = {"group": pre, "peers": others}
    for k in ("pe", "ev_ebitda", "ps"):
        vals = [m[k] for m in (multiples_of(snaps[t]) for t in others) if m[k] is not None]
        out[k] = median(vals) if len(vals) >= min_group - 1 else None
    unlev = []
    for t in members:
        b, s = betas.get(t), snaps.get(t)
        if b is None or s is None:
            continue
        unlev.append(b / (1.0 + (1.0 - TAX) * _de(s)))
    own = snaps.get(ticker)
    out["beta"] = (median(unlev) * (1.0 + (1.0 - TAX) * _de(own))
                   if len(unlev) >= min_group and own is not None else None)
    return out
