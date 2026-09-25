"""Phone alerts through ntfy.sh (free, no account): price levels, big daily
moves, watchlist breakouts, insider purchases and next-day earnings.

Setup: install the ntfy app, subscribe to a hard-to-guess topic name, and put
the same name in ``NTFY_TOPIC``. Anyone who knows the topic can read it, so
treat it like a password (it lives in .env, never in the repo).

Rules, the fired-alert log and dedupe state are one JSON document kept where
the added tickers are: ``STOCKSKILL_ALERTS_FILE``, else Upstash (so a cloud
instance sees the same rules), else ``data/phone_alerts.json``.

``evaluate_prices`` and the event builders are pure (tested); ``Checker`` runs
them on a schedule and ``send`` publishes.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
import uuid
from datetime import date, datetime, timedelta

TYPES = {
    "price_above": "Price rises to",
    "price_below": "Price falls to",
    "move": "Moves in a day by",
    "breakout": "Watchlist breakouts",
    "insider_buy": "Insider purchases on the watchlist",
    "earnings": "Watchlist earnings the next trading day",
}
_KEY = "stockskill:alerts"
_LOG_MAX = 60


# --- storage ----------------------------------------------------------------

def _file_path() -> str | None:
    p = os.environ.get("STOCKSKILL_ALERTS_FILE")
    if p:
        return p
    from ..server.added_store import _cfg
    return None if _cfg()[0] else "data/phone_alerts.json"


def _empty() -> dict:
    return {"rules": [], "log": [], "state": {}}


def load() -> dict:
    path = _file_path()
    data = None
    if path:
        try:
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
        except Exception:  # noqa: BLE001
            data = None
    else:
        from ..server.added_store import _cfg
        url, token = _cfg()
        try:
            import requests
            r = requests.get(f"{url}/get/{_KEY}", headers={"Authorization": f"Bearer {token}"}, timeout=8)
            val = r.json().get("result") if r.status_code == 200 else None
            data = json.loads(val) if val else None
        except Exception:  # noqa: BLE001
            data = None
    out = _empty()
    if isinstance(data, dict):
        out.update({k: data.get(k) or out[k] for k in out})
    return out


def save(doc: dict) -> bool:
    doc["log"] = (doc.get("log") or [])[-_LOG_MAX:]
    # dedupe keys older than two weeks are no longer needed
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    doc["state"] = {k: v for k, v in (doc.get("state") or {}).items()
                    if not (k.startswith(("bo:", "ins:", "er:", "mv:")) and str(v)[:10] < cutoff)}
    path = _file_path()
    if path:
        try:
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(path, "w") as f:
                json.dump(doc, f)
            return True
        except Exception:  # noqa: BLE001
            return False
    from ..server.added_store import _cfg
    url, token = _cfg()
    try:
        import requests
        r = requests.post(f"{url}/set/{_KEY}", data=json.dumps(doc),
                          headers={"Authorization": f"Bearer {token}"}, timeout=8)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


_DOC_LOCK = threading.Lock()


def new_rule(kind: str, ticker: str | None = None, value: float | None = None) -> dict:
    """Validated rule dict; raises ValueError on bad input."""
    if kind not in TYPES:
        raise ValueError("unknown alert type")
    rule = {"id": uuid.uuid4().hex[:10], "type": kind, "on": True, "created": date.today().isoformat()}
    if kind in ("price_above", "price_below", "move"):
        if value is None or not value > 0:
            raise ValueError("enter a positive number")
        rule["value"] = float(value)
    if kind in ("price_above", "price_below"):
        if not ticker:
            raise ValueError("enter a ticker")
        rule["ticker"] = ticker.upper()
    elif kind == "move":
        rule["ticker"] = (ticker or "*").upper()
    elif kind == "insider_buy":
        rule["value"] = float(value) if value and value > 0 else 100_000.0
    return rule


# --- pure evaluation --------------------------------------------------------

def evaluate_prices(rules: list[dict], quotes: dict, state: dict, today: str,
                    watchlist: list[str] = ()) -> list[dict]:
    """Price-level and daily-move alerts. ``quotes``: {ticker: {price,
    change_pct}}. Mutates ``state`` (arming + once-a-day keys); returns events.

    A level alert fires once when crossed and re-arms after the price moves
    back 1% the other way, so a stock hovering at the line doesn't buzz."""
    events = []
    for r in rules:
        if not r.get("on"):
            continue
        kind, rid = r["type"], r["id"]
        if kind in ("price_above", "price_below"):
            q = quotes.get(r["ticker"])
            if not q or q.get("price") is None:
                continue
            px, lvl, key = q["price"], r["value"], "arm:" + rid
            hit = px >= lvl if kind == "price_above" else px <= lvl
            rearm = px < lvl * 0.99 if kind == "price_above" else px > lvl * 1.01
            if hit and state.get(key) != "fired":
                state[key] = "fired"
                word = "rose to" if kind == "price_above" else "fell to"
                events.append({"rule": rid, "ticker": r["ticker"], "tags": ["chart_with_upwards_trend" if kind == "price_above" else "chart_with_downwards_trend"],
                               "title": f"{r['ticker']} {word} ${px:,.2f}",
                               "body": f"Your alert level was ${lvl:,.2f}."})
            elif rearm and state.get(key) == "fired":
                state[key] = "armed"
        elif kind == "move":
            names = list(watchlist) if r.get("ticker") in (None, "*") else [r["ticker"]]
            for t in names:
                q = quotes.get(t)
                chg = (q or {}).get("change_pct")
                if chg is None or abs(chg) * 100 < r["value"]:
                    continue
                key = f"mv:{rid}:{t}:{today}"
                if key in state:
                    continue
                state[key] = today
                events.append({"rule": rid, "ticker": t, "tags": ["zap"],
                               "title": f"{t} {'up' if chg > 0 else 'down'} {abs(chg) * 100:.1f}% today",
                               "body": f"Now ${q['price']:,.2f}. Your threshold: {r['value']:g}% either way."})
    return events


