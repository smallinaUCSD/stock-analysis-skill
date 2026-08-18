"""Live holdings state for the served dashboard.

PRIVACY: this reads/writes holdings.csv (real balances, gitignored) and is only
ever served by the local `serve` app — it is NEVER written to a static file and
NEVER published to GitHub Pages. Trades here are BOOKKEEPING to mirror what the
user already did in their brokerage; nothing is sent to any broker.

Positions carry a dollar market_value (from the CSV) plus optional shares and
cost_basis. The snapshot enriches each position with a live price and previous
close (cached briefly) to derive current value, today's gain and net gain.
Shares are inferred from market_value / price when not stored. Cash is a money-
market balance shown as Fidelity SPAXX.
"""

from __future__ import annotations

import re
import threading
import time

from ..portfolio.manage import read_rows, write_rows, HoldingRow

_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-\^]{1,12}$")
CASH = "CASH"
SPAXX = "SPAXX"   # Fidelity money-market fund used to hold cash

ACCOUNT_LABELS = {"brokerage": "Brokerage", "roth": "Roth IRA", "401k": "401(k)"}
ACCOUNT_ORDER = ["brokerage", "roth", "401k"]
_PRICE_TTL = 60.0     # seconds to reuse a fetched price map
_DIV_TTL = 3600.0     # dividends change rarely -> cache for an hour


def account_label(key: str) -> str:
    return ACCOUNT_LABELS.get(key, key or "(unlabeled)")


