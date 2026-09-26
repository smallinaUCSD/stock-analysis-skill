"""Usage analytics and health monitoring for the public site, first-party
and privacy-friendly.

* Every request (minus polling and static files) is recorded: route, status,
  duration, device class, browser, OS, and who - the account id when signed
  in, otherwise a hash of IP + browser that changes every day (no cookie, and
  the IP itself is never stored).
* Pages send a few feature events (quick-look opened, tab switched, ...).
* Rows are buffered in memory and written in batches to their own SQLite
  file (``STOCKSKILL_ANALYTICS_DB``, default data/analytics.db), kept 90 days (the Privacy Policy's limit for server logs).

``classify_ua`` and the report queries are tested.
"""

from __future__ import annotations

import atexit
import hashlib
import os
import re
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS hits (
  ts REAL NOT NULL, day TEXT NOT NULL, route TEXT, path TEXT, method TEXT, status INTEGER, ms REAL,
  uid INTEGER, visitor TEXT, device TEXT, browser TEXT, os TEXT, referrer TEXT, ticker TEXT, page INTEGER
);
CREATE INDEX IF NOT EXISTS hits_day ON hits(day);
CREATE TABLE IF NOT EXISTS events (
  ts REAL NOT NULL, day TEXT NOT NULL, name TEXT NOT NULL, detail TEXT, uid INTEGER, visitor TEXT, device TEXT
);
CREATE INDEX IF NOT EXISTS events_day ON events(day);
"""

_SKIP = re.compile(r"^/(healthz|api/board/meta|api/quotes|sw\.js|manifest\.webmanifest|icon-|apple-touch|favicon|api/t$)")
_BOT = re.compile(r"bot|crawl|spider|slurp|curl|wget|python-requests|httpx|headless|monitor|uptime", re.I)
_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def db_path() -> str:
    return os.environ.get("STOCKSKILL_ANALYTICS_DB") or "data/analytics.db"


def _conn():
    p = db_path()
    if os.path.dirname(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    c = sqlite3.connect(p, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    return c


def init() -> None:
    c = _conn()
    c.executescript(SCHEMA)
    c.commit()
    c.close()


def classify_ua(ua: str) -> tuple[str, str, str] | None:
    """(device, browser, os), or None for bots and scripts."""
    ua = ua or ""
    if not ua or _BOT.search(ua):
        return None
    if re.search(r"iPad|Tablet|Android(?!.*Mobile)", ua):
        device = "tablet"
    elif re.search(r"Mobi|iPhone|Android", ua):
        device = "mobile"
    else:
        device = "desktop"
    if "Edg/" in ua:
        browser = "Edge"
    elif "Firefox/" in ua or "FxiOS" in ua:
        browser = "Firefox"
    elif "CriOS" in ua or ("Chrome/" in ua and "Chromium" not in ua):
        browser = "Chrome"
    elif "Safari/" in ua:
        browser = "Safari"
    else:
        browser = "Other"
    if re.search(r"iPhone|iPad|iPod", ua):
        os_ = "iOS"
    elif "Android" in ua:
        os_ = "Android"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        os_ = "macOS"
    elif "Windows" in ua:
        os_ = "Windows"
    elif "Linux" in ua:
        os_ = "Linux"
    else:
        os_ = "Other"
    return device, browser, os_


def visitor_id(ip: str, ua: str, day: str, secret: str) -> str:
    """Anonymous, changes daily, can't be reversed to an IP."""
    return hashlib.sha256(f"{secret}|{day}|{ip}|{ua}".encode()).hexdigest()[:16]


