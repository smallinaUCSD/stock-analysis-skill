"""Per-user notifications: the daily market summary and alerts when a
followed politician's trade is published, delivered by any mix of email,
browser push and the in-app Today panel (each user's choice).

* Email goes through an SMTP account (e.g. Gmail with an app password:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM), only to
  addresses the user has confirmed, with a one-click unsubscribe link.
* Browser push uses the Web Push standard with this server's own VAPID key
  (generated once, kept in data/.vapid_private.pem).
* The scheduler runs in the public app when STOCKSKILL_NOTIFY=1: summaries at
  8:30am and 4:30pm Eastern on weekdays, politician trades every 30 minutes.

``compose_summary`` and ``trade_events`` are pure (tested).
"""

from __future__ import annotations

import html
import json
import os
import smtplib
import threading
import time
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from . import db

SLOTS = {"pre": (8, 30), "post": (16, 30)}
INDEXES = [("SPY", "S&P 500"), ("QQQ", "Nasdaq-100"), ("DIA", "Dow"), ("IWM", "Russell 2000")]


# --- settings helpers -----------------------------------------------------------

def public_url() -> str:
    return (os.environ.get("STOCKSKILL_PUBLIC_URL") or "").rstrip("/")


def _secret(app=None) -> str:
    if app is not None and app.secret_key:
        return app.secret_key
    from .auth import _secret_key
    return _secret_key()


def token(uid: int, email: str, salt: str, secret: str | None = None) -> str:
    from itsdangerous import URLSafeTimedSerializer
    return URLSafeTimedSerializer(secret or _secret(), salt=salt).dumps({"u": uid, "e": email})


def read_token(tok: str, salt: str, max_age: int, secret: str | None = None) -> dict | None:
    from itsdangerous import BadSignature, URLSafeTimedSerializer
    try:
        return URLSafeTimedSerializer(secret or _secret(), salt=salt).loads(tok, max_age=max_age)
    except BadSignature:
        return None


# --- email -------------------------------------------------------------------

LAST_ERROR = {"msg": None}


def _explain(e: Exception) -> str:
    """A plain-English reason an email didn't send."""
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return ("Gmail didn't accept the sign-in. Check SMTP_USER and that SMTP_PASSWORD is an app password "
                "(16 letters, no spaces) created with 2-Step Verification on.")
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "The mail server refused that recipient address."
    if isinstance(e, (OSError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)):
        return f"Couldn't reach the mail server ({e})."
    return f"The mail server returned an error ({e})."


def email_ready() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def send_email(to: str, subject: str, text: str, html_body: str | None = None,
               unsubscribe: str | None = None) -> bool:
    if not email_ready():
        return False
    from .legal import operator
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{operator()} <{os.environ.get('MAIL_FROM') or os.environ['SMTP_USER']}>"
    msg["To"] = to
    if unsubscribe:
        msg["List-Unsubscribe"] = f"<{unsubscribe}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    try:
        port = int(os.environ.get("SMTP_PORT") or 587)
        cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with cls(os.environ["SMTP_HOST"], port, timeout=20) as s:
            if port != 465:
                s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"].replace(" ", ""))
            s.send_message(msg)
        LAST_ERROR["msg"] = None
        return True
    except Exception as e:  # noqa: BLE001
        import sys
        LAST_ERROR["msg"] = _explain(e)
        print(f"email to {to} failed: {e}", file=sys.stderr, flush=True)
        return False


def _email_html(title: str, lines: list[str], url: str, unsub: str) -> str:
    body = "".join(f'<p style="margin:0 0 10px;line-height:1.55">{ln}</p>' for ln in lines)
    return (f'<div style="background:#faf9f5;padding:24px;font-family:Georgia,serif;color:#141413">'
            f'<div style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #e6dfd8;border-radius:14px;padding:24px">'
            f'<h1 style="font-weight:500;font-size:24px;margin:0 0 14px">{html.escape(title)}</h1>{body}'
            f'<p style="margin:18px 0 0"><a href="{html.escape(url)}" style="background:#cc785c;color:#fff;text-decoration:none;'
            f'padding:10px 18px;border-radius:8px;display:inline-block">Open your watchlist</a></p></div>'
            f'<p style="max-width:560px;margin:14px auto 0;font-size:12px;color:#6c6a64;line-height:1.5">Research, not financial '
            f'advice. <a href="{html.escape(public_url())}/account" style="color:#6c6a64">Notification settings</a> · '
            f'<a href="{html.escape(unsub)}" style="color:#6c6a64">Unsubscribe from emails</a></p></div>')


