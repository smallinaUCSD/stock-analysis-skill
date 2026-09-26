"""User accounts in SQLite: profiles, per-user watchlists, passkeys and the
record of which Terms / Privacy versions each user accepted.

One file (``STOCKSKILL_DB``, default ``data/users.db``, never committed).
Passwords are stored only as salted scrypt hashes (werkzeug); passkeys only as
public keys. Every function opens its own short connection, so it is safe
across gunicorn threads.
"""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT,
  google_sub TEXT UNIQUE,
  first_name TEXT, last_name TEXT, dob TEXT, gender TEXT,
  investor_type TEXT, experience TEXT, referral TEXT,
  groups TEXT,
  terms_version TEXT, privacy_version TEXT, accepted_at REAL,
  onboarded INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL, last_login REAL
);
CREATE TABLE IF NOT EXISTS watchlist (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL, added_at REAL NOT NULL,
  PRIMARY KEY (user_id, ticker)
);
CREATE TABLE IF NOT EXISTS follows (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  pid TEXT NOT NULL, name TEXT, added_at REAL NOT NULL,
  PRIMARY KEY (user_id, pid)
);
CREATE TABLE IF NOT EXISTS push_subs (
  endpoint TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  p256dh TEXT NOT NULL, auth TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT, url TEXT, dedupe TEXT,
  created_at REAL NOT NULL, read_at REAL,
  UNIQUE (user_id, dedupe)
);
CREATE TABLE IF NOT EXISTS passkeys (
  credential_id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  public_key BLOB NOT NULL, sign_count INTEGER NOT NULL DEFAULT 0,
  name TEXT, created_at REAL NOT NULL, last_used REAL
);
-- one row per sign-in: where and on what, and how long it stayed in use
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at REAL NOT NULL, last_seen REAL NOT NULL, ended_at REAL,
  method TEXT, ip TEXT, city TEXT, region TEXT, country TEXT, cc TEXT,
  device TEXT, browser TEXT, os TEXT, revoked INTEGER NOT NULL DEFAULT 0, risk TEXT
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id, last_seen);
CREATE TABLE IF NOT EXISTS login_failures (
  ts REAL NOT NULL, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  ip TEXT, country TEXT, reason TEXT
);
"""

PROFILE_FIELDS = ("first_name", "last_name", "dob", "gender", "investor_type", "experience", "referral")
# notification settings, added after the first release (see _migrate)
NOTIFY_COLUMNS = {"email_verified": "INTEGER NOT NULL DEFAULT 0", "notify_email": "INTEGER NOT NULL DEFAULT 0",
                  "notify_push": "INTEGER NOT NULL DEFAULT 0", "notify_inapp": "INTEGER NOT NULL DEFAULT 1",
                  "summary_times": "TEXT", "summary_groups": "TEXT", "notify_set": "INTEGER NOT NULL DEFAULT 0",
                  "mfa_method": "TEXT", "mfa_secret": "TEXT", "mfa_recovery": "TEXT", "theme": "TEXT",
                  # text-message alerts: E.164 number, confirmed by a texted code, with the consent time
                  "phone": "TEXT", "phone_verified": "INTEGER NOT NULL DEFAULT 0", "notify_sms": "INTEGER NOT NULL DEFAULT 0",
                  "sms_consent_at": "REAL", "notify_events": "INTEGER NOT NULL DEFAULT 0"}


def path() -> str:
    return os.environ.get("STOCKSKILL_DB") or "data/users.db"


@contextmanager
def conn():
    p = path()
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    c = sqlite3.connect(p, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        _migrate(c)


def _migrate(c) -> None:
    """Add columns introduced after a database was created."""
    have = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
    for col, decl in NOTIFY_COLUMNS.items():
        if col not in have:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
    if "channels" not in {r["name"] for r in c.execute("PRAGMA table_info(notifications)")}:
        c.execute("ALTER TABLE notifications ADD COLUMN channels TEXT")
    if "risk" not in {r["name"] for r in c.execute("PRAGMA table_info(sessions)")}:
        c.execute("ALTER TABLE sessions ADD COLUMN risk TEXT")


def _row(r) -> dict | None:
    return dict(r) if r is not None else None


# --- users ------------------------------------------------------------------

def create_user(email: str, password_hash: str | None = None, google_sub: str | None = None,
                first_name: str | None = None, last_name: str | None = None,
                terms_version: str | None = None, privacy_version: str | None = None) -> int:
    now = time.time()
    with conn() as c:
        cur = c.execute(
            "INSERT INTO users (email, password_hash, google_sub, first_name, last_name, "
            "terms_version, privacy_version, accepted_at, created_at, last_login) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (email.strip().lower(), password_hash, google_sub, first_name, last_name,
             terms_version, privacy_version, now if terms_version else None, now, now))
        return int(cur.lastrowid)


def get_user(uid: int) -> dict | None:
    with conn() as c:
        return _row(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())


def by_email(email: str) -> dict | None:
    with conn() as c:
        return _row(c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone())


def by_google(sub: str) -> dict | None:
    with conn() as c:
        return _row(c.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone())


def update_user(uid: int, **fields) -> None:
    allowed = set(PROFILE_FIELDS) | set(NOTIFY_COLUMNS) | {"groups", "onboarded", "google_sub", "password_hash",
                                                           "last_login", "terms_version", "privacy_version",
                                                           "accepted_at"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    with conn() as c:
        c.execute(f"UPDATE users SET {', '.join(k + '=?' for k in fields)} WHERE id=?",
                  (*fields.values(), uid))


def delete_user(uid: int) -> None:
    """Remove the account and everything tied to it (watchlist, passkeys)."""
    with conn() as c:
        c.execute("DELETE FROM users WHERE id=?", (uid,))


# --- sign-in sessions ----------------------------------------------------------

SESSION_COLS = ("method", "ip", "city", "region", "country", "cc", "device", "browser", "os")


def add_session(sid: str, uid: int, **info) -> None:
    now = time.time()
    info = {k: info.get(k) for k in SESSION_COLS}
    with conn() as c:
        c.execute(f"INSERT INTO sessions (id, user_id, created_at, last_seen, {', '.join(SESSION_COLS)}) "
                  f"VALUES (?,?,?,?,{','.join('?' * len(SESSION_COLS))})",
                  (sid, uid, now, now, *[info[k] for k in SESSION_COLS]))


MAX_ACTIVE_SESSIONS = 20


def cap_sessions(uid: int, keep: int = MAX_ACTIVE_SESSIONS) -> int:
    """Sign out the least recently used devices beyond ``keep``."""
    with conn() as c:
        old = [r[0] for r in c.execute("SELECT id FROM sessions WHERE user_id=? AND ended_at IS NULL "
                                       "ORDER BY last_seen DESC LIMIT -1 OFFSET ?", (uid, keep))]
        for sid in old:
            c.execute("UPDATE sessions SET ended_at=? WHERE id=?", (time.time(), sid))
        return len(old)


def set_session_risk(sid: str, risk: str | None) -> None:
    with conn() as c:
        c.execute("UPDATE sessions SET risk=? WHERE id=?", (risk, sid))


def session_history(uid: int, exclude: str, days: float = 90) -> list[dict]:
    """Earlier sign-ins to compare a new one with, newest first."""
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM sessions WHERE user_id=? AND id != ? AND last_seen > ? ORDER BY last_seen DESC LIMIT 200",
            (uid, exclude, time.time() - days * 86400))]


def recent_failures(uid: int, seconds: float = 3600) -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM login_failures WHERE user_id=? AND ts > ?",
                         (uid, time.time() - seconds)).fetchone()[0]


def unread_count(uid: int) -> int:
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read_at IS NULL", (uid,)).fetchone()[0]


def get_session(sid: str) -> dict | None:
    with conn() as c:
        return _row(c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone())


def touch_session(sid: str) -> None:
    with conn() as c:
        c.execute("UPDATE sessions SET last_seen=? WHERE id=?", (time.time(), sid))


def end_session(sid: str) -> None:
    with conn() as c:
        c.execute("UPDATE sessions SET ended_at=COALESCE(ended_at, ?) WHERE id=?", (time.time(), sid))


def revoke_sessions(uid: int, sid: str | None = None, keep: str | None = None) -> int:
    """Sign out one session (``sid``) or all but ``keep``. Returns how many."""
    now = time.time()
    with conn() as c:
        if sid:
            cur = c.execute("UPDATE sessions SET revoked=1, ended_at=COALESCE(ended_at, ?) "
                            "WHERE id=? AND user_id=? AND ended_at IS NULL", (now, sid, uid))
        else:
            cur = c.execute("UPDATE sessions SET revoked=1, ended_at=COALESCE(ended_at, ?) "
                            "WHERE user_id=? AND id != ? AND ended_at IS NULL", (now, uid, keep or ""))
        return cur.rowcount


def user_sessions(uid: int, days: float = 30) -> list[dict]:
    """This person's sign-ins still in use or used in the last ``days`` days, newest first."""
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM sessions WHERE user_id=? AND (ended_at IS NULL OR last_seen > ?) "
            "ORDER BY ended_at IS NOT NULL, last_seen DESC LIMIT 30", (uid, time.time() - days * 86400))]


