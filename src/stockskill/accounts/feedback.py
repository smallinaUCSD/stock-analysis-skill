"""Hearing from people: the Feedback button on every signed-in page, and the
"Was this brief useful?" links at the foot of each emailed brief.

* Feedback: POST /api/feedback stores the message with the page, browser and
  window size, and emails the admins (STOCKSKILL_ADMINS). The admin page lists it
  with a status (new / planned / shipped / won't do) and a private note.
* Brief ratings: each summary email carries Yes / No links signed for that
  person and that brief. The link opens a small page whose script records the
  answer, so the link scanners some mail providers run can't vote; the page then
  offers an optional "what would make it better?" box.
"""

from __future__ import annotations

import html
import os
import threading
from urllib.parse import quote

from flask import current_app, jsonify, request, session

from . import db

RATE_SALT = "rate:"
RATE_MAX_AGE = 45 * 86400
SKIP_WIDGET = {"/login", "/signup", "/welcome", "/verify-email", "/forgot", "/reset", "/logout", "/brief/rate",
               "/terms", "/privacy"}


# --- brief rating links (used by notify.deliver) -----------------------------------

def rating_links(u: dict, key: str) -> tuple[str, str]:
    """(HTML line, plain-text line) with this person's Yes / No links for one brief."""
    from .notify import public_url, token
    t = token(u["id"], u["email"], RATE_SALT + key)
    base = f"{public_url()}/brief/rate?k={quote(key)}&t={t}&v="
    html_line = ('<span style="color:#6c6a64;font-size:14px">Was this brief useful? '
                 f'<a href="{html.escape(base)}yes" style="color:#cc785c">Yes</a> · '
                 f'<a href="{html.escape(base)}no" style="color:#cc785c">No</a></span>')
    return html_line, f"Was this brief useful? Yes: {base}yes  No: {base}no"


def _rater(key: str, tok: str) -> dict | None:
    from .notify import read_token
    d = read_token(tok or "", RATE_SALT + (key or ""), RATE_MAX_AGE)
    u = db.get_user(d["u"]) if d else None
    return u if u and u["email"] == d.get("e") else None


# --- the widget -------------------------------------------------------------------

