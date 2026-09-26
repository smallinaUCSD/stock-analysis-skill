"""Text-message alerts through Twilio's REST API (no SDK).

Off until the host sets TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and either
TWILIO_FROM (a Twilio number, +1...) or TWILIO_MESSAGING_SERVICE_SID. US
numbers need a registered sender (toll-free verification or A2P 10DLC) before
carriers will deliver. Twilio handles STOP / HELP replies on its own.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time

import requests

MAX_LEN = 320                      # two SMS segments


def sms_ready() -> bool:
    e = os.environ.get
    return bool(e("TWILIO_ACCOUNT_SID") and e("TWILIO_AUTH_TOKEN")
                and (e("TWILIO_FROM") or e("TWILIO_MESSAGING_SERVICE_SID")))


def normalize_phone(raw: str | None) -> str | None:
    """E.164 (+15551234567) or None. Ten digits are taken as a US number."""
    s = (raw or "").strip()
    digits = re.sub(r"\D", "", s)
    if s.startswith("+"):
        return "+" + digits if 8 <= len(digits) <= 15 and not digits.startswith("0") else None
    if len(digits) == 10 and digits[0] not in "01":
        return "+1" + digits
    if len(digits) == 11 and digits[0] == "1" and digits[1] not in "01":
        return "+" + digits
    return None


def mask(phone: str | None) -> str:
    return f"(•••) •••-{phone[-4:]}" if phone else ""


def send_sms(to: str, body: str) -> tuple[bool, str | None]:
    """(sent, error)."""
    if not sms_ready():
        return False, "Text messages aren't set up on this server yet."
    e = os.environ.get
    data = {"To": to, "Body": body[:MAX_LEN]}
    if e("TWILIO_MESSAGING_SERVICE_SID"):
        data["MessagingServiceSid"] = e("TWILIO_MESSAGING_SERVICE_SID")
    else:
        data["From"] = e("TWILIO_FROM")
    try:
        r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{e('TWILIO_ACCOUNT_SID')}/Messages.json",
                          data=data, auth=(e("TWILIO_ACCOUNT_SID"), e("TWILIO_AUTH_TOKEN")), timeout=15)
    except requests.RequestException as ex:
        return False, f"Couldn't reach the text-message service ({type(ex).__name__})."
    if r.status_code in (200, 201):
        return True, None
    try:
        msg = r.json().get("message") or ""
    except ValueError:
        msg = ""
    return False, "The text-message service refused it" + (f": {msg}" if msg else ".")


def alert_text(brand: str, title: str, body: str, url: str) -> str:
    """One short text: brand, headline, the gist, a link and the opt-out line."""
    tail = f"\n{url}\nReply STOP to opt out."
    room = MAX_LEN - len(tail) - len(brand) - len(title) - 4
    gist = (body or "").replace("\n", " ").strip()
    if len(gist) > room:
        gist = gist[:max(0, room - 1)].rstrip() + "…"
    return f"{brand}: {title}" + (f". {gist}" if gist and room > 20 else "") + tail


# --- confirmation codes (in memory; they last 10 minutes) ------------------------

_CODES: dict[int, dict] = {}


def new_code(uid: int, phone: str) -> str:
    code = f"{secrets.randbelow(10 ** 6):06d}"
    _CODES[uid] = {"phone": phone, "hash": hashlib.sha256(code.encode()).hexdigest(),
                   "exp": time.time() + 600, "tries": 0}
    return code


def check_code(uid: int, code: str) -> str | None:
    """The confirmed phone number, or None (wrong, expired or too many tries)."""
    rec = _CODES.get(uid)
    if not rec or time.time() > rec["exp"] or rec["tries"] >= 5:
        _CODES.pop(uid, None)
        return None
    rec["tries"] += 1
    if hmac.compare_digest(rec["hash"], hashlib.sha256(re.sub(r"\D", "", code or "").encode()).hexdigest()):
        _CODES.pop(uid, None)
        return rec["phone"]
    return None