class HoldingsService:
    def __init__(self, path: str = "holdings.csv"):
        self._path = path
        self._lock = threading.Lock()
        self._px_cache: dict[str, tuple[float | None, float | None]] = {}
        self._px_ts = 0.0
        self._div_cache: dict[str, float | None] = {}
        self._div_ts = 0.0

    # --- read ----------------------------------------------------------
    def _rows(self) -> list[HoldingRow]:
        try:
            return read_rows(self._path)
        except OSError:
            return []

    def _prices(self, tickers: list[str]) -> dict[str, tuple[float | None, float | None]]:
        """Map ticker -> (last_price, prev_close), cached for _PRICE_TTL seconds."""
        now = time.time()
        need = [t for t in tickers if t not in self._px_cache]
        if need or now - self._px_ts > _PRICE_TTL:
            try:
                from ..data.prices import price_map
                pm = price_map(tickers, period="5d")
            except Exception:  # noqa: BLE001
                pm = {}
            cache: dict[str, tuple[float | None, float | None]] = {}
            for t in tickers:
                cl = pm.get(t) or []
                last = cl[-1] if cl else None
                prev = cl[-2] if len(cl) >= 2 else None
                cache[t] = (last, prev)
            self._px_cache = cache
            self._px_ts = now
        return self._px_cache

    def _dividends(self, tickers: list[str]) -> dict[str, float | None]:
        """Map ticker -> annual dividend per share, cached for _DIV_TTL (they
        rarely change). Fetched in parallel to keep the page responsive."""
        now = time.time()
        fresh = (self._div_cache and now - self._div_ts < _DIV_TTL
                 and all(t in self._div_cache for t in tickers))
        if fresh:
            return self._div_cache
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor

        def one(t):
            try:
                info = yf.Ticker(t).info or {}
                return t, (info.get("dividendRate") or info.get("trailingAnnualDividendRate"))
            except Exception:  # noqa: BLE001
                return t, None
        cache: dict[str, float | None] = {}
        try:
            with ThreadPoolExecutor(max_workers=6) as ex:
                for t, d in ex.map(one, tickers):
                    cache[t] = d
        except Exception:  # noqa: BLE001
            cache = {t: None for t in tickers}
        self._div_cache = cache
        self._div_ts = now
        return self._div_cache

    def snapshot(self) -> dict:
        rows = self._rows()
        tickers = sorted({r.ticker for r in rows if r.ticker != CASH})
        px = self._prices(tickers) if tickers else {}
        div = self._dividends(tickers) if tickers else {}
        accounts: dict[str, dict] = {}
        for r in rows:
            acct = r.account or "(unlabeled)"
            a = accounts.setdefault(acct, {"key": acct, "label": account_label(acct),
                                           "positions": [], "cash": 0.0})
            if r.ticker == CASH:
                a["cash"] += r.market_value or 0.0
                continue
            price, prev = px.get(r.ticker, (None, None))
            shares = r.shares
            if shares is None and price and r.market_value:
                shares = r.market_value / price
            value = (shares * price) if (shares is not None and price) else (r.market_value or 0.0)
            value = round(value, 2)   # avoid float noise from value/price*price round-trips
            today_pct = (price / prev - 1) if (price and prev) else None
            today_dollar = round(shares * (price - prev), 2) if (shares is not None and price and prev) else None
            cost = r.cost_basis
            net_pct = (price / cost - 1) if (price and cost) else None
            net_dollar = round(shares * (price - cost), 2) if (shares is not None and price and cost) else None
            cost_total = round(shares * cost, 2) if (shares is not None and cost) else None
            div_ps = div.get(r.ticker)            # annual dividend per share
            div_yield = (div_ps / price) if (div_ps and price) else None
            if shares is not None and div_ps:
                div_income = round(shares * div_ps, 2)
            elif div_yield and value:
                div_income = round(value * div_yield, 2)
            else:
                div_income = None
            a["positions"].append({
                "ticker": r.ticker, "shares": shares, "price": price,
                "cost_basis": cost, "cost_total": cost_total, "market_value": value,
                "today_pct": today_pct, "today_dollar": today_dollar,
                "net_pct": net_pct, "net_dollar": net_dollar,
                "div_yield": div_yield, "div_income": div_income,
            })

        def akey(k):
            return (ACCOUNT_ORDER.index(k) if k in ACCOUNT_ORDER else 99, k)
        out_accounts, grand_pos, grand_cash, grand_today, grand_cost, grand_div = \
            [], 0.0, 0.0, 0.0, 0.0, 0.0
        for k in sorted(accounts, key=akey):
            a = accounts[k]
            a["positions"].sort(key=lambda p: p["market_value"], reverse=True)
            pos_total = sum(p["market_value"] for p in a["positions"])
            a["positions_total"] = pos_total
            a["total"] = pos_total + a["cash"]
            a["today_dollar"] = sum(p["today_dollar"] or 0.0 for p in a["positions"])
            a["cost_total"] = sum(p["cost_total"] or 0.0 for p in a["positions"])
            a["div_income"] = sum(p["div_income"] or 0.0 for p in a["positions"])
            for p in a["positions"]:
                p["pct_of_account"] = (p["market_value"] / a["total"]) if a["total"] else 0.0
            grand_pos += pos_total
            grand_cash += a["cash"]
            grand_today += a["today_dollar"]
            grand_cost += a["cost_total"]
            grand_div += a["div_income"]
            out_accounts.append(a)
        return {
            "accounts": out_accounts,
            "grand_total": grand_pos + grand_cash,
            "grand_positions": grand_pos,
            "grand_cash": grand_cash,
            "grand_today_dollar": grand_today,
            "grand_cost_basis": grand_cost,
            "grand_div_income": grand_div,
            "cash_symbol": SPAXX,
        }

    def _current_price(self, ticker: str) -> float | None:
        try:
            from ..data.prices import closing_prices
            cl = closing_prices(ticker, "5d")
            return cl[-1] if cl else None
        except Exception:  # noqa: BLE001
            return None

    # --- write helpers -------------------------------------------------
    def _find(self, rows, ticker, account):
        for r in rows:
            if r.ticker == ticker and r.account == account:
                return r
        return None

    def _cash_row(self, rows, account) -> HoldingRow:
        r = self._find(rows, CASH, account)
        if r is None:
            r = HoldingRow(CASH, account, None, 0.0)
            rows.append(r)
        if r.market_value is None:
            r.market_value = 0.0
        return r

    # --- mutations -----------------------------------------------------
    def trade(self, ticker: str, account: str, side: str, amount: float,
              settle_cash: bool = True, price: float | None = None) -> dict:
        ticker = (ticker or "").strip().upper()
        account = (account or "").strip()
        if not _TICKER_RE.match(ticker) or ticker == CASH:
            return {"ok": False, "error": f"invalid ticker '{ticker}'"}
        if not account:
            return {"ok": False, "error": "account is required"}
        if side not in ("buy", "sell"):
            return {"ok": False, "error": "side must be buy|sell"}
        if not amount or amount <= 0:
            return {"ok": False, "error": "amount must be a positive dollar value"}
        if price is not None and price <= 0:
            price = None
        with self._lock:
            rows = self._rows()
            pos = self._find(rows, ticker, account)
            if side == "buy":
                if pos is None:
                    pos = HoldingRow(ticker, account, None, 0.0)
                    rows.append(pos)
                if price:
                    # reconcile a legacy dollar-only position into shares first,
                    # so an added priced lot doesn't drop the existing value
                    if pos.shares is None and (pos.market_value or 0) > 0:
                        cur = self._current_price(ticker)
                        if cur:
                            pos.shares = (pos.market_value or 0.0) / cur
                            if pos.cost_basis is None:
                                pos.cost_basis = cur
                    add_sh = amount / price
                    old_sh = pos.shares or 0.0
                    old_cost = pos.cost_basis or price
                    new_sh = old_sh + add_sh
                    pos.cost_basis = (old_sh * old_cost + amount) / new_sh if new_sh else price
                    pos.shares = new_sh
                pos.market_value = (pos.market_value or 0.0) + amount
            else:  # sell
                if pos is None or (pos.market_value or 0.0) <= 0:
                    return {"ok": False, "error": f"no {ticker} position in {account_label(account)} to sell"}
                pos.market_value = (pos.market_value or 0.0) - amount
                if price and pos.shares:
                    pos.shares = max(0.0, pos.shares - amount / price)
                if pos.market_value <= 1e-6:
                    rows.remove(pos)
            note = ""
            if settle_cash:
                cash = self._cash_row(rows, account)
                cash.market_value += amount if side == "sell" else -amount
                if cash.market_value < 0:
                    note = "cash is now negative; deposit to reconcile"
            write_rows(self._path, rows)
        self._px_ts = 0.0   # force a price refresh on next snapshot
        return {"ok": True, "ticker": ticker, "account": account, "side": side,
                "amount": amount, "note": note}

    def cash(self, account: str, direction: str, amount: float) -> dict:
        account = (account or "").strip()
        if not account:
            return {"ok": False, "error": "account is required"}
        if direction not in ("deposit", "withdraw"):
            return {"ok": False, "error": "direction must be deposit|withdraw"}
        if not amount or amount <= 0:
            return {"ok": False, "error": "amount must be a positive dollar value"}
        with self._lock:
            rows = self._rows()
            cash = self._cash_row(rows, account)
            cash.market_value += amount if direction == "deposit" else -amount
            note = "cash is now negative" if cash.market_value < 0 else ""
            write_rows(self._path, rows)
        return {"ok": True, "account": account, "direction": direction,
                "amount": amount, "balance": cash.market_value, "note": note}