WIDGET = """
<div id="smi-fb" aria-live="polite">
<button type="button" id="smi-fb-btn" aria-expanded="false" aria-controls="smi-fb-panel">Feedback</button>
<div id="smi-fb-panel" hidden>
  <div class="smi-fb-h">Tell us what you think<button type="button" id="smi-fb-x" aria-label="Close">&times;</button></div>
  <p class="smi-fb-sub">Something confusing, missing or broken? Every message is read.</p>
  <textarea id="smi-fb-msg" maxlength="2000" rows="5" placeholder="What would make this better?"></textarea>
  <div class="smi-fb-row"><span id="smi-fb-st"></span><button type="button" id="smi-fb-send">Send</button></div>
</div></div>
<style>
#smi-fb{position:fixed;left:16px;bottom:16px;z-index:2147483000;font:15px/1.4 var(--font,Georgia,serif)}
#smi-fb-btn{height:36px;padding:0 16px;border-radius:999px;border:1px solid var(--border-strong,rgba(250,249,245,.25));
  background:var(--surface,#252320);color:var(--ink,#faf9f5);cursor:pointer;font:inherit;box-shadow:0 6px 20px rgba(0,0,0,.25)}
#smi-fb-btn:hover{border-color:var(--accent,#cc785c)}
#smi-fb-panel{position:absolute;left:0;bottom:46px;width:min(340px,calc(100vw - 32px));background:var(--surface,#252320);
  color:var(--ink,#faf9f5);border:1px solid var(--border-strong,rgba(250,249,245,.25));border-radius:14px;padding:14px 14px 12px;
  box-shadow:0 18px 50px rgba(0,0,0,.35)}
.smi-fb-h{display:flex;justify-content:space-between;align-items:center;font-weight:600}
#smi-fb-x{border:none;background:none;color:var(--muted,#a09d96);font-size:22px;line-height:1;cursor:pointer}
.smi-fb-sub{margin:4px 0 10px;color:var(--muted,#a09d96);font-size:13px}
#smi-fb-msg{width:100%;box-sizing:border-box;resize:vertical;border-radius:10px;border:1px solid var(--border-strong,rgba(250,249,245,.25));
  background:var(--bg,#1f1e1b);color:var(--ink,#faf9f5);padding:8px 10px;font:inherit}
.smi-fb-row{display:flex;justify-content:space-between;align-items:center;margin-top:8px;gap:8px}
#smi-fb-st{font-size:13px;color:var(--muted,#a09d96)}
#smi-fb-send{height:34px;padding:0 16px;border:none;border-radius:999px;background:var(--accent,#cc785c);color:#1a1512;font:inherit;font-weight:600;cursor:pointer}
#smi-fb-send:disabled{opacity:.6;cursor:default}
@media print{#smi-fb{display:none}}
</style>
<script>
(function(){
  if(window.top!==window.self){ var n=document.getElementById('smi-fb'); if(n) n.remove(); return; }
  var btn=document.getElementById('smi-fb-btn'), pnl=document.getElementById('smi-fb-panel'), msg=document.getElementById('smi-fb-msg'),
      st=document.getElementById('smi-fb-st'), send=document.getElementById('smi-fb-send');
  function show(on){ pnl.hidden=!on; btn.setAttribute('aria-expanded', on?'true':'false'); if(on){ st.textContent=''; msg.focus(); } }
  btn.onclick=function(){ show(pnl.hidden); };
  document.getElementById('smi-fb-x').onclick=function(){ show(false); btn.focus(); };
  document.addEventListener('keydown',function(e){ if(e.key==='Escape' && !pnl.hidden){ show(false); btn.focus(); } });
  send.onclick=function(){
    var t=msg.value.trim(); if(t.length<2){ st.textContent='Write a few words first.'; return; }
    send.disabled=true; st.textContent='Sending…';
    fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:t,page:location.pathname,viewport:innerWidth+'x'+innerHeight})})
      .then(function(r){ return r.json().then(function(d){ return {ok:r.ok&&d.ok,d:d}; }); })
      .then(function(x){ send.disabled=false;
        if(x.ok){ msg.value=''; st.textContent='Thanks! We read every message.'; setTimeout(function(){ show(false); },1800); }
        else st.textContent=(x.d&&x.d.error)||'Could not send. Try again.'; })
      .catch(function(){ send.disabled=false; st.textContent='Could not send. Try again.'; });
  };
})();
</script>
"""


def _admins() -> list[str]:
    return [e.strip() for e in (os.environ.get("STOCKSKILL_ADMINS") or "").split(",") if e.strip()]


