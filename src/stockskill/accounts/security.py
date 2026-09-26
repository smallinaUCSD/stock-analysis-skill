"""Account security: 2-step verification (authenticator app or emailed code,
plus one-time backup codes), password reset, changing the account email, and
the emails that go with them (welcome, reset, security notices).

Passkeys and Google sign-in already verify the person strongly, so 2-step
verification applies to email + password sign-ins. ``totp`` is RFC 6238
(the standard authenticator-app algorithm), pure and tested.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import struct
import threading
import time

from flask import jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .auth import (_EMAIL_RE, _body, _limited, _login, _next_for, bp, current_user, login_required)

ISSUER = "SM Investments"


# --- authenticator codes (TOTP) ---------------------------------------------------

def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    counter = int((time.time() if at is None else at) // step)
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return f"{code:0{digits}d}"


def check_totp(secret: str, code: str, at: float | None = None) -> int | None:
    """The time step the code matches (allowing one step of clock drift), or None."""
    code = "".join(c for c in str(code) if c.isdigit())
    now = time.time() if at is None else at
    for drift in (0, -1, 1):
        t = now + drift * 30
        if len(code) == 6 and hmac.compare_digest(totp(secret, t), code):
            return int(t // 30)
    return None


def otpauth_uri(secret: str, email: str) -> str:
    from urllib.parse import quote
    return f"otpauth://totp/{quote(ISSUER)}:{quote(email)}?secret={secret}&issuer={quote(ISSUER)}"


def qr_svg(data: str) -> str:
    import io
    import segno
    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="svg", scale=5, border=2, dark="#141413", light="#ffffff",
                                     xmldecl=False, svgns=True)
    return buf.getvalue().decode()


# --- backup codes -------------------------------------------------------------------

def new_recovery_codes(n: int = 10) -> tuple[list[str], str]:
    """(codes to show once, JSON of their hashes to store)."""
    codes = []
    for _ in range(n):
        raw = base64.b32encode(secrets.token_bytes(5)).decode().lower()
        codes.append(raw[:4] + "-" + raw[4:8])
    return codes, json.dumps([generate_password_hash(c) for c in codes])


def use_recovery_code(u: dict, code: str) -> bool:
    code = code.strip().lower().replace(" ", "")
    if len(code) == 8:
        code = code[:4] + "-" + code[4:]
    hashes = json.loads(u.get("mfa_recovery") or "[]")
    for i, h in enumerate(hashes):
        if check_password_hash(h, code):
            db.update_user(u["id"], mfa_recovery=json.dumps(hashes[:i] + hashes[i + 1:]))
            return True
    return False


# --- emailed codes (in memory, 10 minutes, 5 tries) ------------------------------------

_CODES: dict = {}
_CODES_LOCK = threading.Lock()
_USED_STEPS: dict = {}          # last authenticator time step used per user (no replays)


def send_code(u: dict, purpose: str) -> bool:
    from . import notify
    code = f"{secrets.randbelow(10 ** 6):06d}"
    with _CODES_LOCK:
        _CODES[(u["id"], purpose)] = (generate_password_hash(code), time.time() + 600, 0)
    what = "sign in" if purpose == "login" else "turn on 2-step verification"
    return notify.send_simple(u["email"], f"Your code: {code}",
                              [f"Your code to {what} is <b style=\"font-size:22px;letter-spacing:3px\">{code}</b>.",
                               "It expires in 10 minutes. If you didn't try to sign in, change your password."])


def check_code(uid: int, purpose: str, code: str) -> bool:
    code = "".join(c for c in str(code) if c.isdigit())
    with _CODES_LOCK:
        rec = _CODES.get((uid, purpose))
        if not rec or rec[1] < time.time() or rec[2] >= 5:
            _CODES.pop((uid, purpose), None)
            return False
        ok = check_password_hash(rec[0], code)
        if ok:
            _CODES.pop((uid, purpose), None)
        else:
            _CODES[(uid, purpose)] = (rec[0], rec[1], rec[2] + 1)
        return ok


def verify_second_factor(u: dict, code: str) -> bool:
    """Authenticator code, emailed code or a backup code for this user."""
    code = (code or "").strip()
    if u.get("mfa_method") == "totp" and u.get("mfa_secret"):
        step = check_totp(u["mfa_secret"], code)
        if step is not None and _USED_STEPS.get(u["id"]) != step:
            _USED_STEPS[u["id"]] = step
            return True
    if u.get("mfa_method") == "email" and check_code(u["id"], "login", code):
        return True
    return use_recovery_code(u, code)


def _mask(email: str) -> str:
    name, _, dom = email.partition("@")
    return (name[:1] + "•" * max(1, len(name) - 1)) + "@" + dom


def notice(u: dict, subject: str, text: str) -> None:
    """A security email, sent in the background so the request stays fast."""
    from . import notify
    lines = [html.escape(text), "If this wasn't you, reset your password right away and contact us."]
    threading.Thread(target=notify.send_simple, args=(u["email"], subject, lines), daemon=True).start()


# --- the second step at sign-in ----------------------------------------------------------

def start_mfa(u: dict, nxt: str | None):
    """Called by the password sign-in when 2-step verification is on."""
    session.clear()
    session["mfa_uid"] = u["id"]
    session["mfa_at"] = time.time()
    session["mfa_next"] = nxt or ""
    hint = None
    if u.get("mfa_method") == "email":
        send_code(u, "login")
        hint = _mask(u["email"])
    return jsonify({"ok": False, "mfa": u.get("mfa_method"), "email_hint": hint})


@bp.post("/auth/mfa")
def finish_mfa():
    uid, at = session.get("mfa_uid"), session.get("mfa_at") or 0
    if not uid or time.time() - at > 600:
        session.clear()
        return jsonify({"ok": False, "error": "That took too long. Sign in again."}), 401
    if _limited(f"mfa:{uid}", 8):
        return jsonify({"ok": False, "error": "Too many attempts. Wait 15 minutes and try again."}), 429
    u = db.get_user(uid)
    if not u or not verify_second_factor(u, _body().get("code") or ""):
        from .auth import _failed
        _failed(u, "wrong 2-step code")
        return jsonify({"ok": False, "error": "That code didn't work. Check it and try again."}), 401
    nxt = session.get("mfa_next")
    _login(uid, "password + " + ("authenticator app" if u.get("mfa_method") == "totp" else "emailed code"))
    return jsonify({"ok": True, "next": _next_for(u, nxt)})


@bp.post("/auth/mfa/resend")
def resend_mfa():
    uid = session.get("mfa_uid")
    u = db.get_user(uid) if uid else None
    if not u or u.get("mfa_method") != "email" or _limited(f"mfa-resend:{uid}", 3):
        return jsonify({"ok": False, "error": "Can't send another code right now."}), 400
    send_code(u, "login")
    return jsonify({"ok": True})


# --- turning 2-step verification on and off ------------------------------------------------

def _check_password(u: dict, pw: str) -> bool:
    return not u.get("password_hash") or check_password_hash(u["password_hash"], pw or "")


@bp.post("/api/me/mfa/totp/start")
@login_required
def totp_start():
    u = current_user()
    secret = new_secret()
    session["mfa_setup"] = secret
    uri = otpauth_uri(secret, u["email"])
    return jsonify({"ok": True, "secret": secret, "uri": uri, "qr": qr_svg(uri)})


@bp.post("/api/me/mfa/email/start")
@login_required
def email_mfa_start():
    from . import notify
    u = current_user()
    if not notify.email_ready():
        return jsonify({"ok": False, "error": "Email isn't set up on this server."}), 400
    if _limited(f"mfa-setup:{u['id']}", 5, 3600):
        return jsonify({"ok": False, "error": "Try again later."}), 429
    ok = send_code(u, "setup")
    return jsonify({"ok": ok, "error": None if ok else (notify.LAST_ERROR["msg"] or "The email couldn't be sent.")})


@bp.post("/api/me/mfa/confirm")
@login_required
def mfa_confirm():
    b = _body()
    u = current_user()
    method = b.get("method")
    if method == "totp":
        secret = session.get("mfa_setup")
        if not secret or check_totp(secret, b.get("code") or "") is None:
            return jsonify({"ok": False, "error": "That code didn't match. Check the time on your phone and try again."}), 400
        fields = {"mfa_method": "totp", "mfa_secret": secret}
    elif method == "email":
        if not check_code(u["id"], "setup", b.get("code") or ""):
            return jsonify({"ok": False, "error": "That code didn't match or has expired."}), 400
        fields = {"mfa_method": "email", "mfa_secret": None, "email_verified": 1}
    else:
        return jsonify({"ok": False, "error": "Choose a method."}), 400
    codes, stored = new_recovery_codes()
    db.update_user(u["id"], mfa_recovery=stored, **fields)
    session.pop("mfa_setup", None)
    notice(u, "2-step verification is on", "2-step verification was turned on for your account.")
    return jsonify({"ok": True, "recovery_codes": codes})


@bp.post("/api/me/mfa/disable")
@login_required
def mfa_disable():
    b = _body()
    u = current_user()
    if _limited(f"mfa-off:{u['id']}", 8):
        return jsonify({"ok": False, "error": "Too many attempts."}), 429
    if not _check_password(u, b.get("password") or ""):
        return jsonify({"ok": False, "error": "Your password is incorrect."}), 400
    db.update_user(u["id"], mfa_method=None, mfa_secret=None, mfa_recovery=None)
    notice(u, "2-step verification is off", "2-step verification was turned off for your account.")
    return jsonify({"ok": True})


@bp.post("/api/me/mfa/recovery")
@login_required
def mfa_new_recovery():
    u = current_user()
    if not u.get("mfa_method"):
        return jsonify({"ok": False, "error": "2-step verification is off."}), 400
    if not _check_password(u, _body().get("password") or ""):
        return jsonify({"ok": False, "error": "Your password is incorrect."}), 400
    codes, stored = new_recovery_codes()
    db.update_user(u["id"], mfa_recovery=stored)
    return jsonify({"ok": True, "recovery_codes": codes})


# --- forgot password ---------------------------------------------------------------------

def _reset_payload(u: dict) -> dict:
    # tied to the current password, so the link stops working once it's used
    return {"u": u["id"], "e": u["email"], "h": hashlib.sha256((u.get("password_hash") or "none").encode()).hexdigest()[:16]}


@bp.post("/auth/forgot")
def forgot():
    from . import notify
    email = (_body().get("email") or "").strip().lower()
    if _limited("forgot-ip:" + (request.remote_addr or "?"), 10, 3600) or _limited("forgot:" + email, 3, 3600):
        return jsonify({"ok": False, "error": "Too many requests. Try again in an hour."}), 429
    u = db.by_email(email) if _EMAIL_RE.match(email) else None
    if u:
        send_reset(u)
    # the same answer whether or not the account exists
    return jsonify({"ok": True})


def send_reset(u: dict, why: str = "Someone asked to reset the password for this account.") -> None:
    from itsdangerous import URLSafeTimedSerializer
    from . import notify
    tok = URLSafeTimedSerializer(notify._secret(), salt="reset").dumps(_reset_payload(u))
    link = f"{notify.public_url()}/reset?t={tok}"
    threading.Thread(target=notify.send_simple, args=(u["email"], "Reset your password", [
        html.escape(why),
        f'<a href="{html.escape(link)}">Choose a new password</a> (the link works once, for one hour).',
        "If you didn't ask for this, ignore this email; your password hasn't changed."]), daemon=True).start()


# --- unusual sign-ins -------------------------------------------------------------------------

def unusual_sign_in(u: dict, new: dict, reasons: list[str]) -> None:
    """Tell the person about a sign-in that doesn't look like them: email (always),
    the Today panel, browser notifications and a text if they have those on."""
    from itsdangerous import URLSafeTimedSerializer
    from .. import geoip
    from . import notify, risk
    from .pages import BRAND
    if not u or _limited(f"unusual:{u['id']}", 5, 3600):
        return
    from datetime import datetime
    from zoneinfo import ZoneInfo
    when = datetime.now(ZoneInfo("America/New_York")).strftime("%a %b %-d at %-I:%M %p ET")
    place = geoip.label(new) or "an unknown location"
    device = f"{new.get('browser') or 'a browser'} on {new.get('os') or 'an unknown system'}"
    tok = URLSafeTimedSerializer(notify._secret(), salt="notme").dumps({"u": u["id"], "s": new["id"]})
    notme = f"{notify.public_url()}/security/not-me?t={tok}"
    title = "Unusual sign-in to your account" if set(reasons) & {"failed attempts", "impossible travel", "new country"} \
        else "New sign-in to your account"
    lines = [f"Your {html.escape(BRAND)} account was signed in to on {html.escape(when)} from "
             f"<b>{html.escape(place)}</b> (address {html.escape(new.get('ip') or 'unknown')}) using {html.escape(device)}.",
             html.escape(risk.explain(reasons)),
             "<b>If this was you,</b> there's nothing to do.",
             f'<b>If it wasn\'t you,</b> <a href="{html.escape(notme)}">sign out everywhere and secure your account</a>. '
             "We'll sign out every device and send you a link to choose a new password."]
    threading.Thread(target=notify.send_simple, args=(u["email"], title, lines, notify.public_url() + "/account",
                                                      "See where you're signed in"), daemon=True).start()
    short = f"{place}, {device}"
    try:
        db.add_notification(u["id"], "security", title, "\n".join(html.unescape(notify._strip_tags(x)) for x in lines),
                            "/account", f"signin:{new['id']}")
    except Exception:  # noqa: BLE001
        pass

    def extra():
        try:
            notify.send_push(u["id"], title, short, "/account")
        except Exception:  # noqa: BLE001
            pass
        if u.get("phone_verified") and u.get("phone"):
            from . import sms
            sms.send_sms(u["phone"], f"{BRAND}: {title.lower().capitalize()} from {short}. Not you? {notme}")
    threading.Thread(target=extra, daemon=True).start()


def _notme_payload(tok: str) -> dict | None:
    from itsdangerous import BadSignature, URLSafeTimedSerializer
    from . import notify
    try:
        return URLSafeTimedSerializer(notify._secret(), salt="notme").loads(tok or "", max_age=14 * 86400)
    except BadSignature:
        return None


@bp.get("/security/not-me")
def not_me_page():
    """The link in an unusual sign-in alert. A page with a button (a POST), so
    an email scanner opening the link doesn't sign anyone out."""
    from .pages import not_me_html
    d = _notme_payload(request.args.get("t") or "")
    if not d or not db.get_user(d["u"]):
        return not_me_html(None), 400
    return not_me_html(request.args.get("t"))