def breakout_events(rule: dict, candidates: list[dict], state: dict, as_of: str) -> list[dict]:
    out = []
    for c in candidates:
        key = f"bo:{c['ticker']}:{as_of}"
        if key in state:
            continue
        state[key] = as_of
        conf = c.get("score")
        out.append({"rule": rule["id"], "ticker": c["ticker"], "tags": ["rocket"],
                    "title": f"{c['ticker']} broke out to a 20-day high",
                    "body": (f"Closed ${c['close']:,.2f}" + (f", {c['change'] * 100:+.1f}% on the day" if c.get("change") is not None else "")
                             + (f"; {conf} of 4 confirmations." if conf is not None else "."))})
    return out


def insider_events(rule: dict, trades: dict[str, list[dict]], state: dict, since: str) -> list[dict]:
    """Open-market purchases (Form 4 code P) since ``since`` worth at least
    the rule's dollar value. ``trades``: {ticker: [{name, date, code, shares, price}]}."""
    out = []
    for t, rows in trades.items():
        for x in rows or []:
            if x.get("code") != "P" or (x.get("date") or "") < since:
                continue
            val = abs(x.get("shares") or 0) * (x.get("price") or 0)
            if val < rule.get("value", 100_000):
                continue
            key = f"ins:{t}:{x['date']}:{x.get('name', '')}"
            if key in state:
                continue
            state[key] = x["date"]
            out.append({"rule": rule["id"], "ticker": t, "tags": ["moneybag"],
                        "title": f"Insider bought {t}: ${val / 1e6:,.2f}M",
                        "body": f"{(x.get('name') or 'An insider').title()} bought {abs(x['shares']):,.0f} shares at ${x['price']:,.2f} on {x['date']}."})
    return out


def earnings_events(rule: dict, rows: list[dict], state: dict) -> list[dict]:
    out = []
    when = {"pre": "before the open", "post": "after the close", "during": "during the day"}
    for r in rows:
        key = f"er:{r['ticker']}:{r['date']}"
        if key in state:
            continue
        state[key] = r["date"]
        wd = datetime.fromisoformat(r["date"]).strftime("%A")
        out.append({"rule": rule["id"], "ticker": r["ticker"], "tags": ["calendar"],
                    "title": f"{r['ticker']} reports {wd} {when.get(r.get('timing') or '', '')}".strip(),
                    "body": (f"EPS estimate ${r['eps_est']:.2f}." if r.get("eps_est") is not None else "Estimate not available.")})
    return out


def next_trading_day(d: date) -> date:
    n = d + timedelta(days=1)
    while n.weekday() >= 5:
        n += timedelta(days=1)
    return n


# --- sending ----------------------------------------------------------------

def topic() -> str | None:
    t = (os.environ.get("NTFY_TOPIC") or "").strip()
    return t or None


def suggest_topic() -> str:
    return "stockskill-" + secrets.token_urlsafe(12).replace("_", "").replace("-", "").lower()[:16]


