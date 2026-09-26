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
