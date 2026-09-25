"""Sign-up, sign-in (email + password, Google, passkeys), onboarding and
account APIs, and the gate that sends signed-out visitors to the landing page.

Enabled with ``STOCKSKILL_AUTH=1`` (the public copy of the site). Sessions are
signed cookies (HttpOnly, SameSite=Lax, Secure over HTTPS). State-changing
requests must come from our own origin. Sign-in attempts are rate-limited.
"""

from __future__ import annotations

import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import date
from urllib.parse import quote, urlparse

from flask import Blueprint, current_app, g, jsonify, redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, legal
from .groups import groups as all_groups, tickers_for

bp = Blueprint("accounts", __name__)

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$")
INVESTOR_TYPES = {
    "casual": "Casual investor",
    "longterm": "Long-term, buy-and-hold investor",
    "etf": "ETF and index-fund investor",
    "active": "Active trader or day trader",
    "options": "Options trader",
    "crypto": "Crypto investor",
    "advisor": "Financial advisor or wealth manager",
    "professional": "Hedge fund or asset-management professional",
    "student": "Student or learning to invest",
    "other": "Other",
}
EXPERIENCE = {"beginner": "Just starting", "intermediate": "A few years", "advanced": "Very experienced"}
GENDERS = {"female": "Female", "male": "Male", "nonbinary": "Non-binary", "self": "Prefer to self-describe",
           "na": "Prefer not to say"}
REFERRALS = {"friend": "A friend or colleague", "search": "Search engine", "social": "Social media",
             "reddit": "Reddit or a forum", "news": "News or a blog", "other": "Other"}
_PUBLIC_PATHS = {"/", "/login", "/signup", "/terms", "/privacy", "/healthz", "/favicon.ico", "/logout"}
_ONBOARD_OK = {"/welcome", "/account", "/logout", "/terms", "/privacy"}


# --- setup ------------------------------------------------------------------

def _secret_key() -> str:
    k = os.environ.get("STOCKSKILL_SECRET_KEY")
    if k:
        return k
    path = os.path.join(os.path.dirname(db.path()) or ".", ".secret_key")
    try:
        return open(path).read().strip()
    except OSError:
        k = secrets.token_hex(32)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600), "w") as f:
            f.write(k)
        return k


def init_app(app, board, tickers_path: str, cache_dir) -> None:
    from datetime import timedelta
    from werkzeug.middleware.proxy_fix import ProxyFix
    # the app listens on 127.0.0.1 behind Tailscale/Cloudflare, which pass the
    # real host, scheme and client IP in X-Forwarded-* headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.secret_key = _secret_key()
    secure = _public_url().startswith("https://")
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=secure, SESSION_COOKIE_NAME="smi_session",
                      PERMANENT_SESSION_LIFETIME=timedelta(days=30))
    app.config["ACCT"] = {"board": board, "tickers_path": tickers_path, "cache_dir": cache_dir}
    db.init()
    app.before_request(_gate)
    app.register_blueprint(bp)


def _public_url() -> str:
    return (os.environ.get("STOCKSKILL_PUBLIC_URL") or "").rstrip("/")


def _origin() -> str:
    return _public_url() or f"{request.scheme}://{request.host}"


def _rp_id() -> str:
    return urlparse(_origin()).hostname or "localhost"


# --- sessions ---------------------------------------------------------------

def current_user() -> dict | None:
    if "user" not in g:
        uid = session.get("uid")
        g.user = db.get_user(uid) if uid else None
        if uid and not g.user:
            session.clear()
    return g.user


def needs_terms(u: dict) -> bool:
    return u.get("terms_version") != legal.TERMS_VERSION or u.get("privacy_version") != legal.PRIVACY_VERSION


def _login(uid: int) -> None:
    session.clear()
    session["uid"] = uid
    session.permanent = True
    db.update_user(uid, last_login=time.time())
    g.pop("user", None)


def _next_for(u: dict, want: str | None = None) -> str:
    if not u.get("onboarded") or needs_terms(u):
        return "/welcome"
    if want and want.startswith("/") and not want.startswith("//") and not want.startswith("/\\"):
        return want
    return "/"