def add_login_failure(uid: int | None, ip: str, country: str | None, reason: str) -> None:
    with conn() as c:
        c.execute("INSERT INTO login_failures VALUES (?,?,?,?,?)", (time.time(), uid, ip, country, reason))


def prune_sessions(days: float = 90) -> None:
    """Drop sign-in records unused for ``days`` days (the Privacy Policy's limit)."""
    cut = time.time() - days * 86400
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE last_seen < ?", (cut,))
        c.execute("DELETE FROM login_failures WHERE ts < ?", (cut,))


# --- watchlists -------------------------------------------------------------

def watchlist(uid: int) -> list[str]:
    with conn() as c:
        return [r["ticker"] for r in c.execute(
            "SELECT ticker FROM watchlist WHERE user_id=? ORDER BY added_at, rowid", (uid,))]


def add_tickers(uid: int, tickers) -> None:
    now = time.time()
    with conn() as c:
        c.executemany("INSERT OR IGNORE INTO watchlist (user_id, ticker, added_at) VALUES (?,?,?)",
                      [(uid, t.upper(), now) for t in tickers if t])


def remove_tickers(uid: int, tickers) -> None:
    with conn() as c:
        c.executemany("DELETE FROM watchlist WHERE user_id=? AND ticker=?", [(uid, t.upper()) for t in tickers])