@bp.post("/security/not-me")
def not_me():
    d = _notme_payload(_body().get("t") or "")
    u = db.get_user(d["u"]) if d else None
    if not u:
        return jsonify({"ok": False, "error": "This link has expired. Sign in and use Account settings instead."}), 400
    n = db.revoke_sessions(u["id"])
    from .auth import _SEEN
    _SEEN.clear()
    if session.get("uid") == u["id"]:
        session.clear()
    if u.get("password_hash"):
        send_reset(u, "You told us a sign-in to your account wasn't you, so we signed out every device.")
    notice(u, "We signed out all your devices", f"At your request we signed out {n} device(s). "
           + ("Use the link we emailed to choose a new password, then sign in again." if u.get("password_hash")
              else "Sign in again with Google, and check your Google account's security settings."))
    return jsonify({"ok": True, "signed_out": n, "password": bool(u.get("password_hash"))})


@bp.post("/auth/reset")
def reset_password():
    from itsdangerous import BadSignature, URLSafeTimedSerializer
    from . import notify
    b = _body()
    try:
        d = URLSafeTimedSerializer(notify._secret(), salt="reset").loads(b.get("token") or "", max_age=3600)
    except BadSignature:
        d = None
    u = db.get_user(d["u"]) if d else None
    if not u or _reset_payload(u) != d:
        return jsonify({"ok": False, "error": "This reset link has expired or was already used. Request a new one."}), 400
    pw = b.get("password") or ""
    if len(pw) < 10 or len(set(pw)) < 5:
        return jsonify({"ok": False, "error": "Use a password of at least 10 characters."}), 400
    db.update_user(u["id"], password_hash=generate_password_hash(pw), email_verified=1)
    db.revoke_sessions(u["id"])                      # a reset signs out every device
    from .auth import _SEEN
    _SEEN.clear()
    notice(u, "Your password was changed", "The password for your account was just reset.")
    return jsonify({"ok": True, "next": "/login"})