def _gate():
    """Signed-out visitors see only the landing, sign-in and legal pages;
    signed-in users finish onboarding before using the app."""
    p = request.path
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not _same_origin():
        return jsonify({"ok": False, "error": "Request blocked (cross-site)."}), 403
    if p in _PUBLIC_PATHS or p.startswith("/auth/"):
        return None
    u = current_user()
    if not u:
        if p.startswith("/api/"):
            return jsonify({"ok": False, "error": "Please sign in."}), 401
        return redirect("/login?next=" + quote(request.full_path.rstrip("?"), safe="/?=&"))
    if not u.get("onboarded") or needs_terms(u):
        if p in _ONBOARD_OK or p.startswith("/api/me") or p == "/api/groups":
            return None
        if p.startswith("/api/"):
            return jsonify({"ok": False, "error": "Finish setting up your account first."}), 403
        return redirect("/welcome")
    return None


def _same_origin() -> bool:
    src = request.headers.get("Origin") or request.headers.get("Referer")
    if not src:
        return True                       # non-browser clients; the session cookie is SameSite=Lax
    host = urlparse(src).netloc
    allowed = {request.host, urlparse(_public_url()).netloc} - {""}
    return host in allowed


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrap(*a, **k):
        if not current_user():
            return jsonify({"ok": False, "error": "Please sign in."}), 401
        return fn(*a, **k)
    return wrap


# --- rate limiting ------------------------------------------------------------

_HITS: dict = defaultdict(deque)
_HITS_LOCK = threading.Lock()


