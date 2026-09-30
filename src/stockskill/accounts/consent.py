"""Cookie consent and the cookie policy.

Essential cookies (signing in, remembering a device that passed 2-step, this
choice) are always on. The one optional cookie is the "how you found us" one
(attribution.py): it's set only until someone chooses "Essential only", and that
choice deletes it and keeps it from coming back. The banner shows on every page
until a choice is made; /cookies lists every cookie and lets people change it.
"""

from __future__ import annotations

from flask import jsonify, request

COOKIE = "smi_consent"
YEAR = 365 * 86400

COOKIES = [  # (name, kind, purpose, lasts)
    ("smi_session", "Essential", "Keeps you signed in and protects forms from cross-site requests.", "30 days"),
    ("smi_dev", "Essential", "Remembers that this browser passed 2-step verification, so you're not asked for a "
                             "code every time.", "30 days"),
    ("smi_consent", "Essential", "Remembers your cookie choice.", "1 year"),
    ("smi_src", "Optional", "Remembers how you found us (the campaign tag on a link, or the site that linked to us) "
                            "so we know which places bring people. Never shared.", "60 days"),
]

BANNER = """
<div id="smi-ck" role="region" aria-label="Cookie choice">
  <p>We use essential cookies to keep you signed in and secure, and, if you're OK with it, one that remembers how you
  found us. No advertising or cross-site tracking. <a href="/cookies">Cookie policy</a></p>
  <div class="smi-ck-b"><button type="button" data-c="essential">Essential only</button><button type="button" data-c="all" class="p">Accept</button></div>
</div>
<style>
#smi-ck{position:fixed;left:50%;transform:translateX(-50%);bottom:16px;z-index:2147483001;width:min(640px,calc(100vw - 32px));
  box-sizing:border-box;display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:14px 16px;
  background:var(--surface,#252320);color:var(--ink,#faf9f5);border:1px solid var(--border-strong,rgba(250,249,245,.25));border-radius:14px;
  box-shadow:0 18px 50px rgba(0,0,0,.35);font:14px/1.45 var(--font,Georgia,serif)}
#smi-ck p{margin:0;flex:1 1 300px} #smi-ck a{color:var(--accent,#cc785c)}
.smi-ck-b{display:flex;gap:8px}
.smi-ck-b button{height:34px;padding:0 14px;border-radius:999px;border:1px solid var(--border-strong,rgba(250,249,245,.25));
  background:transparent;color:inherit;font:inherit;cursor:pointer}
.smi-ck-b button.p{background:var(--accent,#cc785c);border-color:var(--accent,#cc785c);color:#1a1512;font-weight:600}
@media (max-width:600px){#smi-ck{bottom:64px}}
@media print{#smi-ck{display:none}}
</style>
<script>
(function(){ var b=document.getElementById('smi-ck'); if(!b) return; if(window.top!==window.self){ b.remove(); return; }
  b.addEventListener('click',function(e){ var t=e.target.closest('button[data-c]'); if(!t) return;
    fetch('/api/consent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({choice:t.dataset.c})})
      .finally(function(){ b.remove(); }); }); })();
</script>
"""


def choice() -> str | None:
    c = request.cookies.get(COOKIE)
    return c if c in ("all", "essential") else None


def optional_allowed() -> bool:
    return choice() != "essential"


def init_app(app) -> None:
    from .pages import _LG_CSS, _WZ_CSS, _brand_link, _shell

    @app.post("/api/consent")
    def set_consent():
        c = (request.get_json(silent=True) or {}).get("choice")
        if c not in ("all", "essential"):
            return jsonify({"ok": False, "error": "Choose all or essential."}), 400
        resp = jsonify({"ok": True, "choice": c})
        secure = request.is_secure or bool(app.config.get("SESSION_COOKIE_SECURE"))
        resp.set_cookie(COOKIE, c, max_age=YEAR, samesite="Lax", secure=secure)
        if c == "essential":
            from .attribution import COOKIE as SRC
            resp.delete_cookie(SRC)
        return resp

    @app.get("/cookies")
    def cookie_policy():
        import html
        rows = "".join(f"<tr><td><code>{n}</code></td><td>{k}</td><td>{html.escape(p)}</td><td>{d}</td></tr>"
                       for n, k, p, d in COOKIES)
        cur = {"all": "You accepted all cookies.", "essential": "You chose essential cookies only."}.get(
            choice() or "", "You haven't made a choice yet.")
        body = (f'<div class="lg-wrap"><div class="wz-top">{_brand_link()}<a class="small" href="/">Home</a></div>'
                '<div class="wz-card"><h1>Cookie policy</h1>'
                '<p class="lead" style="color:var(--muted)">We use a small number of first-party cookies. None are for '
                'advertising, none track you across other sites, and we don\'t use third-party analytics.</p>'
                '<table class="ck-t"><thead><tr><th>Cookie</th><th>Kind</th><th>What it does</th><th>Kept for</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>'
                f'<p id="ck-cur"><b>{cur}</b> Essential cookies are needed for the site to work, so they\'re always on.</p>'
                '<p><button class="btn ghost" data-c="essential">Essential only</button> '
                '<button class="btn primary" data-c="all">Accept all</button></p>'
                '<p class="small muted">See also the <a href="/privacy">Privacy Policy</a>.</p></div></div>')
        js = """document.addEventListener('click',function(e){ var t=e.target.closest('button[data-c]'); if(!t) return;
  post('/api/consent',{choice:t.dataset.c}).then(function(d){ if(d.ok) document.getElementById('ck-cur').firstChild.textContent=
    d.choice==='all'?'You accepted all cookies.':'You chose essential cookies only.'; }); });"""
        css = (".ck-t{width:100%;border-collapse:collapse;font-size:14px;margin:12px 0}.ck-t th,.ck-t td{text-align:left;"
               "padding:8px 6px;border-top:1px solid var(--border);vertical-align:top}.ck-t th{color:var(--muted);font-weight:500}")
        return _shell("Cookie policy · SM Investments", body, _WZ_CSS + _LG_CSS + css, js)

    @app.after_request
    def _consent_banner(resp):
        try:
            if choice() == "essential" and request.cookies.get("smi_src"):
                resp.delete_cookie("smi_src")
            if (choice() or resp.status_code != 200 or resp.mimetype != "text/html" or resp.direct_passthrough
                    or "Content-Encoding" in resp.headers or request.path.startswith("/embed")
                    or request.path == "/cookies"):
                return resp
            data = resp.get_data()
            i = data.rfind(b"</body>")
            if i < 0 or b'id="smi-ck"' in data:
                return resp
            resp.set_data(data[:i] + BANNER.encode() + data[i:])
        except Exception:  # noqa: BLE001
            pass
        return resp
