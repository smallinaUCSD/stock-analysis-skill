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