def _limited(key: str, limit: int, window: float = 900.0) -> bool:
    now = time.time()
    with _HITS_LOCK:
        q = _HITS[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def _ip() -> str:
    return request.remote_addr or "?"


# --- email + password ---------------------------------------------------------

def _body() -> dict:
    return request.get_json(silent=True) or {}


@bp.post("/auth/signup")
def signup():
    b = _body()
    email = (b.get("email") or "").strip().lower()
    pw = b.get("password") or ""
    if _limited("signup:" + _ip(), 10, 3600):
        return jsonify({"ok": False, "error": "Too many attempts. Try again later."}), 429
    if not _EMAIL_RE.match(email):
        return jsonify({"ok": False, "error": "Enter a valid email address."}), 400
    if len(pw) < 10 or len(pw) > 200:
        return jsonify({"ok": False, "error": "Use a password of at least 10 characters."}), 400
    if pw.lower() == email or pw.isdigit() or len(set(pw)) < 5:
        return jsonify({"ok": False, "error": "That password is too easy to guess."}), 400
    if not b.get("accept"):
        return jsonify({"ok": False, "error": "Please accept the Terms of Service and Privacy Policy."}), 400
    if db.by_email(email):
        return jsonify({"ok": False, "error": "An account with this email already exists. Sign in instead."}), 409
    uid = db.create_user(email, password_hash=generate_password_hash(pw),
                         terms_version=legal.TERMS_VERSION, privacy_version=legal.PRIVACY_VERSION)
    _login(uid)
    return jsonify({"ok": True, "next": "/welcome"})


@bp.post("/auth/login")
def login():
    b = _body()
    email = (b.get("email") or "").strip().lower()
    pw = b.get("password") or ""
    if _limited("login-ip:" + _ip(), 20) or _limited("login:" + email, 8):
        return jsonify({"ok": False, "error": "Too many attempts. Wait 15 minutes and try again."}), 429
    u = db.by_email(email) if email else None
    # same message whether the email exists or not
    if not u or not u.get("password_hash") or not check_password_hash(u["password_hash"], pw):
        if u and not u.get("password_hash") and u.get("google_sub"):
            return jsonify({"ok": False, "error": "This account uses Sign in with Google."}), 401
        return jsonify({"ok": False, "error": "Email or password is incorrect."}), 401
    _login(u["id"])
    return jsonify({"ok": True, "next": _next_for(u, b.get("next"))})


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect("/") if request.method == "GET" else jsonify({"ok": True, "next": "/"})


# --- Google -------------------------------------------------------------------

def google_client_id() -> str | None:
    return (os.environ.get("GOOGLE_CLIENT_ID") or "").strip() or None


def verify_google_token(token: str, client_id: str) -> dict | None:
    """Claims from a Google ID token, checked by Google's token endpoint and
    against our client id; None if invalid."""
    try:
        import requests
        r = requests.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": token}, timeout=10)
        c = r.json() if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None
    if not c or c.get("aud") != client_id or c.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        return None
    if int(c.get("exp") or 0) < time.time() or str(c.get("email_verified")).lower() != "true":
        return None
    return c


@bp.post("/auth/google")
def google_login():
    cid = google_client_id()
    if not cid:
        return jsonify({"ok": False, "error": "Google sign-in isn't set up on this server."}), 400
    if _limited("google:" + _ip(), 30):
        return jsonify({"ok": False, "error": "Too many attempts. Try again later."}), 429
    c = verify_google_token(_body().get("credential") or "", cid)
    if not c:
        return jsonify({"ok": False, "error": "Google sign-in failed. Please try again."}), 401
    sub, email = c["sub"], c["email"].lower()
    u = db.by_google(sub) or db.by_email(email)
    if u:
        if not u.get("google_sub"):
            db.update_user(u["id"], google_sub=sub)        # link Google to the existing account
    else:
        # new account: they accept the Terms on the first onboarding screen
        uid = db.create_user(email, google_sub=sub, first_name=c.get("given_name"), last_name=c.get("family_name"))
        u = db.get_user(uid)
    _login(u["id"])
    return jsonify({"ok": True, "next": _next_for(u, _body().get("next"))})


# --- passkeys (WebAuthn) ------------------------------------------------------

def _b64(b: bytes) -> str:
    from webauthn.helpers import bytes_to_base64url
    return bytes_to_base64url(b)


def _unb64(s: str) -> bytes:
    from webauthn.helpers import base64url_to_bytes
    return base64url_to_bytes(s)


@bp.post("/auth/passkey/register/options")
@login_required
def passkey_register_options():
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                          ResidentKeyRequirement, UserVerificationRequirement)
    u = current_user()
    name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or u["email"]
    opts = generate_registration_options(
        rp_id=_rp_id(), rp_name=legal.operator(), user_name=u["email"], user_display_name=name,
        user_id=f"smi-{u['id']}".encode(),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.PREFERRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=_unb64(p["credential_id"])) for p in db.passkeys(u["id"])])
    session["pk_reg"] = _b64(opts.challenge)
    return current_app.response_class(options_to_json(opts), mimetype="application/json")


@bp.post("/auth/passkey/register/verify")
@login_required
def passkey_register_verify():
    from webauthn import verify_registration_response
    chal = session.pop("pk_reg", None)
    b = _body()
    if not chal:
        return jsonify({"ok": False, "error": "That took too long. Try again."}), 400
    try:
        v = verify_registration_response(credential=b.get("credential"), expected_challenge=_unb64(chal),
                                         expected_origin=_origin(), expected_rp_id=_rp_id())
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"The passkey couldn't be verified ({e})."}), 400
    label = (b.get("name") or "").strip()[:60] or _device_label()
    db.add_passkey(current_user()["id"], _b64(v.credential_id), v.credential_public_key, v.sign_count, label)
    return jsonify({"ok": True})


def _device_label() -> str:
    ua = request.headers.get("User-Agent", "")
    for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android phone"),
                      ("Macintosh", "Mac"), ("Windows", "Windows PC")):
        if key in ua:
            return name
    return "Passkey"


@bp.post("/auth/passkey/login/options")
def passkey_login_options():
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement
    if _limited("pk:" + _ip(), 40):
        return jsonify({"ok": False, "error": "Too many attempts. Try again later."}), 429
    opts = generate_authentication_options(rp_id=_rp_id(), user_verification=UserVerificationRequirement.PREFERRED)
    session["pk_auth"] = _b64(opts.challenge)
    return current_app.response_class(options_to_json(opts), mimetype="application/json")


