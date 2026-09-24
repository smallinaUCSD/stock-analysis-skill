"""Options snapshot from yfinance: near-term ATM put/call + implied-vol skew.

Pure display data -- no strategy, no recommendation. Summarizes the nearest
expiry's at-the-money call and put and a simple put/call implied-vol skew
(a rough gauge of how much the market is paying for downside protection).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OptionQuote:
    strike: float
    last_price: float | None
    implied_vol: float | None


@dataclass
class OptionsSnapshot:
    expiry: str | None = None
    spot: float | None = None
    atm_call: OptionQuote | None = None
    atm_put: OptionQuote | None = None
    put_call_iv_skew: float | None = None   # put IV - call IV (positive = downside bid up)
    available: bool = False
    note: str = ""


def _nearest_row(df, spot: float):
    """Row whose strike is closest to spot."""
    if df is None or df.empty:
        return None
    idx = (df["strike"] - spot).abs().idxmin()
    return df.loc[idx]


def fetch_options_snapshot(ticker: str, spot: float | None = None) -> OptionsSnapshot:
    """Nearest-expiry ATM call/put and IV skew. Best-effort; may be empty."""
    import yfinance as yf

    try:
        t = yf.Ticker(ticker)
        expiries = t.options
        if not expiries:
            return OptionsSnapshot(available=False, note="no listed options")
        expiry = expiries[0]
        chain = t.option_chain(expiry)
        if spot is None:
            fi = t.fast_info
            spot = getattr(fi, "last_price", None)
        if spot is None:
            return OptionsSnapshot(expiry=expiry, available=False, note="no spot price")

        call_row = _nearest_row(chain.calls, spot)
        put_row = _nearest_row(chain.puts, spot)

        def quote(row):
            if row is None:
                return None
            return OptionQuote(
                strike=float(row["strike"]),
                last_price=float(row["lastPrice"]) if row.get("lastPrice") is not None else None,
                implied_vol=float(row["impliedVolatility"]) if row.get("impliedVolatility") is not None else None,
            )

        atm_call = quote(call_row)
        atm_put = quote(put_row)
        skew = None
        if atm_put and atm_call and atm_put.implied_vol is not None and atm_call.implied_vol is not None:
            skew = atm_put.implied_vol - atm_call.implied_vol

        return OptionsSnapshot(
            expiry=expiry, spot=spot, atm_call=atm_call, atm_put=atm_put,
            put_call_iv_skew=skew, available=True,
        )
    except Exception as e:  # noqa: BLE001
        return OptionsSnapshot(available=False, note=f"fetch failed: {e}")


def expected_moves(ticker: str, spot: float, earnings: str | None = None,
                   today=None) -> dict:
    """Options-implied moves to a few upcoming expiries (next week, ~a month,
    through earnings), from at-the-money straddle prices on Yahoo's chains.

    {"available", "moves": [{label, expiry, days, strike, straddle, move_pct,
    low, high, iv, source}], "stale", "note"}. Best-effort; never raises."""
    from datetime import date

    from ..trade.expected_move import option_price, pick_expiries, straddle_move
    import yfinance as yf

    today = today or date.today()
    try:
        t = yf.Ticker(ticker)
        chosen = pick_expiries(t.options, today, earnings)
    except Exception as e:  # noqa: BLE001
        return {"available": False, "moves": [], "note": f"options unavailable ({e})"}
    if not chosen:
        return {"available": False, "moves": [], "note": "no listed options"}
    moves, stale = [], False
    for label, exp in chosen:
        try:
            ch = t.option_chain(exp)
            c, p = _nearest_row(ch.calls, spot), _nearest_row(ch.puts, spot)
            if c is None or p is None:
                continue
            cp, cs = option_price(c.get("bid"), c.get("ask"), c.get("lastPrice"))
            pp, ps = option_price(p.get("bid"), p.get("ask"), p.get("lastPrice"))
            y, m, d = (int(x) for x in exp.split("-"))
            days = (date(y, m, d) - today).days
            mv = straddle_move(spot, cp, pp, days)
            if not mv:
                continue
            src = "mid" if (cs == "mid" and ps == "mid") else "last trade"
            stale = stale or src != "mid"
            mv.update({"label": label, "expiry": exp, "days": days,
                       "strike": float(c["strike"]), "source": src})
            moves.append(mv)
        except Exception:  # noqa: BLE001
            continue
    return {"available": bool(moves), "moves": moves, "stale": stale,
            "note": ("Priced from last trades (the market is closed), so treat these as "
                     "approximate." if stale else "")}


def chain_near(ticker: str, spot: float, target_days: int = 35, today=None) -> dict | None:
    """The option chain for the expiry closest to ``target_days`` out (21-60
    days): {expiry, days, calls, puts, stale}. Prices are bid/ask midpoints, or
    the last trade when the market is closed (``stale``)."""
    from datetime import date

    from ..trade.expected_move import option_price
    import yfinance as yf

    today = today or date.today()
    try:
        t = yf.Ticker(ticker)
        exps = []
        for e in t.options or []:
            y, m, d = (int(x) for x in e.split("-"))
            n = (date(y, m, d) - today).days
            if 21 <= n <= 60:
                exps.append((abs(n - target_days), n, e))
        if not exps:
            return None
        _, days, exp = min(exps)
        ch = t.option_chain(exp)
    except Exception:  # noqa: BLE001
        return None
    stale = False

    def rows(df):
        nonlocal stale
        out = []
        for _, r in df.iterrows():
            k = float(r["strike"])
            if not (0.5 * spot <= k <= 1.6 * spot):
                continue
            px, src = option_price(r.get("bid"), r.get("ask"), r.get("lastPrice"))
            if px is None:
                continue
            stale = stale or src != "mid"
            out.append({"strike": k, "price": round(px, 2)})
        return out
    return {"expiry": exp, "days": days, "calls": rows(ch.calls), "puts": rows(ch.puts), "stale": stale}