def _email_admins(u: dict, page: str, ua: str, viewport: str, message: str, fid: int) -> None:
    from .notify import public_url, send_simple
    who = html.escape(" ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or u["email"])
    lines = [f"<b>From:</b> {who} ({html.escape(u['email'])})", f"<b>Page:</b> {html.escape(page or '?')} · "
             f"{html.escape(viewport or '?')}", f"<b>Browser:</b> {html.escape((ua or '?')[:160])}",
             html.escape(message).replace("\n", "<br>")]
    for to in _admins():
        try:
            send_simple(to, f"Feedback #{fid}: {message[:60]}", lines, public_url() + "/admin", "Open admin")
        except Exception:  # noqa: BLE001
            pass


# --- routes -----------------------------------------------------------------------

def init_app(app) -> None:
    from .auth import _limited, current_user
    from .pages import _LG_CSS, _WZ_CSS, _brand_link, _shell, message_html

    @app.post("/api/feedback")
    def send_feedback():
        u = current_user()
        if not u:
            return jsonify({"ok": False, "error": "Please sign in."}), 401
        b = request.get_json(silent=True) or {}
        message = str(b.get("message") or "").strip()
        if len(message) < 2:
            return jsonify({"ok": False, "error": "Write a few words first."}), 400
        if len(message) > 2000:
            return jsonify({"ok": False, "error": "That's a bit long: keep it under 2,000 characters."}), 400
        if _limited(f"feedback:{u['id']}", 8, 3600):
            return jsonify({"ok": False, "error": "Thanks! That's a lot of messages for one hour; try again later."}), 429
        page = str(b.get("page") or "")[:200].split("?")[0]
        viewport = str(b.get("viewport") or "")[:20]
        ua = request.headers.get("User-Agent", "")[:300]
        fid = db.add_feedback(u["id"], page, ua, viewport, message)
        threading.Thread(target=_email_admins, args=(u, page, ua, viewport, message, fid), daemon=True).start()
        return jsonify({"ok": True, "id": fid})

    @app.get("/brief/rate")
    def rate_page():
        k, t, v = request.args.get("k", ""), request.args.get("t", ""), request.args.get("v", "")
        if v not in ("yes", "no") or not _rater(k, t):
            return message_html("Link expired", "That link is invalid or too old. Thanks for wanting to tell us, "
                                "though: the Feedback button in the app works any time."), 400
        payload = html.escape(f'{{"k":{_js(k)},"t":{_js(t)},"v":{_js(v)}}}', quote=True)
        body = (f'<div class="lg-wrap"><div class="wz-top">{_brand_link()}<a class="small" href="/">Home</a></div>'
                f'<div class="wz-card" id="rt" data-p="{payload}"><h1>Thanks for the feedback</h1>'
                f'<p class="lead" id="rt-msg" style="color:var(--muted)">Saving your answer…</p>'
                '<div class="field"><label for="rt-c">What would make the brief more useful? (optional)</label>'
                '<textarea class="inp" id="rt-c" rows="4" maxlength="1000" style="height:auto;padding:10px"></textarea></div>'
                '<button class="btn primary" id="rt-send" type="button">Send</button> '
                '<a class="btn ghost" href="/">Go to your watchlist</a></div></div>')
        js = """
(function(){ var el=document.getElementById('rt'), p=JSON.parse(el.dataset.p), m=document.getElementById('rt-msg');
  function post(extra){ return fetch('/api/brief/rate',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(Object.assign({},p,extra||{}))}).then(function(r){ return r.json(); }); }
  post().then(function(d){ m.textContent=d.ok?(p.v==='yes'?'Glad it helped. Your answer is saved.':'Sorry it missed. Your answer is saved.'):(d.error||'Could not save it.'); })
        .catch(function(){ m.textContent='Could not save it. Try the link again.'; });
  document.getElementById('rt-send').onclick=function(){ var c=document.getElementById('rt-c').value.trim(); if(!c) return;
    this.disabled=true; post({comment:c}).then(function(d){ m.textContent=d.ok?'Thank you! We read every comment.':(d.error||'Could not save it.'); }); };
})();"""
        return _shell("Thanks · SM Investments", body, _WZ_CSS + _LG_CSS, js)

    @app.post("/api/brief/rate")
    def rate_api():
        b = request.get_json(silent=True) or {}
        k, v = str(b.get("k") or ""), b.get("v")
        u = _rater(k, str(b.get("t") or ""))
        if not u or v not in ("yes", "no"):
            return jsonify({"ok": False, "error": "That link is invalid or too old."}), 400
        if _limited(f"rate:{u['id']}", 30, 3600):
            return jsonify({"ok": False, "error": "Too many tries. Try again later."}), 429
        comment = str(b.get("comment") or "").strip()[:1000] or None
        db.rate_brief(u["id"], k[:80], v == "yes", comment)
        return jsonify({"ok": True})

    def _admin_only():
        check = current_app.config.get("IS_ADMIN")
        return bool(check and check())

    @app.get("/api/admin/feedback")
    def admin_feedback():
        if not _admin_only():
            return jsonify({"ok": False}), 404
        days = min(max(request.args.get("days", type=int) or 30, 7), 90)
        return jsonify({"ok": True, "feedback": db.feedback_list(), "ratings": db.brief_rating_stats(days)})

    @app.post("/api/admin/feedback/<int:fid>")
    def admin_feedback_set(fid: int):
        if not _admin_only():
            return jsonify({"ok": False}), 404
        b = request.get_json(silent=True) or {}
        ok = db.set_feedback(fid, b.get("status"), b.get("note"))
        return jsonify({"ok": ok}), (200 if ok else 400)

    @app.after_request
    def _feedback_widget(resp):
        try:
            if (resp.status_code != 200 or resp.mimetype != "text/html" or resp.direct_passthrough
                    or "Content-Encoding" in resp.headers or not session.get("uid")
                    or request.path in SKIP_WIDGET or request.path.startswith("/embed")):
                return resp
            data = resp.get_data()
            i = data.rfind(b"</body>")
            if i < 0 or b'id="smi-fb"' in data:
                return resp
            resp.set_data(data[:i] + WIDGET.encode() + data[i:])
        except Exception:  # noqa: BLE001
            pass
        return resp


def _js(s: str) -> str:
    import json
    return json.dumps(s)