# --- changing the account email ----------------------------------------------------------

@bp.post("/api/me/email")
@login_required
def change_email():
    from itsdangerous import URLSafeTimedSerializer
    from . import notify
    b = _body()
    u = current_user()
    new = (b.get("email") or "").strip().lower()
    if not _EMAIL_RE.match(new):
        return jsonify({"ok": False, "error": "Enter a valid email address."}), 400
    if new == u["email"]:
        return jsonify({"ok": False, "error": "That's already your email."}), 400
    if not _check_password(u, b.get("password") or ""):
        return jsonify({"ok": False, "error": "Your password is incorrect."}), 400
    if db.by_email(new):
        return jsonify({"ok": False, "error": "Another account already uses that email."}), 409
    if not notify.email_ready():
        return jsonify({"ok": False, "error": "Email isn't set up on this server."}), 400
    if _limited(f"email-change:{u['id']}", 5, 3600):
        return jsonify({"ok": False, "error": "Try again later."}), 429
    tok = URLSafeTimedSerializer(notify._secret(), salt="email-change").dumps({"u": u["id"], "e": u["email"], "n": new})
    link = f"{notify.public_url()}/account/email/confirm?t={tok}"
    ok = notify.send_simple(new, "Confirm your new email", [
        f"Confirm that you want to use this address ({html.escape(new)}) for your account.",
        f'<a href="{html.escape(link)}">Confirm my new email</a> (the link works for 24 hours).'])
    return jsonify({"ok": ok, "error": None if ok else (notify.LAST_ERROR["msg"] or "The email couldn't be sent.")})