def send_verification(u: dict) -> bool:
    link = f"{public_url()}/notifications/verify?t={token(u['id'], u['email'], 'verify')}"
    text = (f"Confirm this email address to get your market summaries and alerts:\n{link}\n\n"
            "If you didn't sign up, ignore this message.")
    lines = ["Confirm this email address to get your market summaries and alerts.",
             f'<a href="{html.escape(link)}">Confirm my email</a>', "If you didn't sign up, you can ignore this message."]
    return send_email(u["email"], "Confirm your email", text,
                      _email_html("Confirm your email", lines, link, link))


# --- browser push ---------------------------------------------------------------

def _vapid_path() -> str:
    return os.path.join(os.path.dirname(db.path()) or ".", ".vapid_private.pem")


def vapid_public_key() -> str | None:
    """The applicationServerKey browsers need (created on first use)."""
    try:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from py_vapid import Vapid, b64urlencode
    except ImportError:
        return None
    path = _vapid_path()
    if os.path.exists(path):
        v = Vapid.from_file(path)
    else:
        v = Vapid()
        v.generate_keys()
        v.save_key(path)
        os.chmod(path, 0o600)
    raw = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return b64urlencode(raw)


def send_push(uid: int, title: str, body: str, url: str | None) -> int:
    """Push to every browser the user subscribed; drops expired subscriptions."""
    subs = db.push_subs(uid)
    if not subs:
        return 0
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return 0
    vapid_public_key()                                   # make sure the key file exists
    from .legal import contact
    sent = 0
    for s in subs:
        try:
            webpush({"endpoint": s["endpoint"], "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}},
                    data=json.dumps({"title": title, "body": body, "url": url or "/"}),
                    vapid_private_key=_vapid_path(),
                    vapid_claims={"sub": "mailto:" + (contact() or "admin@example.com")}, timeout=10)
            sent += 1
        except WebPushException as e:
            if e.response is not None and e.response.status_code in (404, 410):
                db.drop_push(s["endpoint"])
        except Exception:  # noqa: BLE001
            pass
    return sent


# --- delivery -------------------------------------------------------------------

def deliver(u: dict, kind: str, title: str, lines: list[str], url: str, dedupe: str,
            push_body: str | None = None) -> dict:
    """Send one message through each channel the user chose. The dedupe key
    makes it once-only per user (safe to call again after a restart)."""
    plain = [html.unescape(_strip_tags(ln)) for ln in lines]
    fresh = db.add_notification(u["id"], kind, title, "\n".join(plain), url, dedupe)
    out = {"inapp": bool(u.get("notify_inapp")), "email": False, "push": 0}
    if not fresh:
        return {"duplicate": True}
    if u.get("notify_email") and u.get("email_verified"):
        unsub = f"{public_url()}/notifications/unsubscribe?t={token(u['id'], u['email'], 'unsub')}"
        full = url if url.startswith("http") else public_url() + url
        out["email"] = send_email(u["email"], title, "\n\n".join(plain) + f"\n\n{full}\n\nUnsubscribe: {unsub}",
                                  _email_html(title, lines, full, unsub), unsubscribe=unsub)
    if u.get("notify_push"):
        out["push"] = send_push(u["id"], title, push_body or (plain[0] if plain else ""), url)
    return out


def _strip_tags(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", s)


# --- the daily summary ----------------------------------------------------------

def _pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return "0.0%" if abs(x) < 0.0005 else f"{x * 100:+.1f}%"


def compose_summary(slot: str, user: dict, watch: list[str], quotes: dict, groups: list[dict],
                    earnings: list[dict], econ: list[dict], today: date) -> tuple[str, list[str], str]:
    """(title, lines as simple HTML, short push text) for one user.
    ``quotes``: {ticker: {price, change_pct}} - the latest session's move."""
    day = today.strftime("%a %b %-d")
    when = "yesterday" if slot == "pre" else "today"
    title = ("Before the bell · " if slot == "pre" else "Market close · ") + day
    lines = []
    name = (user.get("first_name") or "").strip()
    lines.append((f"Good morning{', ' + html.escape(name) if name else ''}. " if slot == "pre"
                  else f"Here's how the market closed{', ' + html.escape(name) if name else ''}. ")
                 + "All changes are for the " + ("last session." if slot == "pre" else "day."))
    idx = [f"{lbl} <b>{_pct(quotes[t]['change_pct'])}</b>" for t, lbl in INDEXES
           if quotes.get(t) and quotes[t].get("change_pct") is not None]
    if idx:
        lines.append("<b>Markets " + when + ":</b> " + " · ".join(idx))
    chosen = set((user.get("summary_groups") or user.get("groups") or "").split(",")) - {""}
    sect = []
    for g in groups:
        if g["key"] not in chosen:
            continue
        ch = [(t, quotes[t]["change_pct"]) for t in g["tickers"] if quotes.get(t) and quotes[t].get("change_pct") is not None]
        if len(ch) < 2:
            continue
        avg = sum(c for _, c in ch) / len(ch)
        best, worst = max(ch, key=lambda x: x[1]), min(ch, key=lambda x: x[1])
        sect.append((avg, f"{html.escape(g['label'])} <b>{_pct(avg)}</b> (best {best[0]} {_pct(best[1])}, "
                          f"worst {worst[0]} {_pct(worst[1])})"))
    if sect:
        lines.append("<b>Your sectors:</b> " + "; ".join(s for _, s in sorted(sect, key=lambda x: -x[0])))
    mine = sorted(((t, quotes[t]["change_pct"]) for t in watch
                   if quotes.get(t) and quotes[t].get("change_pct") is not None), key=lambda x: -x[1])
    if mine:
        up = ", ".join(f"{t} {_pct(c)}" for t, c in mine[:3] if c > 0)
        dn = ", ".join(f"{t} {_pct(c)}" for t, c in reversed(mine[-3:]) if c < 0)
        if up:
            lines.append("<b>Your biggest gainers:</b> " + up)
        if dn:
            lines.append("<b>Your biggest decliners:</b> " + dn)
    wmap = {"pre": "before the open", "post": "after the close", "during": "during the day"}
    if earnings:
        lines.append("<b>Earnings on your list:</b> " + "; ".join(
            f"{e['ticker']} {'today' if e['date'] == today.isoformat() else 'tomorrow'} {wmap.get(e.get('timing') or '', '')}".strip()
            for e in earnings[:8]))
    if econ:
        lines.append("<b>Economic data:</b> " + "; ".join(
            f"{html.escape(e['name'])} {'today' if e['date'] == today.isoformat() else 'tomorrow'}"
            + (f" at {datetime.strptime(e['time'], '%H:%M').strftime('%-I:%M%p').lower()} ET" if e.get("time") else "")
            for e in econ[:6]))
    spy = quotes.get("SPY", {}).get("change_pct")
    push = (f"S&P 500 {_pct(spy)}" if spy is not None else "Your market summary") + (
        f"; {len(earnings)} of your stocks report soon" if earnings else "")
    return title, lines, push


# --- politician trades ------------------------------------------------------------

def trade_events(trades: list[dict], followers: dict, member_id, since_days: int = 10,
                 today: date | None = None) -> list[tuple[int, dict, str]]:
    """[(user_id, trade, dedupe)] for trades by followed politicians that were
    disclosed recently and after the user started following them."""
    today = today or date.today()
    floor = (today - timedelta(days=since_days)).isoformat()
    out = []
    for t in trades:
        filed = t.get("filed") or ""
        if filed < floor:
            continue
        pid = member_id(t)
        if not pid or pid not in followers:
            continue
        key = f"tr:{pid}:{filed}:{t.get('ticker') or t.get('asset') or ''}:{t.get('type') or ''}:{t.get('amount') or ''}:{t.get('traded') or ''}"
        for uid, since in followers[pid]:
            if filed >= datetime.fromtimestamp(since).date().isoformat():
                out.append((uid, t, key))
    return out


def trade_message(t: dict, pid: str) -> tuple[str, list[str], str]:
    who = t.get("member") or "A politician"
    verb = "bought" if (t.get("type") or "").lower().startswith("buy") else "sold" if (t.get("type") or "").lower().startswith("sell") else "traded"
    what = t.get("ticker") or t.get("asset") or "a security"
    title = f"{who} {verb} {what}"
    lines = [f"<b>{html.escape(who)}</b> {verb} <b>{html.escape(what)}</b>"
             + (f" ({html.escape(t['amount'])})" if t.get("amount") else "") + "."]
    dates = []
    if t.get("traded"):
        dates.append(f"traded {t['traded']}")
    if t.get("filed"):
        dates.append(f"disclosed {t['filed']}")
    if dates:
        lines.append(", ".join(dates).capitalize() + ". Reports can come up to 45 days after the trade.")
    return title, lines, f"/politician/{pid}"


# --- scheduler ------------------------------------------------------------------------

class Scheduler:
    def __init__(self, app, member_id):
        self.app, self.member_id = app, member_id
        self.state_path = os.path.join(os.path.dirname(db.path()) or ".", "notify_state.json")
        self.last_trades = 0.0

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _state(self) -> dict:
        try:
            return json.load(open(self.state_path))
        except (OSError, ValueError):
            return {}

    def _save(self, st: dict):
        tmp = self.state_path + ".tmp"
        json.dump(st, open(tmp, "w"))
        os.replace(tmp, self.state_path)

    def _loop(self):
        while True:
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                import sys
                print(f"notify scheduler: {e}", file=sys.stderr, flush=True)
            time.sleep(60)

    def tick(self, now: datetime | None = None, force_slot: str | None = None):
        from ..marketclock import market_status
        st = market_status(now)
        et = st.et
        state = self._state()
        for slot, (h, m) in SLOTS.items():
            key = f"{et.date().isoformat()}:{slot}"
            due = force_slot == slot or (st.is_weekday and (et.hour, et.minute) >= (h, m) and (et.hour - h) < 3)
            if due and key not in state:
                state[key] = time.time()
                self._save(state)
                self.run_summaries(slot, et.date())
        if time.time() - self.last_trades > 1800:
            self.last_trades = time.time()
            self.run_trades()
            db.prune_notifications(90)

    def run_summaries(self, slot: str, today: date) -> int:
        cfg = self.app.config["ACCT"]
        users = [u for u in db.all_users() if (u.get("summary_times") in (slot, "both"))]
        if not users:
            return 0
        from .groups import groups as all_groups
        groups = all_groups(cfg["tickers_path"], cfg["cache_dir"])
        gmap = {g["key"]: g for g in groups}
        need = {t for t, _ in INDEXES}
        watch = {}
        for u in users:
            watch[u["id"]] = db.watchlist(u["id"])
            need |= set(watch[u["id"]])
            for k in (u.get("summary_groups") or u.get("groups") or "").split(","):
                need |= set(gmap.get(k, {}).get("tickers", []))
        quotes = _quotes(sorted(need), cfg["cache_dir"])
        try:
            from ..data import earnings as E
            cal = E.calendar(sorted(need), 2)
        except Exception:  # noqa: BLE001
            cal = []
        try:
            from ..data import economy as EC
            econ = [e for e in EC.calendar(cfg["cache_dir"], 0, 2) if e["importance"] >= 2]
        except Exception:  # noqa: BLE001
            econ = []
        tomorrow = (today + timedelta(days=1)).isoformat()
        sent = 0
        for u in users:
            w = set(watch[u["id"]])
            if slot == "pre":
                er = [e for e in cal if e["ticker"] in w and e["date"] == today.isoformat()]
                ec = [e for e in econ if e["date"] == today.isoformat()]
            else:
                er = [e for e in cal if e["ticker"] in w and ((e["date"] == today.isoformat() and e.get("timing") == "post")
                                                             or (e["date"] == tomorrow and e.get("timing") != "post"))]
                ec = [e for e in econ if e["date"] == tomorrow]
            title, lines, push = compose_summary(slot, u, watch[u["id"]], quotes, groups, er, ec, today)
            r = deliver(u, "summary", title, lines, "/", f"sum:{today.isoformat()}:{slot}", push)
            sent += 0 if r.get("duplicate") else 1
        return sent

    def run_trades(self) -> int:
        followers = db.followers_by_pid()
        if not followers:
            return 0
        from ..data.congress import recent_trades
        cfg = self.app.config["ACCT"]
        trades = recent_trades(cfg["cache_dir"]).get("trades") or []
        users = {u["id"]: u for u in db.all_users()}
        n = 0
        for uid, t, key in trade_events(trades, followers, self.member_id):
            u = users.get(uid)
            if not u:
                continue
            pid = self.member_id(t)
            title, lines, url = trade_message(t, pid)
            r = deliver(u, "trade", title, lines, url, key)
            n += 0 if r.get("duplicate") else 1
        return n


def _quotes(tickers: list[str], cache_dir) -> dict:
    """Latest-session moves: live quotes when available, else cached closes."""
    out = {}
    try:
        from ..data import finnhub
        if finnhub.has_finnhub():
            out = finnhub.batch_quotes(tickers)
    except Exception:  # noqa: BLE001
        out = {}
    from ..watchlist.pipeline import _load_cached
    for t in tickers:
        if t in out:
            continue
        td = _load_cached(cache_dir, t) if cache_dir else None
        cl = [c for c in ((td.ohlcv or {}).get("close") or []) if c] if td else []
        if len(cl) >= 2:
            out[t] = {"price": cl[-1], "change_pct": cl[-1] / cl[-2] - 1}
    return out