@bp.post("/auth/passkey/login/verify")
def passkey_login_verify():
    from webauthn import verify_authentication_response
    chal = session.pop("pk_auth", None)
    b = _body()
    cred = b.get("credential") or {}
    pk = db.passkey(cred.get("id") or "") if isinstance(cred, dict) else None
    if not chal or not pk:
        return jsonify({"ok": False, "error": "That passkey isn't recognised. Sign in another way."}), 401
    try:
        v = verify_authentication_response(credential=cred, expected_challenge=_unb64(chal), expected_rp_id=_rp_id(),
                                           expected_origin=_origin(), credential_public_key=pk["public_key"],
                                           credential_current_sign_count=pk["sign_count"])
    except Exception:  # noqa: BLE001
        return jsonify({"ok": False, "error": "The passkey couldn't be verified."}), 401
    db.touch_passkey(pk["credential_id"], v.new_sign_count)
    _login(pk["user_id"])
    return jsonify({"ok": True, "next": _next_for(db.get_user(pk["user_id"]), b.get("next"))})


# --- onboarding + account -------------------------------------------------------

def _cfg() -> dict:
    return current_app.config["ACCT"]


def _public_user(u: dict) -> dict:
    keep = ("email", "first_name", "last_name", "dob", "gender", "investor_type", "experience", "referral",
            "onboarded", "created_at")
    out = {k: u.get(k) for k in keep}
    out["groups"] = [x for x in (u.get("groups") or "").split(",") if x]
    out["has_password"] = bool(u.get("password_hash"))
    out["google_linked"] = bool(u.get("google_sub"))
    out["needs_terms"] = needs_terms(u)
    return out


@bp.get("/api/me")
@login_required
def me():
    u = current_user()
    return jsonify({"ok": True, "user": _public_user(u), "watchlist": db.watchlist(u["id"]),
                    "passkeys": db.passkeys(u["id"]),
                    # ordered [key, label] pairs (a JSON object would be re-sorted alphabetically)
                    "options": {k: [[a, b] for a, b in m.items()] for k, m in (
                        ("investor_types", INVESTOR_TYPES), ("experience", EXPERIENCE), ("genders", GENDERS),
                        ("referrals", REFERRALS))},
                    "terms_version": legal.TERMS_VERSION, "google": bool(google_client_id())})


@bp.get("/api/groups")
@login_required
def groups_api():
    c = _cfg()
    return jsonify({"ok": True, "groups": [{k: g_[k] for k in ("key", "label", "kind", "blurb")} |
                                           {"count": len(g_["tickers"]), "tickers": g_["tickers"]}
                                           for g_ in all_groups(c["tickers_path"], c["cache_dir"])]})


@bp.post("/api/me/terms")
@login_required
def accept_terms():
    if not _body().get("accept"):
        return jsonify({"ok": False, "error": "Please accept to continue."}), 400
    db.update_user(current_user()["id"], terms_version=legal.TERMS_VERSION,
                   privacy_version=legal.PRIVACY_VERSION, accepted_at=time.time())
    return jsonify({"ok": True})


def _ensure_on_board(tickers) -> None:
    """Tickers not yet on the shared board are added to it (in the background)."""
    board = _cfg().get("board")
    if not board:
        return
    try:
        missing = sorted(set(tickers) - board._current_tickers())
    except Exception:  # noqa: BLE001
        return
    for i in range(0, len(missing), 50):
        board.add_bulk(missing[i:i + 50])