@bp.get("/account/email/confirm")
def confirm_email_change():
    from itsdangerous import BadSignature, URLSafeTimedSerializer
    from . import notify
    from .pages import message_html
    try:
        d = URLSafeTimedSerializer(notify._secret(), salt="email-change").loads(request.args.get("t", ""), max_age=86400)
    except BadSignature:
        d = None
    u = db.get_user(d["u"]) if d else None
    if not u or u["email"] != d["e"]:
        return message_html("Link expired", "This link has expired or was already used."), 400
    if db.by_email(d["n"]):
        return message_html("Email in use", "Another account already uses that email address."), 409
    db.update_user_email(u["id"], d["n"])
    notice(u, "Your account email was changed",
           f"The email for your account was changed from {u['email']} to {d['n']}.")
    return message_html("Email changed", f"Your account now uses {d['n']}. Use it the next time you sign in.")


# --- welcome ----------------------------------------------------------------------------------

def welcome(u: dict, verify: bool) -> None:
    from . import notify
    if not notify.email_ready():
        return
    name = (u.get("first_name") or "").strip()
    lines = [f"Welcome{', ' + html.escape(name) if name else ''}! Your account is ready.",
             "Pick your sectors and indices and your watchlist builds itself. From there: valuations from SEC filings, "
             "ten years of financials, earnings reactions, the screener and trade trackers."]
    if verify:
        tok = notify.token(u["id"], u["email"], "verify")
        link = f"{notify.public_url()}/notifications/verify?t={tok}"
        lines.append(f'<a href="{html.escape(link)}">Confirm your email address</a> so we can send your summaries '
                     "and alerts, and help you if you forget your password.")
    threading.Thread(target=notify.send_simple, args=(u["email"], "Welcome to SM Investments", lines), daemon=True).start()