class Collector:
    def __init__(self, secret: str):
        self.secret = secret
        self.buf: list = []
        self.ev: list = []
        self.lock = threading.Lock()
        init()
        threading.Thread(target=self._flush_loop, daemon=True).start()
        atexit.register(self._final_flush)

    def _final_flush(self):
        try:
            self.flush()                               # don't lose the last few seconds on a restart
        except Exception:  # noqa: BLE001
            pass

    def record(self, route, path, method, status, ms, uid, ip, ua, referrer, ticker, is_page) -> None:
        if _SKIP.match(path or ""):
            return
        cls = classify_ua(ua)
        if cls is None:
            return
        now = time.time()
        day = date.today().isoformat()
        ref = None
        if referrer:
            m = re.match(r"https?://([^/]+)", referrer)
            ref = m.group(1) if m else None
        with self.lock:
            self.buf.append((now, day, route, path[:200], method, status, round(ms, 1), uid,
                             visitor_id(ip, ua, day, self.secret), *cls, ref, ticker, 1 if is_page else 0))

    def event(self, name: str, detail: str | None, uid, ip, ua) -> bool:
        cls = classify_ua(ua)
        if cls is None or not _EVENT_NAME.match(name or ""):
            return False
        day = date.today().isoformat()
        with self.lock:
            if len(self.ev) < 5000:
                self.ev.append((time.time(), day, name, (detail or "")[:60] or None, uid,
                                visitor_id(ip, ua, day, self.secret), cls[0]))
        return True

    def flush(self) -> None:
        with self.lock:
            hits, ev, self.buf, self.ev = self.buf, self.ev, [], []
        if not hits and not ev:
            return
        c = _conn()
        c.executemany("INSERT INTO hits VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", hits)
        c.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?)", ev)
        c.commit()
        c.close()

    def _flush_loop(self):
        last_prune = 0.0
        while True:
            time.sleep(5)
            try:
                self.flush()
                if time.time() - last_prune > 86400:
                    last_prune = time.time()
                    cut = (date.today() - timedelta(days=90)).isoformat()
                    c = _conn()
                    c.execute("DELETE FROM hits WHERE day < ?", (cut,))
                    c.execute("DELETE FROM events WHERE day < ?", (cut,))
                    c.commit()
                    c.close()
            except Exception:  # noqa: BLE001
                pass


# --- reports ---------------------------------------------------------------------

def _q(c, sql, *args):
    return [dict(r) for r in c.execute(sql, args)]