def set_watchlist(uid: int, tickers) -> None:
    with conn() as c:
        c.execute("DELETE FROM watchlist WHERE user_id=?", (uid,))
    add_tickers(uid, tickers)


# --- passkeys ---------------------------------------------------------------

def add_passkey(uid: int, credential_id: str, public_key: bytes, sign_count: int, name: str) -> None:
    with conn() as c:
        c.execute("INSERT INTO passkeys (credential_id, user_id, public_key, sign_count, name, created_at) "
                  "VALUES (?,?,?,?,?,?)", (credential_id, uid, public_key, sign_count, name, time.time()))


def passkeys(uid: int) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT credential_id, name, created_at, last_used FROM passkeys WHERE user_id=? ORDER BY created_at", (uid,))]


def passkey(credential_id: str) -> dict | None:
    with conn() as c:
        return _row(c.execute("SELECT * FROM passkeys WHERE credential_id=?", (credential_id,)).fetchone())


def touch_passkey(credential_id: str, sign_count: int) -> None:
    with conn() as c:
        c.execute("UPDATE passkeys SET sign_count=?, last_used=? WHERE credential_id=?",
                  (sign_count, time.time(), credential_id))


def delete_passkey(uid: int, credential_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM passkeys WHERE user_id=? AND credential_id=?", (uid, credential_id))


# --- follows, push subscriptions, notifications ---------------------------------

def follows(uid: int) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT pid, name, added_at FROM follows WHERE user_id=? ORDER BY added_at", (uid,))]


def follow(uid: int, pid: str, name: str | None) -> None:
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO follows (user_id, pid, name, added_at) VALUES (?,?,?,?)",
                  (uid, pid, name, time.time()))


def unfollow(uid: int, pid: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM follows WHERE user_id=? AND pid=?", (uid, pid))


def followers_by_pid() -> dict[str, list[tuple[int, float]]]:
    """{pid: [(user_id, followed_at)]} for everyone who follows someone."""
    out: dict = {}
    with conn() as c:
        for r in c.execute("SELECT user_id, pid, added_at FROM follows"):
            out.setdefault(r["pid"], []).append((r["user_id"], r["added_at"]))
    return out


def add_push(uid: int, endpoint: str, p256dh: str, auth: str) -> None:
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO push_subs (endpoint, user_id, p256dh, auth, created_at) VALUES (?,?,?,?,?)",
                  (endpoint, uid, p256dh, auth, time.time()))


def push_subs(uid: int) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM push_subs WHERE user_id=?", (uid,))]


def drop_push(endpoint: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM push_subs WHERE endpoint=?", (endpoint,))


def add_notification(uid: int, kind: str, title: str, body: str, url: str | None, dedupe: str) -> bool:
    """Store one notification; False if this user already has it (same dedupe key)."""
    with conn() as c:
        cur = c.execute("INSERT OR IGNORE INTO notifications (user_id, kind, title, body, url, dedupe, created_at) "
                        "VALUES (?,?,?,?,?,?,?)", (uid, kind, title, body, url, dedupe, time.time()))
        return cur.rowcount > 0


def set_delivery(uid: int, dedupe: str, channels: str) -> None:
    """Record which channels a notification actually went out on (for the admin page)."""
    with conn() as c:
        c.execute("UPDATE notifications SET channels=? WHERE user_id=? AND dedupe=?", (channels, uid, dedupe))


def notifications(uid: int, limit: int = 30) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, kind, title, body, url, created_at, read_at FROM notifications WHERE user_id=? "
            "ORDER BY created_at DESC LIMIT ?", (uid, limit))]


def mark_read(uid: int) -> None:
    with conn() as c:
        c.execute("UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL", (time.time(), uid))


def all_users() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users WHERE onboarded=1")]


def prune_notifications(days: int = 90) -> None:
    with conn() as c:
        c.execute("DELETE FROM notifications WHERE created_at < ?", (time.time() - days * 86400,))


def update_user_email(uid: int, email: str) -> None:
    with conn() as c:
        c.execute("UPDATE users SET email=?, email_verified=1 WHERE id=?", (email.strip().lower(), uid))
