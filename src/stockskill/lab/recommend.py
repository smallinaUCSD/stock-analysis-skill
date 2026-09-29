"""Ideas for one account: stocks worth adding given what they already watch,
and politicians and funds worth following (whose trades or holdings overlap
theirs). Scores are simple, explained blends, each idea with its reasons.

Two styles for stocks:
* ``similar``: more of what they like (same industries and sectors), of
  good quality, that funds hold and politicians have been buying;
* ``diversify``: good-quality companies in areas they don't hold yet that
  move least like their list.
"""

from __future__ import annotations

from collections import Counter


def _pct_ranks(rows: list[dict], key: str, higher_better: bool = True) -> dict:
    vals = sorted(r[key] for r in rows if isinstance(r.get(key), (int, float)))
    if not vals:
        return {}
    n = len(vals)
    out = {}
    for r in rows:
        v = r.get(key)
        if isinstance(v, (int, float)):
            import bisect
            p = bisect.bisect_left(vals, v) / max(1, n - 1)
            out[r["ticker"]] = p if higher_better else 1 - p
    return out


def quality(rows: list[dict]) -> dict:
    """0..1 per ticker: growth, margins, returns on equity, cash yield, a sane P/E."""
    parts = [_pct_ranks(rows, "rev_growth"), _pct_ranks(rows, "net_margin"), _pct_ranks(rows, "roe"),
             _pct_ranks(rows, "fcf_yield"),
             _pct_ranks([r for r in rows if (r.get("pe") or 0) > 0], "pe", higher_better=False)]
    out = {}
    for r in rows:
        got = [p[r["ticker"]] for p in parts if r["ticker"] in p]
        if len(got) >= 2:
            out[r["ticker"]] = sum(got) / len(got)
    return out


def stocks(watch: list[str], universe: list[dict], *, style: str = "similar", fund_holders: dict | None = None,
           politician_buys: dict | None = None, corr=None, limit: int = 12, min_mcap: float = 2e9) -> list[dict]:
    """[{ticker, name, sector, industry, score, reasons}] best first.
    ``fund_holders``/``politician_buys``: {ticker: count}; ``corr(ticker)``: mean
    correlation with the watchlist (or None when prices aren't cached)."""
    mine = {t.upper() for t in watch}
    by_t = {r["ticker"]: r for r in universe if r.get("ticker")}
    held = [by_t[t] for t in mine if t in by_t]
    ind = Counter(r.get("industry") for r in held if r.get("industry"))
    sec = Counter(r.get("sector") for r in held if r.get("sector"))
    n_held = max(1, len(held))
    pool = [r for r in universe if r.get("ticker") not in mine and (r.get("mcap") or 0) >= min_mcap
            and r.get("sector") and r.get("price")]
    q = quality(pool)
    fund_holders, politician_buys = fund_holders or {}, politician_buys or {}
    scored = []
    for r in pool:
        t = r["ticker"]
        same_ind, same_sec = ind.get(r.get("industry"), 0), sec.get(r.get("sector"), 0)
        affinity = min(1.0, (same_ind + 0.5 * same_sec) / n_held * 3)
        social = min(1.0, fund_holders.get(t, 0) / 4 + politician_buys.get(t, 0) / 3)
        qual = q.get(t, 0.4)
        if style == "diversify":
            base = 0.4 * (1 - min(1.0, same_sec / n_held * 3)) + 0.4 * qual + 0.2 * social
        else:
            base = 0.45 * affinity + 0.35 * qual + 0.2 * social
        scored.append((base, r, affinity, social, qual))
    scored.sort(key=lambda x: -x[0])
    top = scored[:max(limit * 4, 40)]                        # correlation only for the front-runners (it loads prices)
    out = []
    for base, r, affinity, social, qual in top:
        t = r["ticker"]
        c = corr(t) if corr else None
        score = base
        if c is not None:
            score += (0.25 * (1 - max(c, 0)) if style == "diversify" else 0.05 * max(c, 0))
        reasons = []
        peers = [h["ticker"] for h in held if h.get("industry") == r.get("industry")][:3]
        if style != "diversify" and peers:
            reasons.append(f"Same industry as {', '.join(peers)}")
        elif style == "diversify" and not sec.get(r.get("sector")):
            reasons.append(f"Adds {r['sector']}, which you don't hold")
        if qual >= 0.7:
            bits = []
            if isinstance(r.get("rev_growth"), (int, float)) and r["rev_growth"] > 0.1:
                bits.append(f"revenue up {r['rev_growth'] * 100:.0f}%")
            if isinstance(r.get("net_margin"), (int, float)) and r["net_margin"] > 0.15:
                bits.append(f"{r['net_margin'] * 100:.0f}% net margin")
            reasons.append("Strong business" + (f" ({', '.join(bits)})" if bits else ""))
        if fund_holders.get(t):
            reasons.append(f"Held by {fund_holders[t]} tracked fund{'s' if fund_holders[t] > 1 else ''}")
        if politician_buys.get(t):
            reasons.append(f"Bought by {politician_buys[t]} politician{'s' if politician_buys[t] > 1 else ''} this year")
        if c is not None and style == "diversify" and c < 0.4:
            reasons.append(f"Moves little like your list (correlation {c:.2f})")
        out.append({"ticker": t, "name": r.get("name"), "sector": r.get("sector"), "industry": r.get("industry"),
                    "mcap": r.get("mcap"), "score": round(score, 3), "reasons": reasons or ["Solid all-round fit"]})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def funds_to_follow(watch: list[str], reports: list[dict], limit: int = 5) -> list[dict]:
    """Funds whose latest holdings overlap your watchlist most (by weight)."""
    mine = {t.upper() for t in watch}
    out = []
    for rep in reports:
        hs = [h for h in rep.get("holdings") or [] if h.get("ticker") in mine and not h.get("put_call")]
        if not hs:
            continue
        w = sum(h.get("weight") or 0 for h in hs)
        names = [h["ticker"] for h in sorted(hs, key=lambda h: -(h.get("weight") or 0))][:4]
        out.append({"cik": rep.get("cik"), "fund": rep.get("fund"), "manager": rep.get("manager"),
                    "overlap": len(hs), "weight": round(w, 4),
                    "reason": f"{len(hs)} of your stocks ({', '.join(names)}) are {w * 100:.0f}% of its portfolio"})
    out.sort(key=lambda x: (-x["weight"], -x["overlap"]))
    return out[:limit]


def politicians_to_follow(watch: list[str], trades: list[dict], member_id, limit: int = 5) -> list[dict]:
    """Politicians who traded the most of your stocks in the trades given."""
    mine = {t.upper() for t in watch}
    hits: dict = {}
    for t in trades:
        tk = (t.get("ticker") or "").upper()
        if tk not in mine:
            continue
        pid = member_id(t)
        if not pid:
            continue
        h = hits.setdefault(pid, {"id": pid, "name": t.get("member"), "tickers": Counter(), "n": 0})
        h["tickers"][tk] += 1
        h["n"] += 1
    out = []
    for h in sorted(hits.values(), key=lambda h: (-len(h["tickers"]), -h["n"]))[:limit]:
        tks = [t for t, _ in h["tickers"].most_common(4)]
        out.append({"id": h["id"], "name": h["name"], "trades": h["n"], "stocks": len(h["tickers"]),
                    "reason": f"Traded {len(h['tickers'])} of your stocks ({', '.join(tks)}) {h['n']} times"})
    return out