def report(days: int = 30, users_db: str | None = None) -> dict:
    """Everything the admin dashboard shows."""
    c = _conn()
    today = date.today()
    since = (today - timedelta(days=days - 1)).isoformat()
    wk = (today - timedelta(days=6)).isoformat()
    now = time.time()
    who = "COALESCE(CAST(uid AS TEXT), visitor)"
    out: dict = {"days": days}
    out["active_now"] = c.execute(f"SELECT COUNT(DISTINCT {who}) FROM hits WHERE ts > ?", (now - 300,)).fetchone()[0]

    def active(since_day, signed_in=True):
        col = "uid" if signed_in else "visitor"
        cond = "uid IS NOT NULL" if signed_in else "uid IS NULL"
        return c.execute(f"SELECT COUNT(DISTINCT {col}) FROM hits WHERE day >= ? AND {cond}", (since_day,)).fetchone()[0]
    out["dau"], out["wau"], out["mau"] = (active(today.isoformat()), active(wk),
                                          active((today - timedelta(days=29)).isoformat()))
    out["visitors_today"] = active(today.isoformat(), False)
    out["daily"] = _q(c, f"""SELECT day, COUNT(DISTINCT CASE WHEN uid IS NOT NULL THEN uid END) AS users,
                             COUNT(DISTINCT CASE WHEN uid IS NULL THEN visitor END) AS visitors,
                             SUM(page) AS pages FROM hits WHERE day >= ? GROUP BY day ORDER BY day""", since)
    out["top_pages"] = _q(c, f"""SELECT route, COUNT(*) AS views, COUNT(DISTINCT {who}) AS people FROM hits
                                 WHERE day >= ? AND page = 1 GROUP BY route ORDER BY views DESC LIMIT 15""", wk)
    out["top_features"] = _q(c, f"""SELECT name, COUNT(*) AS uses, COUNT(DISTINCT {who}) AS people FROM events
                                    WHERE day >= ? GROUP BY name ORDER BY uses DESC LIMIT 15""", wk)
    out["top_api"] = _q(c, f"""SELECT route, COUNT(*) AS calls, COUNT(DISTINCT {who}) AS people FROM hits
                               WHERE day >= ? AND page = 0 GROUP BY route ORDER BY calls DESC LIMIT 15""", wk)
    # a stock page open or a quick look counts as one view (not the page's own data calls)
    out["top_stocks"] = _q(c, f"""SELECT ticker, COUNT(*) AS views, COUNT(DISTINCT who) AS people FROM (
                                    SELECT ticker, {who} AS who FROM hits WHERE day >= ? AND page = 1 AND ticker IS NOT NULL
                                    UNION ALL
                                    SELECT UPPER(detail), {who} FROM events WHERE day >= ? AND name = 'quicklook' AND detail IS NOT NULL)
                                  GROUP BY ticker ORDER BY people DESC, views DESC LIMIT 15""", wk, wk)
    for k, col in (("devices", "device"), ("browsers", "browser"), ("os", "os")):
        out[k] = _q(c, f"SELECT {col} AS name, COUNT(DISTINCT {who}) AS people FROM hits WHERE day >= ? "
                       f"GROUP BY {col} ORDER BY people DESC", since)
    out["referrers"] = _q(c, """SELECT referrer AS name, COUNT(*) AS visits FROM hits WHERE day >= ? AND page = 1
                                AND referrer IS NOT NULL GROUP BY referrer ORDER BY visits DESC LIMIT 10""", since)
    # health: last 24 hours
    d1 = now - 86400
    tot = c.execute("SELECT COUNT(*), SUM(status >= 500), SUM(status >= 400 AND status < 500) FROM hits WHERE ts > ?", (d1,)).fetchone()
    out["requests_24h"], out["errors_24h"], out["client_errors_24h"] = tot[0] or 0, tot[1] or 0, tot[2] or 0
    rows = _q(c, "SELECT route, ms FROM hits WHERE ts > ? AND route IS NOT NULL", d1)
    by: dict = {}
    for r in rows:
        by.setdefault(r["route"], []).append(r["ms"])
    lat = []
    for route, v in by.items():
        v.sort()
        lat.append({"route": route, "count": len(v), "p50": v[len(v) // 2], "p95": v[min(len(v) - 1, int(len(v) * 0.95))]})
    out["slow_routes"] = sorted(lat, key=lambda x: -x["p95"])[:12]
    allms = sorted(r["ms"] for r in rows)
    out["p50_ms"] = allms[len(allms) // 2] if allms else None
    out["p95_ms"] = allms[min(len(allms) - 1, int(len(allms) * 0.95))] if allms else None
    out["recent_errors"] = _q(c, """SELECT ts, path, status, ms FROM hits WHERE status >= 500 ORDER BY ts DESC LIMIT 15""")
    c.close()
    out.update(_account_stats(users_db, since))
    return out


def _account_stats(users_db: str | None, since: str) -> dict:
    """Sign-ups, the onboarding funnel, retention and notification settings."""
    p = users_db or os.environ.get("STOCKSKILL_DB") or "data/users.db"
    if not os.path.exists(p):
        return {}
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    ts0 = datetime.fromisoformat(since).timestamp()
    out = {
        "accounts": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "onboarded": c.execute("SELECT COUNT(*) FROM users WHERE onboarded = 1").fetchone()[0],
        "signups": [dict(r) for r in c.execute(
            "SELECT date(created_at, 'unixepoch') AS day, COUNT(*) AS n FROM users WHERE created_at >= ? GROUP BY day ORDER BY day", (ts0,))],
        "new_accounts": c.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (ts0,)).fetchone()[0],
        "new_onboarded": c.execute("SELECT COUNT(*) FROM users WHERE created_at >= ? AND onboarded = 1", (ts0,)).fetchone()[0],
        "investor_types": [dict(r) for r in c.execute(
            "SELECT COALESCE(investor_type,'not set') AS name, COUNT(*) AS n FROM users GROUP BY name ORDER BY n DESC")],
        "sign_in": {"google": c.execute("SELECT COUNT(*) FROM users WHERE google_sub IS NOT NULL").fetchone()[0],
                    "password": c.execute("SELECT COUNT(*) FROM users WHERE password_hash IS NOT NULL").fetchone()[0],
                    "passkey": c.execute("SELECT COUNT(DISTINCT user_id) FROM passkeys").fetchone()[0],
                    "two_step": c.execute("SELECT COUNT(*) FROM users WHERE mfa_method IS NOT NULL").fetchone()[0]},
        "notify": {"summary": c.execute("SELECT COUNT(*) FROM users WHERE summary_times IN ('pre','post','both')").fetchone()[0],
                   "email": c.execute("SELECT COUNT(*) FROM users WHERE notify_email = 1 AND email_verified = 1").fetchone()[0],
                   "push": c.execute("SELECT COUNT(DISTINCT user_id) FROM push_subs").fetchone()[0],
                   "sms": _n(c, "SELECT COUNT(*) FROM users WHERE notify_sms = 1 AND phone_verified = 1"),
                   "events": _n(c, "SELECT COUNT(*) FROM users WHERE notify_events = 1"),
                   "follows": c.execute("SELECT COUNT(*) FROM follows").fetchone()[0]},
    }
    # alerts sent per day, by type, and how many went out by email / push / text
    kind = ("CASE WHEN kind = 'summary' AND dedupe LIKE '%:pre' THEN 'Pre-market summary' "
            "WHEN kind = 'summary' AND dedupe LIKE '%:post' THEN 'Post-market summary' "
            "WHEN kind = 'event' THEN 'Market event' WHEN kind = 'trade' THEN 'Politician trade' "
            "WHEN kind = 'fund' THEN 'Fund filing' ELSE kind END")
    try:
        out["alerts"] = [dict(r) for r in c.execute(
            f"""SELECT date(created_at, 'unixepoch', '-4 hours') AS day, {kind} AS kind, COUNT(*) AS n,
                       SUM(COALESCE(channels, '') LIKE '%email%') AS email, SUM(COALESCE(channels, '') LIKE '%push%') AS push,
                       SUM(COALESCE(channels, '') LIKE '%sms%') AS sms
                FROM notifications WHERE created_at >= ? AND kind != 'test'
                GROUP BY day, kind ORDER BY day DESC, kind LIMIT 60""", (time.time() - 14 * 86400,))]
    except sqlite3.OperationalError:
        out["alerts"] = []
    c.close()
    return out


def _n(c, sql: str) -> int:
    try:
        return c.execute(sql).fetchone()[0]
    except sqlite3.OperationalError:                   # an older database without the column
        return 0


def retention(users_db: str | None = None, weeks: int = 6) -> list[dict]:
    """Of people who signed up each week, how many came back 1-7 days later."""
    p = users_db or os.environ.get("STOCKSKILL_DB") or "data/users.db"
    if not os.path.exists(p):
        return []
    u = sqlite3.connect(p)
    users = u.execute("SELECT id, created_at FROM users").fetchall()
    u.close()
    c = _conn()
    out = []
    today = date.today()
    for w in range(weeks, 0, -1):
        start = today - timedelta(days=7 * w + 7)
        end = start + timedelta(days=7)
        cohort = [(uid, ts) for uid, ts in users if start.isoformat() <= date.fromtimestamp(ts).isoformat() < end.isoformat()]
        back = 0
        for uid, ts in cohort:
            if c.execute("SELECT 1 FROM hits WHERE uid = ? AND ts > ? AND ts < ? LIMIT 1",
                         (uid, ts + 86400, ts + 8 * 86400)).fetchone():
                back += 1
        out.append({"week": start.isoformat(), "signups": len(cohort), "returned": back})
    c.close()
    return out