def send(ev: dict) -> bool:
    """Publish one alert to the ntfy topic (JSON form, so any text is safe)."""
    tp = topic()
    if not tp:
        return False
    server = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
    base = (os.environ.get("STOCKSKILL_PUBLIC_URL") or "").rstrip("/")
    msg = {"topic": tp, "title": ev["title"], "message": ev.get("body") or ev["title"],
           "tags": ev.get("tags") or [], "priority": ev.get("priority", 3)}
    if base and ev.get("ticker"):
        msg["click"] = f"{base}/analysis/{ev['ticker']}"
    try:
        import requests
        r = requests.post(server, data=json.dumps(msg).encode(), timeout=10)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


# --- scheduler --------------------------------------------------------------

class Checker:
    """Background loop. Price rules every 5 minutes in the regular session
    (the whole watchlist's moves every 15); breakouts after the close,
    insider buys in the evening, and tomorrow's earnings each morning."""

    def __init__(self, watchlist_fn, breakouts_fn):
        self.watchlist_fn = watchlist_fn      # () -> [tickers]
        self.breakouts_fn = breakouts_fn      # () -> (as_of, [candidates])
        self.last: dict[str, float] = {}
        self.daily: dict[str, str] = {}
        self._started = False

    def start(self) -> None:
        # STOCKSKILL_ALERTS=0 turns the checker off in this process (when two
        # copies of the app run, only one should send, or alerts arrive twice)
        if self._started or not topic() or os.environ.get("STOCKSKILL_ALERTS", "1") == "0":
            return
        self._started = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while True:
            try:
                self.run_once()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(60)

    def _due(self, name: str, every: float) -> bool:
        if time.time() - self.last.get(name, 0) < every:
            return False
        self.last[name] = time.time()
        return True

    def run_once(self, force: bool = False) -> list[dict]:
        from .. import marketclock
        from ..data import finnhub
        st = marketclock.market_status()
        et = st.et
        today = et.date().isoformat()
        with _DOC_LOCK:
            doc = load()
        rules = [r for r in doc["rules"] if r.get("on")]
        if not rules:
            return []
        state, events = doc["state"], []
        wl = None

        # prices: level rules on their tickers; move rules on one name or the watchlist
        if st.is_open or force:
            tickers = {r["ticker"] for r in rules if r["type"] in ("price_above", "price_below")}
            tickers |= {r["ticker"] for r in rules if r["type"] == "move" and r.get("ticker") not in (None, "*")}
            wide = any(r["type"] == "move" and r.get("ticker") in (None, "*") for r in rules)
            if wide and (force or self._due("wide", 900)):
                wl = self.watchlist_fn()
                tickers |= set(wl)
            if tickers and (force or (wide and wl is not None) or self._due("prices", 300)):
                quotes = finnhub.batch_quotes(sorted(tickers))
                events += evaluate_prices(rules, quotes, state, today, wl or [])

        def once_a_day(name: str, after_hour: float) -> bool:
            if force:
                return True
            if not st.is_weekday or et.hour + et.minute / 60 < after_hour or self.daily.get(name) == today:
                return False
            self.daily[name] = today
            return True

        for r in rules:
            if r["type"] == "breakout" and once_a_day("breakout", 16.5):
                as_of, cands = self.breakouts_fn()
                if as_of == today or force:
                    events += breakout_events(r, cands, state, as_of)
            elif r["type"] == "insider_buy" and once_a_day("insider", 18.0):
                from ..data.signals_extra import insider_trades
                wl = wl if wl is not None else self.watchlist_fn()
                since = (et.date() - timedelta(days=3)).isoformat()
                trades = {}
                for t in wl:
                    finnhub._LIMITER.acquire()
                    trades[t] = [x for x in (insider_trades(t, years=0) or []) if x.get("date", "") >= since]
                events += insider_events(r, trades, state, since)
            elif r["type"] == "earnings" and once_a_day("earnings", 8.0):
                from ..data import earnings as E
                wl = wl if wl is not None else self.watchlist_fn()
                nxt = next_trading_day(et.date()).isoformat()
                rows = [x for x in E.calendar(wl, 4) if x["date"] in (today, nxt)
                        and not (x["date"] == today and x.get("timing") == "pre")]
                events += earnings_events(r, rows, state)

        stamp = datetime.now().isoformat(timespec="seconds")
        for ev in events:
            ev["sent"] = send(ev)
            ev["at"] = stamp
        with _DOC_LOCK:
            fresh = load()                    # rules may have changed while we checked
            fresh["state"].update(state)
            fresh["log"] = (fresh.get("log") or []) + [{k: ev[k] for k in ("at", "title", "body", "ticker", "sent")} for ev in events]
            save(fresh)
        return events