@bp.post("/api/me/groups")
@login_required
def set_groups():
    c = _cfg()
    valid = {g_["key"] for g_ in all_groups(c["tickers_path"], c["cache_dir"])}
    keys = [k for k in (_body().get("groups") or []) if k in valid]
    if not keys:
        return jsonify({"ok": False, "error": "Pick at least one."}), 400
    tks = tickers_for(keys, c["tickers_path"], c["cache_dir"])
    u = current_user()
    db.update_user(u["id"], groups=",".join(keys))
    if _body().get("replace", True):
        db.set_watchlist(u["id"], tks)
    else:
        db.add_tickers(u["id"], tks)
    _ensure_on_board(tks)
    return jsonify({"ok": True, "count": len(db.watchlist(u["id"]))})


def _age(dob: date, today: date | None = None) -> int:
    t = today or date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def validate_profile(b: dict) -> tuple[dict, str | None]:
    """Clean profile fields, or an error message."""
    out = {}
    for k in ("first_name", "last_name"):
        v = re.sub(r"\s+", " ", str(b.get(k) or "")).strip()
        if not v or len(v) > 60:
            return {}, "Please enter your first and last name."
        out[k] = v
    try:
        dob = date.fromisoformat(str(b.get("dob") or ""))
    except ValueError:
        return {}, "Please enter your date of birth."
    age = _age(dob)
    if age < 18:
        return {}, "You must be 18 or older to use this service."
    if age > 120:
        return {}, "Please check your date of birth."
    out["dob"] = dob.isoformat()
    for k, allowed, required in (("investor_type", INVESTOR_TYPES, True), ("experience", EXPERIENCE, True),
                                 ("gender", GENDERS, False), ("referral", REFERRALS, False)):
        v = b.get(k) or None
        if v is None and not required:
            out[k] = None
            continue
        if v not in allowed:
            return {}, {"investor_type": "Tell us what kind of investor you are.",
                        "experience": "Choose your experience level."}.get(k, "Please check your answers.")
        out[k] = v
    return out, None


@bp.post("/api/me/profile")
@login_required
def save_profile():
    fields, err = validate_profile(_body())
    if err:
        return jsonify({"ok": False, "error": err}), 400
    db.update_user(current_user()["id"], **fields)
    return jsonify({"ok": True})


@bp.post("/api/me/onboarded")
@login_required
def finish_onboarding():
    u = current_user()
    if needs_terms(u) or not u.get("dob") or not db.watchlist(u["id"]):
        return jsonify({"ok": False, "error": "A step is still missing."}), 400
    db.update_user(u["id"], onboarded=1)
    return jsonify({"ok": True, "next": "/"})


@bp.post("/api/me/watchlist")
@login_required
def edit_watchlist():
    from ..server.watchlist_service import parse_ticker_list
    b = _body()
    add = [t for t in parse_ticker_list(b.get("add") or []) if re.fullmatch(r"[A-Z0-9.\-^=]{1,12}", t)][:50]
    rem = parse_ticker_list(b.get("remove") or [])
    uid = current_user()["id"]
    if add:
        db.add_tickers(uid, add)
        _ensure_on_board(add)
    if rem:
        db.remove_tickers(uid, rem)
    return jsonify({"ok": True, "watchlist": db.watchlist(uid)})


@bp.delete("/api/me/passkeys/<cid>")
@login_required
def remove_passkey(cid: str):
    db.delete_passkey(current_user()["id"], cid)
    return jsonify({"ok": True})


@bp.post("/api/me/delete")
@login_required
def delete_account():
    if (_body().get("confirm") or "").strip().upper() != "DELETE":
        return jsonify({"ok": False, "error": 'Type DELETE to confirm.'}), 400
    db.delete_user(current_user()["id"])
    session.clear()
    return jsonify({"ok": True, "next": "/"})


@bp.post("/api/me/password")
@login_required
def set_password():
    b = _body()
    u = current_user()
    pw = b.get("password") or ""
    if u.get("password_hash") and not check_password_hash(u["password_hash"], b.get("current") or ""):
        return jsonify({"ok": False, "error": "Your current password is incorrect."}), 400
    if len(pw) < 10 or len(set(pw)) < 5:
        return jsonify({"ok": False, "error": "Use a password of at least 10 characters."}), 400
    db.update_user(u["id"], password_hash=generate_password_hash(pw))
    return jsonify({"ok": True})
