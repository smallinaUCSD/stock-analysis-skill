"""HTML for the landing page, sign-in, onboarding, account settings and the
legal pages. Uses the board's design tokens (cream canvas, coral accent,
Cormorant headings, Source Serif body)."""

from __future__ import annotations

import html
import json

from ..dashboard.render import _CSS, _THEME_BOOT, icon
from . import legal

BRAND = "SMI Research"


def _shell(title: str, body: str, css: str = "", js: str = "", head: str = "") -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)}</title>"
            "<meta name=\"description\" content=\"Stock research built on official filings: valuations, "
            "financials, earnings, a market-wide screener, supply chains and insider trades.\">"
            + _THEME_BOOT + HEAD_PWA + head + "<style>" + _CSS + _BASE_CSS + css + "</style></head><body>" + body
            + "<script>" + _COMMON_JS + js + "</script></body></html>")


def _brand_link() -> str:
    return f'<a class="brand" href="/">{_LOGO}<span>{BRAND}</span></a>'


_LOGO = ('<svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><rect x="1" y="1" width="24" height="24" '
         'rx="7" fill="var(--accent)"/><path d="M6 17l4.5-5 3.5 3 6-7" fill="none" stroke="var(--accent-ink)" '
         'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')

_BASE_CSS = """
body{margin:0}
[hidden]{display:none!important}
a{color:var(--link)}
.brand{display:inline-flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink);font-family:var(--font-display);
  font-size:24px;font-weight:500;letter-spacing:-.01em}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 20px;border-radius:var(--r);
  font:500 15px var(--font);text-decoration:none;cursor:pointer;border:1px solid transparent;
  transition:background .15s var(--ease-out),border-color .15s var(--ease-out),transform .1s var(--ease-out)}
.btn:active{transform:scale(.98)}
.btn.primary{background:var(--accent);color:var(--accent-ink)} .btn.primary:hover{background:var(--accent-press)}
.btn.ghost{background:transparent;color:var(--ink);border-color:var(--border-strong)} .btn.ghost:hover{background:var(--surface)}
.btn[disabled]{opacity:.55;cursor:not-allowed;transform:none}
.btn.block{width:100%}
.field{display:flex;flex-direction:column;gap:6px;margin:0 0 14px}
.field label{font-size:13px;color:var(--muted)}
.inp{height:44px;padding:0 12px;border-radius:var(--r);border:1px solid var(--border-strong);background:var(--bg);
  color:var(--ink);font:15px var(--font);width:100%;box-sizing:border-box}
.inp:focus{outline:2px solid color-mix(in srgb,var(--accent) 45%,transparent);outline-offset:1px;border-color:var(--accent)}
select.inp{appearance:auto}
.err{color:var(--down);font-size:14px;min-height:20px;margin:6px 0}
.ok-msg{color:var(--up);font-size:14px}
.muted{color:var(--muted)}
.small{font-size:13px}
.divider{display:flex;align-items:center;gap:12px;color:var(--muted);font-size:13px;margin:16px 0}
.divider:before,.divider:after{content:"";flex:1;height:1px;background:var(--border)}
.au-accept{display:flex;gap:10px;align-items:flex-start;font-size:13px;line-height:1.5;color:var(--muted);margin:4px 0 6px}
.au-accept input{margin-top:3px;flex:none;width:16px;height:16px;accent-color:var(--accent)}
"""

_COMMON_JS = r"""
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function post(url, body){ return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',
  body:JSON.stringify(body||{})}).then(function(r){ return r.json().catch(function(){ return {ok:false,error:'Something went wrong.'}; }); }); }
// --- passkeys (WebAuthn) ---
function b64u(buf){ var s='',b=new Uint8Array(buf); for(var i=0;i<b.length;i++) s+=String.fromCharCode(b[i]);
  return btoa(s).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,''); }
function unb64u(s){ s=s.replace(/-/g,'+').replace(/_/g,'/'); while(s.length%4) s+='='; var b=atob(s), a=new Uint8Array(b.length);
  for(var i=0;i<b.length;i++) a[i]=b.charCodeAt(i); return a.buffer; }
function passkeySupported(){ return !!(window.PublicKeyCredential && navigator.credentials && navigator.credentials.create); }
function createPasskey(name){
  return fetch('/auth/passkey/register/options',{method:'POST',credentials:'same-origin'}).then(function(r){return r.json();}).then(function(o){
    if(o.ok===false) throw new Error(o.error);
    o.challenge=unb64u(o.challenge); o.user.id=unb64u(o.user.id);
    (o.excludeCredentials||[]).forEach(function(c){ c.id=unb64u(c.id); });
    return navigator.credentials.create({publicKey:o});
  }).then(function(c){
    var r=c.response, body={id:c.id,rawId:b64u(c.rawId),type:c.type,authenticatorAttachment:c.authenticatorAttachment||undefined,
      response:{clientDataJSON:b64u(r.clientDataJSON),attestationObject:b64u(r.attestationObject),
                transports:r.getTransports?r.getTransports():[]},clientExtensionResults:c.getClientExtensionResults?c.getClientExtensionResults():{}};
    return post('/auth/passkey/register/verify',{credential:body,name:name||''});
  });
}
function signInWithPasskey(next){
  return fetch('/auth/passkey/login/options',{method:'POST',credentials:'same-origin'}).then(function(r){return r.json();}).then(function(o){
    if(o.ok===false) throw new Error(o.error);
    o.challenge=unb64u(o.challenge); (o.allowCredentials||[]).forEach(function(c){ c.id=unb64u(c.id); });
    return navigator.credentials.get({publicKey:o});
  }).then(function(c){
    var r=c.response, body={id:c.id,rawId:b64u(c.rawId),type:c.type,authenticatorAttachment:c.authenticatorAttachment||undefined,
      response:{clientDataJSON:b64u(r.clientDataJSON),authenticatorData:b64u(r.authenticatorData),signature:b64u(r.signature),
                userHandle:r.userHandle?b64u(r.userHandle):null},clientExtensionResults:{}};
    return post('/auth/passkey/login/verify',{credential:body,next:next||''});
  });
}
function pkError(e){ var n=(e&&e.name)||''; if(n==='NotAllowedError'||n==='AbortError') return 'Passkey request was cancelled.';
  if(n==='InvalidStateError') return 'This device already has a passkey for your account.'; return (e&&e.message)||'Passkey failed.'; }
"""


# --- landing -------------------------------------------------------------------

_FEATURES = [
    ("chart", "A live market board", "Every stock you follow with signals, trend, volume, 52-week range and a quick-look "
     "chart, updated through the trading day, as a table, cards or a heatmap."),
    ("scale", "Valuations from SEC filings", "Discounted cash flow built on three years of reported cash flow, a reverse "
     "DCF that shows the growth the price assumes, and industry peer multiples."),
    ("book", "Ten years of financials", "Income statement, balance sheet and cash flow as filed, with 17 ratios, split-"
     "adjusted per-share numbers and growth rates, side by side."),
    ("calendar", "Earnings, measured", "Who reports next, and how each stock has actually moved the session after its "
     "last twelve reports, timed to the minute from the company's own filing."),
    ("filter", "A market-wide screener", "Filter all 5,900 US-listed stocks by size, sector, valuation, margins and growth, "
     "with presets and CSV export."),
    ("graph", "Supply-chain maps", "Who a company buys from, who buys from it (including customers over 10% of revenue "
     "from its annual report), what it owns and who it competes with."),
    ("users", "Congress, the President and hedge funds", "Two years of reported trades by members of Congress, the President's "
     "filings and 21 major funds' holdings, with profiles and track records."),
    ("pulse", "Economy and rates", "The CPI, jobs, GDP and Fed calendar with the latest readings, and the Treasury yield "
     "curve with its inversion history."),
    ("target", "Forecast ranges and option ideas", "Where a price could be in 1 to 12 months from what options imply, "
     "and defined-risk option structures priced from the real chain."),
    ("bell", "Alerts on your phone", "Price levels, big moves, breakouts, insider purchases and next-day earnings, pushed "
     "to your phone."),
]

_ICONS = {
    "chart": '<path d="M4 19V5M4 19h16M8 15l3-4 3 2 5-6"/>',
    "scale": '<path d="M12 3v18M5 7h14M7 7l-3 7a3 3 0 006 0zM17 7l-3 7a3 3 0 006 0z"/>',
    "book": '<path d="M5 4h9a4 4 0 014 4v12H9a4 4 0 01-4-4zM5 16a4 4 0 014-4h9"/>',
    "calendar": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    "filter": '<path d="M4 5h16l-6 8v6l-4-2v-4z"/>',
    "graph": '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="7" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 7l7.5 0M7.5 8l3.5 8M16.8 9l-3.6 7"/>',
    "users": '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0112 0M16 5a3 3 0 010 6M21 20a6 6 0 00-4-5.6"/>',
    "pulse": '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
    "target": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/>',
    "bell": '<path d="M6 16V11a6 6 0 0112 0v5l2 2H4zM10 20a2 2 0 004 0"/>',
    "check": '<path d="M5 12l5 5 9-10"/>',
}


def _ico(name: str, size: int = 22) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICONS[name]}</svg>')


def landing_html() -> str:
    feats = "".join(f'<div class="lp-feat"><div class="lp-fi">{_ico(k)}</div><h3>{html.escape(t)}</h3>'
                    f'<p>{html.escape(d)}</p></div>' for k, t, d in _FEATURES)
    diff = [
        ("Math you can check", "Every number, from a fair-value estimate to a forecast range, comes from tested code "
         "applied to real data. No language model is asked to guess a price."),
        ("Honest about what works", "We backtest our own signals and publish the result, including when a signal did "
         "not beat an ordinary day. You see the evidence next to the number."),
        ("Straight from the source", "Financial statements and customers from SEC filings, economic data from the BLS "
         "and Treasury, trades from official disclosures. Sources are labeled throughout."),
        ("Terminal breadth, without the terminal", "Financials, earnings, screening, supply chains, insider and "
         "political trades, rates and alerts in one place, instead of five subscriptions."),
    ]
    diff_html = "".join(f'<div class="lp-diff"><span class="lp-dk">{_ico("check", 18)}</span><div><h3>{html.escape(a)}'
                        f'</h3><p>{html.escape(b)}</p></div></div>' for a, b in diff)
    rows = [("10 years of statements from SEC filings", "Some", "Yes", "Yes"),
            ("Customers over 10% of revenue, from the 10-K", "No", "Yes", "Yes"),
            ("Congress, President and hedge-fund trades", "Some", "Yes", "Yes"),
            ("Earnings moves timed to the release", "No", "Yes", "Yes"),
            ("Screen every US stock", "Some", "Yes", "Yes"),
            ("Published backtests of every signal", "No", "Rarely", "Yes"),
            ("Price", "Free with ads", "$20,000+ a year", "Free in beta")]

    def cell(v):
        cls = "y" if v == "Yes" else "n" if v == "No" else ""
        return f'<td class="{cls}">{html.escape(v)}</td>'
    table = "".join(f"<tr><th>{html.escape(r[0])}</th>{cell(r[1])}{cell(r[2])}{cell(r[3])}</tr>" for r in rows)
    tiers = [
        ("Free", "$0", "during the beta", True, ["The live market board and your own watchlist",
                                                  "Valuations, financials and earnings", "The market-wide screener",
                                                  "Supply-chain maps and trade trackers", "Economy calendar and yield curve"]),
        ("Plus", "Coming soon", "", False, ["Everything in Free", "More alerts and saved screens", "Portfolio tracking",
                                            "Exports and email digests"]),
        ("Pro", "Coming soon", "", False, ["Everything in Plus", "Deeper history and faster data", "API access",
                                           "Priority support"]),
    ]
    tier_html = ""
    for name, price, note, live, items in tiers:
        li = "".join(f"<li>{_ico('check', 16)}<span>{html.escape(x)}</span></li>" for x in items)
        cta = ('<a class="btn primary block" href="/signup">Get started free</a>' if live
               else '<button class="btn ghost block" disabled>Coming soon</button>')
        tier_html += (f'<div class="lp-tier{" live" if live else ""}"><h3>{name}</h3>'
                      f'<div class="lp-price">{html.escape(price)}</div><div class="lp-pnote">{html.escape(note) or "&nbsp;"}</div>'
                      f'<ul>{li}</ul>{cta}</div>')
    faq = [("Is this financial advice?", "No. It's research and education. We aren't a registered investment adviser, "
            "and nothing here is a recommendation to buy or sell anything. See our Terms."),
           ("Where does the data come from?", "Company filings from the SEC, economic data from the BLS, BEA, Treasury and "
            "the Federal Reserve, prices and listings from market-data providers. Sources are labeled throughout."),
           ("What does it cost?", "It's free while in beta. Paid plans with extra features are coming; you'll never be "
            "charged without choosing a plan."),
           ("What do you do with my information?", "We use it to run your account and personalize your watchlist. We "
            "don't sell it and don't use ad trackers. You can delete your account at any time.")]
    faq_html = "".join(f"<details class='lp-q'><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>"
                       for q, a in faq)
    spark = ('<svg viewBox="0 0 220 60" class="lp-spark" aria-hidden="true"><path d="M0 48 C20 46 28 40 42 42 S66 30 80 32 '
             '104 20 118 24 142 12 158 16 182 8 196 10 212 4 220 3" fill="none" stroke="var(--up)" stroke-width="2.2"/>'
             '<path d="M0 48 C20 46 28 40 42 42 S66 30 80 32 104 20 118 24 142 12 158 16 182 8 196 10 212 4 220 3 V60 H0Z" '
             'fill="var(--up)" opacity=".08"/></svg>')
    mock = f"""<div class="lp-mock" aria-hidden="true">
  <div class="lp-mh"><span class="lp-dot"></span><span class="lp-dot"></span><span class="lp-dot"></span></div>
  <div class="lp-mrow top"><div><div class="lp-tk">Your watchlist</div><div class="muted small">Signals, trend and valuation at a glance</div></div></div>
  <div class="lp-card"><div class="lp-ch"><b>Semiconductor leader</b><span class="lp-badge up">Strong uptrend</span></div>{spark}
    <div class="lp-stats"><span><small>Fair value range</small>Bear · Base · Bull</span><span><small>Next report</small>After the close</span>
    <span><small>Typical earnings move</small>±5.6%</span></div></div>
  <div class="lp-mini"><div><small>10-year revenue</small><div class="lp-bars">{''.join(f'<i style="height:{h}%"></i>' for h in (12, 16, 19, 18, 26, 38, 39, 58, 82, 100))}</div></div>
    <div><small>Who buys from it</small><div class="lp-nodes"><span>Cust 1 · 22%</span><span>Cust 2 · 14%</span><span>Cloud providers</span></div></div></div>
</div>"""
    body = f"""<header class="lp-nav"><div class="lp-in">{_brand_link()}
  <nav><a href="#features">Features</a><a href="#why">Why us</a><a href="#pricing">Pricing</a></nav>
  <div class="lp-auth"><a class="lp-signin" href="/login">Sign in</a><a class="btn primary" href="/signup">Get started</a></div></div></header>
<main>
<section class="lp-hero"><div class="lp-in lp-hgrid">
  <div><p class="lp-eyebrow">Free during the beta</p>
  <h1>Research stocks the way professionals do.</h1>
  <p class="lp-lead">Valuations built on SEC filings, ten years of financials, earnings reactions, a screener for every US
  stock, supply-chain maps and the trades of Congress and hedge funds, all in one place, with every number shown and
  sourced.</p>
  <div class="lp-cta"><a class="btn primary" href="/signup">Create a free account</a><a class="btn ghost" href="#features">See what's inside</a></div>
  <p class="muted small">No credit card. Not financial advice.</p></div>
  {mock}
</div></section>
<section class="lp-strip"><div class="lp-in lp-stats4">
  <div><b>5,900+</b><span>US stocks in the screener</span></div><div><b>10 years</b><span>of financial statements per company</span></div>
  <div><b>8,700+</b><span>Congress and presidential trades tracked</span></div><div><b>0</b><span>numbers made up by AI</span></div>
</div></section>
<section id="features" class="lp-sec"><div class="lp-in"><p class="lp-eyebrow">Features</p>
  <h2>Everything you check before you buy, on one screen.</h2>
  <div class="lp-feats">{feats}</div></div></section>
<section id="why" class="lp-sec alt"><div class="lp-in"><p class="lp-eyebrow">Why {BRAND}</p>
  <h2>What sets us apart</h2><div class="lp-diffs">{diff_html}</div>
  <div class="lp-cmpwrap"><table class="lp-cmp"><thead><tr><th></th><th>Typical free sites</th><th>Professional terminals</th><th class="us">{BRAND}</th></tr></thead>
  <tbody>{table}</tbody></table></div>
  <p class="muted small">Comparison is general and reflects typical offerings; individual products differ.</p></div></section>
<section id="pricing" class="lp-sec"><div class="lp-in"><p class="lp-eyebrow">Pricing</p>
  <h2>Free while we build. Paid plans are coming.</h2><div class="lp-tiers">{tier_html}</div></div></section>
<section class="lp-sec alt"><div class="lp-in lp-faqwrap"><h2>Questions</h2><div>{faq_html}</div></div></section>
<section class="lp-final"><div class="lp-in"><h2>Start with the stocks you care about.</h2>
  <p class="lp-lead">Pick your sectors and indices, and your watchlist builds itself.</p>
  <a class="btn primary" href="/signup">Create a free account</a></div></section>
</main>
<footer class="lp-foot"><div class="lp-in"><div>{_brand_link()}<p class="muted small">&copy; 2026 {html.escape(legal.operator())}. All rights reserved.</p></div>
  <div class="lp-flinks"><a href="/terms">Terms of Service</a><a href="/privacy">Privacy Policy</a><a href="/login">Sign in</a></div>
  <p class="muted small lp-disc">{BRAND} provides information for research and education only. It is not investment advice or a
  recommendation to buy or sell any security. Investing involves risk, including loss of principal. Data may be delayed or
  inaccurate. Past and simulated performance do not guarantee future results.</p></div></footer>"""
    return _shell(f"{BRAND}: stock research built on official filings", body, _LANDING_CSS)


_LANDING_CSS = """
.lp-in{max-width:1160px;margin:0 auto;padding:0 24px}
.lp-nav{display:block;margin:0;padding:0;position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--border)}
.lp-nav .lp-in{display:flex;align-items:center;gap:28px;height:68px}
.lp-nav nav{display:flex;gap:24px;flex:1} .lp-nav nav a{color:var(--muted);text-decoration:none;font-size:15px}
.lp-nav nav a:hover{color:var(--ink)}
.lp-auth{display:flex;align-items:center;gap:16px} .lp-signin{color:var(--ink);text-decoration:none;font-size:15px}
.lp-hero{padding:72px 0 56px}
.lp-hgrid{display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center}
.lp-eyebrow{font-size:13px;letter-spacing:1.6px;text-transform:uppercase;color:var(--accent);margin:0 0 14px}
.lp-hero h1{font-family:var(--font-display);font-weight:500;font-size:clamp(40px,5.4vw,64px);line-height:1.04;letter-spacing:-.02em;margin:0 0 20px}
.lp-lead{font-size:19px;line-height:1.6;color:var(--body,var(--ink));opacity:.88;margin:0 0 26px;max-width:620px}
.lp-cta{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.lp-mock{border:1px solid var(--border);border-radius:18px;background:var(--surface);padding:14px 16px 18px;
  box-shadow:0 24px 60px -24px rgba(20,20,19,.25)}
.lp-mh{display:flex;gap:6px;margin-bottom:10px} .lp-dot{width:9px;height:9px;border-radius:50%;background:var(--border-strong)}
.lp-mrow.top{margin-bottom:12px} .lp-tk{font-family:var(--font-display);font-size:22px}
.lp-card{background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:14px}
.lp-ch{display:flex;justify-content:space-between;align-items:center;font-size:15px}
.lp-badge{font-size:12px;padding:3px 9px;border-radius:12px;background:color-mix(in srgb,var(--up) 14%,transparent);color:var(--up)}
.lp-spark{width:100%;height:70px;margin:8px 0 6px;display:block}
.lp-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;font-size:13px}
.lp-stats small,.lp-mini small{display:block;color:var(--muted);font-size:11px;letter-spacing:.8px;text-transform:uppercase;margin-bottom:3px}
.lp-mini{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.lp-mini>div{background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:12px}
.lp-bars{display:flex;align-items:flex-end;gap:4px;height:54px} .lp-bars i{flex:1;background:var(--axis);border-radius:2px}
.lp-bars i:last-child{background:var(--accent)}
.lp-nodes{display:flex;flex-wrap:wrap;gap:6px} .lp-nodes span{font-size:12px;border:1px solid var(--border-strong);border-radius:14px;padding:3px 9px}
.lp-strip{border-top:1px solid var(--border);border-bottom:1px solid var(--border);background:var(--surface)}
.lp-stats4{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;padding-top:26px;padding-bottom:26px}
.lp-stats4 b{display:block;font-family:var(--font-display);font-weight:500;font-size:34px}
.lp-stats4 span{color:var(--muted);font-size:14px}
.lp-sec{padding:84px 0} .lp-sec.alt{background:var(--surface);border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
.lp-sec h2,.lp-final h2{font-family:var(--font-display);font-weight:500;font-size:clamp(30px,3.6vw,44px);letter-spacing:-.015em;margin:0 0 34px;max-width:760px;line-height:1.1}
.lp-feats{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.lp-feat{border:1px solid var(--border);border-radius:14px;background:var(--surface);padding:22px;transition:border-color .2s var(--ease-out),transform .2s var(--ease-out)}
.lp-feat:hover{border-color:var(--border-strong);transform:translateY(-2px)}
.lp-fi{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;background:color-mix(in srgb,var(--accent) 13%,transparent);color:var(--accent);margin-bottom:14px}
.lp-feat h3{font-size:17px;font-weight:500;margin:0 0 8px} .lp-feat p{margin:0;color:var(--muted);font-size:15px;line-height:1.55}
.lp-diffs{display:grid;grid-template-columns:1fr 1fr;gap:18px 40px;margin-bottom:40px}
.lp-diff{display:flex;gap:14px} .lp-dk{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:var(--accent);color:var(--accent-ink)}
.lp-diff h3{margin:2px 0 6px;font-size:18px;font-weight:500} .lp-diff p{margin:0;color:var(--muted);line-height:1.55;font-size:15px}
.lp-cmpwrap{overflow-x:auto;border:1px solid var(--border);border-radius:14px;background:var(--bg)}
.lp-cmp{width:100%;border-collapse:collapse;font-size:15px}
.lp-cmp th,.lp-cmp td{padding:13px 16px;border-top:1px solid var(--border);text-align:center}
.lp-cmp thead th{border-top:none;font-weight:500;color:var(--muted);font-size:13px}
.lp-cmp tbody th{text-align:left;font-weight:400}
.lp-cmp .us{color:var(--accent)} .lp-cmp td:last-child{background:color-mix(in srgb,var(--accent) 6%,transparent);font-weight:500}
.lp-cmp td.y{color:var(--up)} .lp-cmp td.n{color:var(--muted)}
.lp-tiers{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.lp-tier{border:1px solid var(--border);border-radius:16px;background:var(--surface);padding:26px;display:flex;flex-direction:column}
.lp-tier.live{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.lp-tier h3{margin:0 0 10px;font-size:18px;font-weight:500}
.lp-price{font-family:var(--font-display);font-size:40px;line-height:1.1}
.lp-pnote{color:var(--muted);font-size:14px;margin:4px 0 16px}
.lp-tier ul{list-style:none;padding:0;margin:0 0 22px;flex:1} .lp-tier li{display:flex;gap:10px;align-items:flex-start;margin:0 0 10px;font-size:15px}
.lp-tier li svg{flex:none;color:var(--accent);margin-top:3px}
.lp-faqwrap{display:grid;grid-template-columns:1fr 2fr;gap:40px}
.lp-q{border-bottom:1px solid var(--border);padding:16px 0} .lp-q summary{cursor:pointer;font-size:17px;list-style:none}
.lp-q summary::-webkit-details-marker{display:none} .lp-q summary:after{content:"+";float:right;color:var(--muted)}
.lp-q[open] summary:after{content:"–"} .lp-q p{color:var(--muted);line-height:1.6;margin:10px 0 0}
.lp-final{padding:90px 0;text-align:center} .lp-final h2{margin:0 auto 14px} .lp-final .lp-lead{margin:0 auto 24px}
.lp-foot{border-top:1px solid var(--border);padding:40px 0 60px}
.lp-foot .lp-in{display:grid;grid-template-columns:1fr auto;gap:18px}
.lp-flinks{display:flex;gap:22px;align-items:flex-start} .lp-flinks a{color:var(--muted);text-decoration:none;font-size:14px}
.lp-flinks a:hover{color:var(--ink)} .lp-disc{grid-column:1/-1;max-width:820px;line-height:1.55}
@media (max-width:900px){.lp-hgrid{grid-template-columns:1fr}.lp-nav nav{display:none}.lp-stats4{grid-template-columns:1fr 1fr}
  .lp-diffs,.lp-tiers,.lp-faqwrap{grid-template-columns:1fr}.lp-foot .lp-in{grid-template-columns:1fr}}
@media (max-width:520px){.lp-hero{padding:40px 0}.lp-sec{padding:56px 0}.lp-auth{gap:12px}.lp-nav .btn{height:38px;padding:0 14px;font-size:14px}.lp-nav .brand span{font-size:20px}.lp-stats{grid-template-columns:1fr 1fr}}
"""


# --- sign in / sign up ------------------------------------------------------------

def login_html(mode: str = "login", google_client_id: str | None = None, nxt: str = "") -> str:
    gsi = '<script src="https://accounts.google.com/gsi/client" async defer></script>' if google_client_id else ""
    body = f"""<div class="au-wrap"><div class="au-top">{_brand_link()}</div>
<div class="au-card">
  <div class="au-tabs" role="tablist"><button data-m="login">Sign in</button><button data-m="signup">Create account</button></div>
  <h1 id="au-h"></h1><p id="au-sub" class="muted"></p>
  <div id="g-btn" class="g-btn"></div>
  <button id="pk-btn" class="btn ghost block" type="button" hidden>{_ico('target', 18)}Sign in with a passkey</button>
  <div class="divider" id="au-or">or with email</div>
  <form id="au-form" novalidate>
    <div class="field"><label for="em">Email</label><input class="inp" id="em" type="email" autocomplete="username webauthn" required></div>
    <div class="field"><label for="pw">Password</label><input class="inp" id="pw" type="password" autocomplete="current-password" required>
      <span class="small muted" id="pw-hint" hidden>At least 10 characters.</span></div>
    <label class="au-accept" id="acc-wrap" hidden><input type="checkbox" id="acc"> <span>I am 18 or older and agree to the
      <a href="/terms" target="_blank">Terms of Service</a> (including binding arbitration and a class-action waiver) and the
      <a href="/privacy" target="_blank">Privacy Policy</a>.</span></label>
    <div class="err" id="au-err" role="alert"></div>
    <button class="btn primary block" id="au-go" type="submit"></button>
  </form>
  <p class="small muted au-switch" id="au-switch"></p>
</div>
<p class="small muted au-legal">Not financial advice. <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a></p></div>"""
    js = ("var MODE=" + json.dumps(mode if mode in ("login", "signup") else "login") + ", NEXT=" + json.dumps(nxt or "")
          + ", GID=" + json.dumps(google_client_id or "") + ";\n" + _LOGIN_JS)
    return _shell(("Sign in" if mode == "login" else "Create your account") + f" · {BRAND}", body, _AUTH_CSS, js, gsi)


_AUTH_CSS = """
.au-wrap{min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:28px 16px}
.au-top{width:100%;max-width:420px;margin-bottom:28px}
.au-card{width:100%;max-width:420px;box-sizing:border-box;background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:26px 26px 20px}
.au-tabs{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-bottom:22px}
.au-tabs button{height:38px;border:none;background:var(--bg);color:var(--muted);font:500 14px var(--font);cursor:pointer}
.au-tabs button.on{background:var(--surface-3);color:var(--ink)}
.au-card h1{font-family:var(--font-display);font-weight:500;font-size:30px;margin:0 0 6px}
.au-card>p{margin:0 0 18px;font-size:15px}
.g-btn{display:flex;justify-content:center;min-height:0;margin-bottom:10px} .g-btn:empty{display:none}
#pk-btn{margin-bottom:4px}
.au-switch{text-align:center;margin:14px 0 0} .au-switch a{cursor:pointer}
.au-legal{margin-top:18px}
"""

_LOGIN_JS = r"""
function setMode(m){ MODE=m;
  document.querySelectorAll('.au-tabs button').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-m')===m); });
  var su=m==='signup';
  document.getElementById('au-h').textContent=su?'Create your account':'Welcome back';
  document.getElementById('au-sub').textContent=su?'Free during the beta. Takes about a minute.':'Sign in to your watchlist and research.';
  document.getElementById('au-go').textContent=su?'Create account':'Sign in';
  document.getElementById('pw').setAttribute('autocomplete', su?'new-password':'current-password');
  document.getElementById('pw-hint').hidden=!su; document.getElementById('acc-wrap').hidden=!su;
  document.getElementById('pk-btn').hidden=su||!passkeySupported();
  document.getElementById('au-switch').innerHTML=su?'Already have an account? <a onclick="setMode(\'login\')">Sign in</a>':
    'New here? <a onclick="setMode(\'signup\')">Create an account</a>';
  document.getElementById('au-err').textContent='';
  try{ history.replaceState(null,'',su?'/signup':'/login'+(NEXT?'?next='+encodeURIComponent(NEXT):'')); }catch(_){}
  renderGoogle();
}
document.querySelectorAll('.au-tabs button').forEach(function(b){ b.addEventListener('click',function(){ setMode(b.getAttribute('data-m')); }); });
function done(d){ if(d.ok){ location.href=d.next||'/'; } else { document.getElementById('au-err').textContent=d.error||'Something went wrong.'; } }
document.getElementById('au-form').addEventListener('submit',function(e){ e.preventDefault();
  var btn=document.getElementById('au-go'); btn.disabled=true;
  var body={email:document.getElementById('em').value, password:document.getElementById('pw').value, next:NEXT};
  if(MODE==='signup') body.accept=document.getElementById('acc').checked;
  post(MODE==='signup'?'/auth/signup':'/auth/login', body).then(function(d){ btn.disabled=false; done(d); }); });
document.getElementById('pk-btn').addEventListener('click',function(){
  document.getElementById('au-err').textContent='';
  signInWithPasskey(NEXT).then(done).catch(function(e){ document.getElementById('au-err').textContent=pkError(e); }); });
function renderGoogle(){
  var el=document.getElementById('g-btn'); if(!GID){ el.innerHTML=''; document.getElementById('au-or').hidden=!passkeySupported()||MODE==='signup'; return; }
  if(!window.google||!google.accounts){ setTimeout(renderGoogle,200); return; }
  google.accounts.id.initialize({client_id:GID, callback:function(r){ post('/auth/google',{credential:r.credential,next:NEXT}).then(done); }});
  el.innerHTML=''; google.accounts.id.renderButton(el,{theme:'outline',size:'large',shape:'pill',width:320,
    text:MODE==='signup'?'signup_with':'signin_with'});
}
setMode(MODE);
"""


# --- onboarding -------------------------------------------------------------------

def welcome_html() -> str:
    body = f"""<div class="wz-wrap"><div class="wz-top">{_brand_link()}<a class="small muted" href="/logout">Sign out</a></div>
<div class="wz-prog" id="wz-prog"></div>
<div class="wz-card" id="wz"><p class="muted">Loading…</p></div></div>"""
    return _shell(f"Set up your account · {BRAND}", body, _WZ_CSS + _NF_CSS, _NF_JS + _WZ_JS)


_WZ_CSS = """
.wz-wrap{max-width:860px;margin:0 auto;padding:24px 16px 60px}
.wz-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:26px}
.wz-prog{display:flex;gap:8px;margin-bottom:18px} .wz-prog span{flex:1;height:4px;border-radius:2px;background:var(--border)}
.wz-prog span.on{background:var(--accent)}
.wz-card{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:28px}
.wz-card h1{font-family:var(--font-display);font-weight:500;font-size:34px;margin:0 0 8px;letter-spacing:-.01em}
.wz-card>p.lead{color:var(--muted);font-size:16px;margin:0 0 22px;line-height:1.55}
.wz-h{font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin:18px 0 10px}
.grp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.grp{position:relative;text-align:left;border:1px solid var(--border);border-radius:12px;background:var(--bg);padding:13px 14px 12px 44px;
  cursor:pointer;font:inherit;color:inherit;transition:border-color .15s var(--ease-out),background .15s var(--ease-out)}
.grp:hover{border-color:var(--border-strong)}
.grp b{display:block;font-weight:500;font-size:15px} .grp small{display:block;color:var(--muted);font-size:13px;line-height:1.4;margin-top:3px}
.grp .n{color:var(--muted);font-size:12px;margin-top:6px;display:block}
.grp:before{content:"";position:absolute;left:14px;top:15px;width:18px;height:18px;border-radius:5px;border:1.5px solid var(--border-strong);background:var(--bg)}
.grp.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 7%,var(--bg))}
.grp.on:before{background:var(--accent);border-color:var(--accent);
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12l5 5 9-10'/%3E%3C/svg%3E");background-size:14px;background-position:center;background-repeat:no-repeat}
.wz-foot{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:24px;flex-wrap:wrap}
.wz-count{color:var(--muted);font-size:14px}
.opt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px}
.opt{border:1px solid var(--border);border-radius:10px;background:var(--bg);padding:11px 14px;cursor:pointer;font:inherit;color:inherit;text-align:left;font-size:15px}
.opt:hover{border-color:var(--border-strong)} .opt.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 7%,var(--bg))}
.seg3{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.seg3 button{height:40px;padding:0 16px;border:none;background:var(--bg);color:var(--muted);font:500 14px var(--font);cursor:pointer}
.seg3 button.on{background:var(--surface-3);color:var(--ink)}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pk-hero{display:flex;gap:18px;align-items:flex-start}
.pk-ico{flex:none;width:56px;height:56px;border-radius:14px;display:grid;place-items:center;background:color-mix(in srgb,var(--accent) 13%,transparent);color:var(--accent)}
.terms-box{border:1px solid var(--border);border-radius:12px;background:var(--bg);padding:16px 18px;font-size:15px;line-height:1.6}
.terms-box ul{margin:8px 0 0;padding-left:20px}
@media (max-width:600px){.wz-card{padding:20px}.row2{grid-template-columns:1fr}.wz-card h1{font-size:28px}}
"""

_WZ_JS = r"""
var ME=null, GROUPS=[], STEPS=[], I=0, SEL={}, PROF={};
function prog(){ document.getElementById('wz-prog').innerHTML=STEPS.map(function(s,k){ return '<span'+(k<=I?' class="on"':'')+'></span>'; }).join(''); }
function show(){ prog(); window.scrollTo(0,0); ({terms:stTerms,sectors:stSectors,about:stAbout,notify:stNotify,passkey:stPasskey})[STEPS[I]](); }
var NOTE='';
function stNotify(){
  if(!NF){ nfInit(ME); if(!ME.user.notify.groups.length){ NF.groups={}; Object.keys(SEL).forEach(function(k){ if(SEL[k]) NF.groups[k]=true; }); } }
  el().innerHTML='<h1>Stay in the loop</h1><p class="lead">Pick a daily market summary, politicians to follow, and how you\'d like to '+
    'hear from us. You can change any of this later in account settings.</p>'+nfHTML(ME, GROUPS)+
    '<div class="err" id="err"></div><div class="wz-foot"><button class="btn ghost" id="back">Back</button><button class="btn primary" id="go">Continue</button></div>';
  nfBind(ME);
  document.getElementById('back').onclick=function(){ I--; show(); };
  document.getElementById('go').onclick=function(){ var go=this; go.disabled=true;
    nfSave().then(function(d){ NOTE=d.email_pending?(d.verification_sent?'We sent a link to '+ME.user.email+'. Click it to start getting emails.':
      'Email will start once your address is confirmed.'):''; next(); })
      .catch(function(e){ go.disabled=false; document.getElementById('err').textContent=(e&&e.message)||e; }); };
}
function next(){ I++; if(I>=STEPS.length) return finish(); show(); }
function el(){ return document.getElementById('wz'); }
function stTerms(){
  el().innerHTML='<h1>Before we start</h1><p class="lead">A quick, plain-English summary of how this works.</p>'+
   '<div class="terms-box"><b>Please confirm:</b><ul><li>This is research and education, not financial advice. We are not a registered '+
   'investment adviser, and nothing here tells you what to buy or sell.</li><li>Models and data can be wrong or delayed. You are responsible '+
   'for your own decisions.</li><li>Disputes are resolved by individual arbitration, not class actions or jury trials (you can opt out '+
   'within 30 days).</li><li>We use your information to run your account and never sell it.</li></ul></div>'+
   '<label class="au-accept" style="margin-top:16px;font-size:14px"><input type="checkbox" id="t-acc" style="accent-color:var(--accent)"> '+
   '<span>I am 18 or older and agree to the <a href="/terms" target="_blank">Terms of Service</a> and '+
   '<a href="/privacy" target="_blank">Privacy Policy</a>.</span></label><div class="err" id="err"></div>'+
   '<div class="wz-foot"><span></span><button class="btn primary" id="go">Continue</button></div>';
  document.getElementById('go').onclick=function(){ post('/api/me/terms',{accept:document.getElementById('t-acc').checked}).then(function(d){
    if(d.ok) next(); else document.getElementById('err').textContent=d.error; }); };
}
function count(){ var s={}; GROUPS.forEach(function(g){ if(SEL[g.key]) g.tickers.forEach(function(t){ s[t]=1; }); }); return Object.keys(s).length; }
function stSectors(){
  var kinds=[['index','Indices'],['funds','Funds'],['theme','Themes'],['sector','Sectors']];
  el().innerHTML='<h1>What do you want to follow?</h1><p class="lead">Pick the indices and sectors you care about. Your watchlist '+
   'starts with every company in them; you can add or remove stocks any time.</p>'+
   kinds.map(function(k){ var gs=GROUPS.filter(function(g){return g.kind===k[0];}); if(!gs.length) return '';
     return '<div class="wz-h">'+k[1]+'</div><div class="grp-grid">'+gs.map(function(g){
       return '<button type="button" class="grp'+(SEL[g.key]?' on':'')+'" data-k="'+g.key+'"><b>'+esc(g.label)+'</b><small>'+esc(g.blurb)+
         '</small><span class="n">'+g.count+' '+(g.count===1?'stock':'stocks')+'</span></button>'; }).join('')+'</div>'; }).join('')+
   '<div class="err" id="err"></div><div class="wz-foot"><span class="wz-count" id="cnt"></span><button class="btn primary" id="go">Continue</button></div>';
  function upd(){ var n=count(); document.getElementById('cnt').textContent=n?n+' stocks in your watchlist':'Choose at least one'; document.getElementById('go').disabled=!n; }
  el().querySelectorAll('.grp').forEach(function(b){ b.onclick=function(){ var k=b.getAttribute('data-k'); SEL[k]=!SEL[k]; b.classList.toggle('on',!!SEL[k]); upd(); }; });
  upd();
  document.getElementById('go').onclick=function(){ var keys=Object.keys(SEL).filter(function(k){return SEL[k];});
    post('/api/me/groups',{groups:keys}).then(function(d){ if(d.ok) next(); else document.getElementById('err').textContent=d.error; }); };
}
function opts(list, key, cls){ return list.map(function(p){ return '<button type="button" class="'+cls+(PROF[key]===p[0]?' on':'')+'" data-f="'+key+'" data-v="'+p[0]+'">'+esc(p[1])+'</button>'; }).join(''); }
function selOpts(list, key, ph){ return '<option value="">'+ph+'</option>'+list.map(function(p){ return '<option value="'+p[0]+'"'+(PROF[key]===p[0]?' selected':'')+'>'+esc(p[1])+'</option>'; }).join(''); }
function stAbout(){
  var o=ME.options, u=ME.user;
  ['first_name','last_name','dob','gender','investor_type','experience','referral'].forEach(function(k){ if(PROF[k]===undefined) PROF[k]=u[k]||''; });
  var max=new Date(); max.setFullYear(max.getFullYear()-18);
  el().innerHTML='<h1>Tell us about you</h1><p class="lead">This tailors explanations and defaults. It\'s never shared or sold.</p>'+
   '<div class="wz-h">What kind of investor are you?</div><div class="opt-grid">'+opts(o.investor_types,'investor_type','opt')+'</div>'+
   '<div class="wz-h">How much investing experience do you have?</div><div class="seg3">'+opts(o.experience,'experience','')+'</div>'+
   '<div class="wz-h">Your details</div><div class="row2">'+
   '<div class="field"><label for="fn">First name</label><input class="inp" id="fn" autocomplete="given-name" value="'+esc(PROF.first_name)+'"></div>'+
   '<div class="field"><label for="ln">Last name</label><input class="inp" id="ln" autocomplete="family-name" value="'+esc(PROF.last_name)+'"></div>'+
   '<div class="field"><label for="dob">Date of birth</label><input class="inp" id="dob" type="date" autocomplete="bday" max="'+max.toISOString().slice(0,10)+'" value="'+esc(PROF.dob)+'"></div>'+
   '<div class="field"><label for="gd">Gender (optional)</label><select class="inp" id="gd">'+selOpts(o.genders,'gender','Choose…')+'</select></div>'+
   '<div class="field"><label for="rf">How did you hear about us? (optional)</label><select class="inp" id="rf">'+selOpts(o.referrals,'referral','Choose…')+'</select></div></div>'+
   '<p class="small muted">We ask for your date of birth to confirm you are 18 or older.</p><div class="err" id="err"></div>'+
   '<div class="wz-foot"><button class="btn ghost" id="back">Back</button><button class="btn primary" id="go">Continue</button></div>';
  el().querySelectorAll('[data-f]').forEach(function(b){ b.onclick=function(){ var f=b.getAttribute('data-f');
    PROF[f]=b.getAttribute('data-v'); el().querySelectorAll('[data-f="'+f+'"]').forEach(function(x){ x.classList.toggle('on',x===b); }); }; });
  document.getElementById('back').onclick=function(){ I--; show(); };
  document.getElementById('go').onclick=function(){
    PROF.first_name=document.getElementById('fn').value; PROF.last_name=document.getElementById('ln').value;
    PROF.dob=document.getElementById('dob').value; PROF.gender=document.getElementById('gd').value||null; PROF.referral=document.getElementById('rf').value||null;
    post('/api/me/profile',PROF).then(function(d){ if(d.ok) next(); else document.getElementById('err').textContent=d.error; }); };
}
function stPasskey(){
  var ok=passkeySupported();
  el().innerHTML='<div class="pk-hero"><div class="pk-ico"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="9" r="4"/><path d="M11 12l9 0M17 12v3M20 12v2M2 20a6 6 0 0112 0"/></svg></div><div>'+
   '<h1>Sign in faster next time</h1><p class="lead">Create a passkey and sign in with Face ID, Touch ID, Windows Hello or your phone '+
   'instead of a password. Your fingerprint or face never leaves your device; we only store a public key.</p></div></div>'+
   (NOTE?'<p class="ok-msg" style="margin:0 0 10px">'+esc(NOTE)+'</p>':'')+
   (ok?'':'<p class="muted">This browser doesn\'t support passkeys. You can add one later from account settings on another device.</p>')+
   '<div class="err" id="err"></div><div class="wz-foot"><button class="btn ghost" id="skip">Skip for now</button>'+
   (ok?'<button class="btn primary" id="go">Create a passkey</button>':'<button class="btn primary" id="skip2">Finish</button>')+'</div>';
  document.getElementById('skip').onclick=finish; var s2=document.getElementById('skip2'); if(s2) s2.onclick=finish;
  var go=document.getElementById('go'); if(go) go.onclick=function(){ go.disabled=true; document.getElementById('err').textContent='';
    createPasskey().then(function(d){ if(d.ok) finish(); else { go.disabled=false; document.getElementById('err').textContent=d.error; } })
      .catch(function(e){ go.disabled=false; document.getElementById('err').textContent=pkError(e); }); };
}
function finish(){ post('/api/me/onboarded').then(function(d){ if(d.ok) location.href='/'; else { alert(d.error||'A step is missing.'); I=0; show(); } }); }
Promise.all([fetch('/api/me').then(function(r){return r.json();}), fetch('/api/groups').then(function(r){return r.json();})]).then(function(a){
  ME=a[0]; GROUPS=a[1].groups||[];
  (ME.user.groups||[]).forEach(function(k){ SEL[k]=true; }); if(!ME.user.groups.length) SEL.mag7=true;
  var only=new URLSearchParams(location.search).get('step');
  STEPS=[]; if(ME.user.needs_terms) STEPS.push('terms');
  if(ME.user.onboarded){                      // returning user: only what was asked for or is missing
    if(only==='sectors'||only==='notify') STEPS.push(only);
    if(!STEPS.length) STEPS.push('sectors');
  } else { STEPS.push('sectors','about','notify'); if(!ME.passkeys.length) STEPS.push('passkey'); }
  show();
});
"""


# --- account ------------------------------------------------------------------------

def account_html() -> str:
    body = f"""<div class="ac-wrap"><div class="wz-top">{_brand_link()}<span><a class="btn ghost" href="/">Back to the board</a></span></div>
<h1 class="ac-h">Account settings</h1><div id="ac" class="muted">Loading…</div></div>"""
    return _shell(f"Account · {BRAND}", body, _WZ_CSS + _AC_CSS + _NF_CSS, _NF_JS + _AC_JS)


_AC_CSS = """
.ac-wrap{max-width:860px;margin:0 auto;padding:24px 16px 60px}
.ac-h{font-family:var(--font-display);font-weight:500;font-size:36px;margin:0 0 18px}
.ac-sec{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:22px;margin-bottom:14px}
.ac-sec h2{font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);font-weight:500;margin:0 0 14px}
.tk-list{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.tk{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--border-strong);border-radius:14px;padding:3px 4px 3px 10px;font-size:13px;background:var(--bg)}
.tk button{border:none;background:none;color:var(--muted);cursor:pointer;font-size:16px;line-height:1;padding:0 4px}
.tk button:hover{color:var(--down)}
.ac-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;border-top:1px solid var(--border);font-size:15px}
.ac-row:first-of-type{border-top:none}
.ac-danger{border-color:color-mix(in srgb,var(--down) 40%,var(--border))}
.btn.danger{background:var(--down);color:#fff}
"""

_AC_JS = r"""
var ME=null;
function prof(){ var o=ME.options,u=ME.user;
  function sel(list,k,ph){ return '<option value="">'+ph+'</option>'+list.map(function(p){ return '<option value="'+p[0]+'"'+(u[k]===p[0]?' selected':'')+'>'+esc(p[1])+'</option>'; }).join(''); }
  return '<div class="ac-sec"><h2>Profile</h2><div class="row2">'+
   '<div class="field"><label>First name</label><input class="inp" id="fn" value="'+esc(u.first_name)+'"></div>'+
   '<div class="field"><label>Last name</label><input class="inp" id="ln" value="'+esc(u.last_name)+'"></div>'+
   '<div class="field"><label>Date of birth</label><input class="inp" id="dob" type="date" value="'+esc(u.dob)+'"></div>'+
   '<div class="field"><label>Gender (optional)</label><select class="inp" id="gd">'+sel(o.genders,'gender','Not specified')+'</select></div>'+
   '<div class="field"><label>Kind of investor</label><select class="inp" id="it">'+sel(o.investor_types,'investor_type','Choose…')+'</select></div>'+
   '<div class="field"><label>Experience</label><select class="inp" id="ex">'+sel(o.experience,'experience','Choose…')+'</select></div></div>'+
   '<div class="wz-foot" style="margin-top:4px"><span class="small" id="p-msg"></span><button class="btn primary" onclick="saveProf()">Save profile</button></div></div>';
}
function saveProf(){ var b={first_name:v('fn'),last_name:v('ln'),dob:v('dob'),gender:v('gd')||null,investor_type:v('it'),experience:v('ex'),referral:ME.user.referral};
  post('/api/me/profile',b).then(function(d){ var m=document.getElementById('p-msg'); m.className='small '+(d.ok?'ok-msg':'err'); m.textContent=d.ok?'Saved.':d.error; }); }
function v(id){ return document.getElementById(id).value; }
function wl(){ return '<div class="ac-sec"><h2>Your watchlist · '+ME.watchlist.length+' stocks</h2><div class="tk-list">'+
   ME.watchlist.map(function(t){ return '<span class="tk">'+esc(t)+'<button title="Remove '+esc(t)+'" onclick="rm(\''+esc(t)+'\')">&times;</button></span>'; }).join('')+
   '</div><div class="wz-foot" style="margin-top:0"><span style="display:flex;gap:8px;flex:1;min-width:240px"><input class="inp" id="addt" placeholder="Add tickers, e.g. NET, OKTA" style="max-width:320px">'+
   '<button class="btn ghost" onclick="addT()">Add</button></span><a class="btn ghost" href="/welcome?step=sectors">Choose sectors again</a></div></div>'; }
function rm(t){ post('/api/me/watchlist',{remove:[t]}).then(function(d){ if(d.ok){ ME.watchlist=d.watchlist; render(); } }); }
function addT(){ var t=v('addt'); if(!t.trim()) return; post('/api/me/watchlist',{add:t.split(/[\s,;]+/)}).then(function(d){ if(d.ok){ ME.watchlist=d.watchlist; render(); } }); }
function signin(){ var u=ME.user;
  return '<div class="ac-sec"><h2>Sign-in methods</h2>'+
   '<div class="ac-row"><span>Email<br><span class="small muted">'+esc(u.email)+'</span></span><span class="small muted">'+(u.has_password?'Password set':'No password')+'</span></div>'+
   '<div class="ac-row"><span>Google</span><span class="small muted">'+(u.google_linked?'Connected':'Not connected')+'</span></div>'+
   ME.passkeys.map(function(p){ return '<div class="ac-row"><span>Passkey: '+esc(p.name||'Passkey')+'<br><span class="small muted">Added '+new Date(p.created_at*1000).toLocaleDateString()+
     (p.last_used?' · last used '+new Date(p.last_used*1000).toLocaleDateString():'')+'</span></span><button class="btn ghost" onclick="rmPk(\''+esc(p.credential_id)+'\')">Remove</button></div>'; }).join('')+
   '<div class="wz-foot"><span class="small err" id="pk-err"></span>'+(passkeySupported()?'<button class="btn ghost" onclick="addPk()">Add a passkey</button>':'')+'</div>'+
   '<div class="wz-h">'+(u.has_password?'Change password':'Set a password')+'</div><div class="row2">'+
   (u.has_password?'<div class="field"><label>Current password</label><input class="inp" id="cur" type="password" autocomplete="current-password"></div>':'')+
   '<div class="field"><label>New password (10+ characters)</label><input class="inp" id="npw" type="password" autocomplete="new-password"></div></div>'+
   '<div class="wz-foot" style="margin-top:0"><span class="small" id="pw-msg"></span><button class="btn ghost" onclick="setPw()">Save password</button></div></div>'; }
function addPk(){ createPasskey().then(function(d){ if(d.ok) load(); else document.getElementById('pk-err').textContent=d.error; })
  .catch(function(e){ document.getElementById('pk-err').textContent=pkError(e); }); }
function rmPk(id){ if(!confirm('Remove this passkey?')) return; fetch('/api/me/passkeys/'+encodeURIComponent(id),{method:'DELETE'}).then(load); }
function setPw(){ var c=document.getElementById('cur'); post('/api/me/password',{current:c?c.value:'',password:v('npw')}).then(function(d){
  var m=document.getElementById('pw-msg'); m.className='small '+(d.ok?'ok-msg':'err'); m.textContent=d.ok?'Password saved.':d.error; if(d.ok) load(); }); }
function danger(){ return '<div class="ac-sec"><h2>Legal</h2><p class="small">You accepted the <a href="/terms">Terms of Service</a> and '+
   '<a href="/privacy">Privacy Policy</a> (version '+esc(ME.terms_version)+').</p></div>'+
   '<div class="ac-sec ac-danger"><h2>Delete account</h2><p class="small muted">Deletes your profile, watchlist and passkeys permanently. This can\'t be undone.</p>'+
   '<div class="wz-foot" style="margin-top:0"><span style="display:flex;gap:8px;flex:1"><input class="inp" id="del" placeholder="Type DELETE to confirm" style="max-width:260px"></span>'+
   '<button class="btn danger" onclick="delAcct()">Delete my account</button></div><div class="err" id="del-err"></div></div>'+
   '<p><a class="btn ghost" href="/logout">Sign out</a></p>'; }
function delAcct(){ post('/api/me/delete',{confirm:v('del')}).then(function(d){ if(d.ok) location.href='/'; else document.getElementById('del-err').textContent=d.error; }); }
var GROUPS=[];
function notif(){ return '<div class="ac-sec"><h2>Notifications</h2>'+nfHTML(ME, GROUPS)+
   '<div class="wz-foot"><span class="small" id="nf-msg"></span><span style="display:flex;gap:8px"><button class="btn ghost" onclick="testNf()">Send me a test</button>'+
   '<button class="btn primary" onclick="saveNf()">Save notifications</button></span></div></div>'; }
function saveNf(){ var m=document.getElementById('nf-msg'); nfSave().then(function(d){ m.className='small ok-msg';
    m.textContent=d.email_pending?(d.verification_sent?'Saved. Check your inbox to confirm your email.':'Saved. Email starts once your address is confirmed.'):'Saved.'; })
  .catch(function(e){ m.className='small err'; m.textContent=(e&&e.message)||e; }); }
function testNf(){ var m=document.getElementById('nf-msg'); post('/api/me/notify/test').then(function(d){
  m.className='small '+(d.ok?'ok-msg':'err');
  m.textContent=d.ok?('Sent'+(d.email?' by email':'')+(d.push?' to '+d.push+' browser'+(d.push>1?'s':''):'')+(d.inapp?' to your Today panel':'')+'.'):d.error; }); }
function render(){ var a=document.getElementById('ac'); a.className=''; if(!NF) nfInit(ME);
  a.innerHTML=prof()+wl()+notif()+signin()+danger(); nfBind(ME); }
function load(){ Promise.all([fetch('/api/me').then(function(r){return r.json();}), fetch('/api/groups').then(function(r){return r.json();})])
  .then(function(a){ ME=a[0]; GROUPS=a[1].groups||[]; render(); }); }
load();
"""


# --- legal ------------------------------------------------------------------------

def legal_html(kind: str) -> str:
    title = "Terms of Service" if kind == "terms" else "Privacy Policy"
    doc = legal.terms_body() if kind == "terms" else legal.privacy_body()
    body = f"""<div class="lg-wrap"><div class="wz-top">{_brand_link()}<a class="small" href="/">Home</a></div>
<article class="lg"><h1>{title}</h1>{doc}</article>
<p class="small muted"><a href="/terms">Terms of Service</a> · <a href="/privacy">Privacy Policy</a></p></div>"""
    return _shell(f"{title} · {BRAND}", body, _WZ_CSS + _LG_CSS)


_LG_CSS = """
.lg-wrap{max-width:780px;margin:0 auto;padding:24px 18px 60px}
.lg h1{font-family:var(--font-display);font-weight:500;font-size:42px;margin:0 0 6px}
.lg h2{font-size:19px;font-weight:500;margin:30px 0 8px}
.lg p,.lg li{font-size:16px;line-height:1.7}
.lg-eff{color:var(--muted);font-size:14px!important}
.lg-callout{border:1px solid var(--accent);background:color-mix(in srgb,var(--accent) 6%,var(--bg));border-radius:12px;padding:14px 16px;line-height:1.6;margin:16px 0 8px}
.lg-caps{font-size:14px!important;text-transform:uppercase;letter-spacing:.2px}
"""


# --- the board, personalised --------------------------------------------------------

def personalize_board(board_html: str, user: dict, tickers: list[str]) -> str:
    """Inject the user's watchlist filter, a My watchlist / All stocks switch
    and an account menu into the shared board."""
    first = (user.get("first_name") or user.get("email") or "?").strip()
    initials = "".join(p[0] for p in first.split()[:2]).upper() or "?"
    inject = ("<style>.me-seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}"
              ".me-seg button{height:34px;padding:0 12px;border:none;background:var(--surface);color:var(--muted);font:500 13px var(--font);cursor:pointer}"
              ".me-seg button.on{background:var(--surface-3);color:var(--ink)}"
              ".me-btn{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;"
              "background:var(--accent);color:var(--accent-ink);font:500 13px var(--font);text-decoration:none;margin-right:6px}"
              ".me-out{font-size:13px;color:var(--muted);margin-right:10px;text-decoration:none}.me-out:hover{color:var(--ink)}</style>"
              "<script>(function(){window.MYWL=new Set(" + json.dumps(tickers) + ");"
              "try{window.MYWL_ON=localStorage.getItem('wl_mine')!=='0';}catch(_){window.MYWL_ON=true;}"
              "var bar=document.querySelector('.bar');if(bar){var s=document.createElement('span');s.className='me-seg';"
              "s.innerHTML='<button data-m=\"1\">My watchlist</button><button data-m=\"0\">All stocks</button>';"
              "bar.insertBefore(s,bar.children[1]||null);"
              "function paint(){s.querySelectorAll('button').forEach(function(b){b.classList.toggle('on',(b.getAttribute('data-m')==='1')===window.MYWL_ON);});}"
              "s.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;window.MYWL_ON=b.getAttribute('data-m')==='1';"
              "try{localStorage.setItem('wl_mine',window.MYWL_ON?'1':'0');}catch(_){}paint();applyFilter();});paint();}"
              "var tr=document.querySelector('.top-r');if(tr){tr.insertAdjacentHTML('afterbegin','<a class=\"me-out\" href=\"/logout\">Sign out</a>"
              "<a class=\"me-btn\" href=\"/account\" title=\"Account settings\">" + html.escape(initials) + "</a>');}"
              "var h=document.querySelector('.top-l h1');if(h)h.textContent=" + json.dumps(f"{first.split()[0]}'s watchlist") + ";"
              "if(typeof applyFilter==='function')applyFilter();})();</script>")
    inject += _TODAY_INJECT
    h = board_html.find("</head>")
    if h >= 0:
        board_html = board_html[:h] + HEAD_PWA + board_html[h:]
    i = board_html.rfind("</body>")
    return board_html[:i] + inject + board_html[i:] if i >= 0 else board_html + inject


_TODAY_INJECT = r"""<style>
.me-today{position:relative;height:34px;padding:0 12px;border-radius:17px;border:1px solid var(--border-strong);background:var(--surface);
  color:var(--ink);font:500 13px var(--font);cursor:pointer;margin-right:10px}
.me-today .dot{position:absolute;top:-2px;right:-2px;width:9px;height:9px;border-radius:50%;background:var(--accent);display:none}
.me-today.unread .dot{display:block}
.td-drawer{position:fixed;top:0;right:0;bottom:0;width:min(420px,100vw);background:var(--bg);border-left:1px solid var(--border);
  box-shadow:-20px 0 50px -20px rgba(0,0,0,.25);z-index:60;transform:translateX(100%);transition:transform .25s var(--ease-out);
  display:flex;flex-direction:column}
.td-drawer.show{transform:none}
.td-head{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid var(--border)}
.td-head h3{font-family:var(--font-display);font-weight:500;font-size:24px;margin:0}
.td-head button{border:none;background:none;font-size:22px;color:var(--muted);cursor:pointer}
.td-list{overflow-y:auto;padding:8px 18px 24px;flex:1}
.td-item{border-bottom:1px solid var(--border);padding:12px 0}
.td-item b{font-weight:500;font-size:15px} .td-item time{display:block;color:var(--muted);font-size:12px;margin:2px 0 6px}
.td-item p{margin:0 0 6px;font-size:14px;line-height:1.5}
.td-item.new b:after{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);margin-left:6px;vertical-align:2px}
.td-card{border:1px solid var(--accent);background:color-mix(in srgb,var(--accent) 6%,var(--surface));border-radius:var(--r-lg,14px);
  padding:14px 18px;margin:0 0 14px}
.td-card h4{margin:0 0 6px;font-family:var(--font-display);font-weight:500;font-size:22px}
.td-card p{margin:0 0 5px;font-size:14px;line-height:1.5}
.td-card .td-act{display:flex;gap:14px;margin-top:8px;font-size:13px} .td-card .td-act a{cursor:pointer;color:var(--link)}
.td-empty{color:var(--muted);font-size:14px;padding:20px 0}
</style>
<div class="td-drawer" id="td-drawer" aria-hidden="true"><div class="td-head"><h3>Today</h3><button onclick="tdClose()" aria-label="Close">&times;</button></div>
<div class="td-list" id="td-list"></div></div>
<script>(function(){
var ITEMS=[];
function e(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function when(t){ var d=new Date(t*1000); return d.toLocaleString('en-US',{weekday:'short',hour:'numeric',minute:'2-digit'}); }
function lines(b){ return (b||'').split('\n').filter(Boolean).map(function(l){ return '<p>'+e(l)+'</p>'; }).join(''); }
var tr=document.querySelector('.top-r');
if(tr) tr.insertAdjacentHTML('afterbegin','<button class="me-today" id="me-today" onclick="tdOpen()">Today<span class="dot"></span></button>');
window.tdOpen=function(){ var l=document.getElementById('td-list');
  l.innerHTML=ITEMS.length?ITEMS.map(function(i){ return '<div class="td-item'+(i.read_at?'':' new')+'"><b>'+e(i.title)+'</b><time>'+when(i.created_at)+'</time>'+lines(i.body)+
    (i.url&&i.url!=='/'?'<a href="'+e(i.url)+'">Open</a>':'')+'</div>'; }).join(''):
    '<div class="td-empty">Nothing yet. Your daily summaries and politician alerts will appear here. Set them up in <a href="/account">account settings</a>.</div>';
  document.getElementById('td-drawer').classList.add('show');
  if(ITEMS.some(function(i){return !i.read_at;})) fetch('/api/me/notifications/read',{method:'POST'}).then(function(){
    ITEMS.forEach(function(i){ i.read_at=i.read_at||1; }); document.getElementById('me-today').classList.remove('unread'); }); };
window.tdClose=function(){ document.getElementById('td-drawer').classList.remove('show'); };
document.addEventListener('keydown',function(ev){ if(ev.key==='Escape') tdClose(); });
fetch('/api/me/notifications').then(function(r){return r.json();}).then(function(d){
  ITEMS=d.items||[]; if(d.unread) document.getElementById('me-today').classList.add('unread');
  var s=ITEMS.find(function(i){ return i.kind==='summary' && !i.read_at && (Date.now()/1000-i.created_at)<18*3600; });
  var host=document.querySelector('.panels');
  if(s && host){ host.insertAdjacentHTML('beforebegin','<div class="td-card" id="td-card"><h4>'+e(s.title)+'</h4>'+lines(s.body)+
    '<div class="td-act"><a onclick="tdOpen()">See all notifications</a><a onclick="document.getElementById(\'td-card\').remove();fetch(\'/api/me/notifications/read\',{method:\'POST\'})">Dismiss</a></div></div>'); }
}).catch(function(){});
})();</script>"""


# --- simple message page, service worker, manifest, icons ---------------------------

def message_html(title: str, text: str) -> str:
    body = (f'<div class="lg-wrap"><div class="wz-top">{_brand_link()}<a class="small" href="/">Home</a></div>'
            f'<div class="wz-card"><h1>{html.escape(title)}</h1><p class="lead" style="color:var(--muted)">{html.escape(text)}</p>'
            f'<a class="btn primary" href="/">Go to your watchlist</a></div></div>')
    return _shell(f"{title} · {BRAND}", body, _WZ_CSS + _LG_CSS)


SERVICE_WORKER = r"""
self.addEventListener('push', function(e){
  var d={}; try{ d=e.data.json(); }catch(_){ d={title:'SMI Research', body:e.data?e.data.text():''}; }
  e.waitUntil(self.registration.showNotification(d.title||'SMI Research',
    {body:d.body||'', icon:'/icon-192.png', badge:'/icon-192.png', data:{url:d.url||'/'}}));
});
self.addEventListener('notificationclick', function(e){
  e.notification.close();
  var url=(e.notification.data||{}).url||'/';
  e.waitUntil(clients.matchAll({type:'window', includeUncontrolled:true}).then(function(ws){
    for(var i=0;i<ws.length;i++){ if('focus' in ws[i]){ ws[i].navigate(url); return ws[i].focus(); } }
    return clients.openWindow(url);
  }));
});
"""

MANIFEST = {"name": BRAND, "short_name": "SMI", "start_url": "/", "display": "standalone",
            "background_color": "#faf9f5", "theme_color": "#cc785c",
            "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                      {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}

HEAD_PWA = ('<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/apple-touch-icon.png">'
            '<meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#cc785c">')

_ICON_CACHE: dict = {}


def icon_png(size: int) -> bytes:
    """The app icon (coral tile with a rising line) as a PNG, drawn in code."""
    if size in _ICON_CACHE:
        return _ICON_CACHE[size]
    import struct
    import zlib
    bg, fg = (0xCC, 0x78, 0x5C), (0xFF, 0xFF, 0xFF)
    pts = [(6, 17), (10.5, 12), (14, 15), (20, 8)]              # the logo path on a 26-unit grid
    pts = [((x - 1) / 24 * size, (y - 1) / 24 * size) for x, y in pts]
    half = size * 0.045

    def near(px, py):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            dx, dy = x2 - x1, y2 - y1
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
            if (px - x1 - t * dx) ** 2 + (py - y1 - t * dy) ** 2 <= half * half:
                return True
        return False
    rows = []
    for y in range(size):
        row = bytearray(b"\x00")
        for x in range(size):
            row += bytes(fg if near(x + 0.5, y + 0.5) else bg)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    _ICON_CACHE[size] = png
    return png


# --- notification settings form (sign-up step + account page) ------------------------

_NF_CSS = """
.nf-seg{display:flex;flex-wrap:wrap;gap:8px}
.nf-chipset{display:flex;flex-wrap:wrap;gap:6px}
.nf-chip{height:32px;padding:0 12px;border-radius:16px;border:1px solid var(--border-strong);background:var(--bg);color:var(--ink);font:13px var(--font);cursor:pointer}
.nf-chip.on{background:color-mix(in srgb,var(--accent) 12%,var(--bg));border-color:var(--accent)}
.nf-people{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px;margin-top:10px}
.nf-p{display:flex;align-items:center;gap:10px;border:1px solid var(--border);border-radius:12px;background:var(--bg);padding:8px 10px}
.nf-p img,.nf-p .ph{width:38px;height:38px;border-radius:50%;object-fit:cover;flex:none;background:var(--surface-2);display:grid;place-items:center;font-size:13px}
.nf-p .who{flex:1;min-width:0;font-size:14px;line-height:1.3} .nf-p .who small{display:block;color:var(--muted);font-size:12px}
.nf-p button{height:30px;padding:0 10px;border-radius:15px;border:1px solid var(--border-strong);background:var(--bg);color:var(--ink);font:12px var(--font);cursor:pointer;flex:none}
.nf-p button.on{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.nf-ch{display:flex;gap:12px;align-items:flex-start;border:1px solid var(--border);border-radius:12px;background:var(--bg);padding:12px 14px;margin-bottom:8px;cursor:pointer}
.nf-ch input{margin-top:3px;width:17px;height:17px;accent-color:var(--accent);flex:none}
.nf-ch b{font-weight:500} .nf-ch small{display:block;color:var(--muted);font-size:13px;line-height:1.45;margin-top:2px}
.nf-ch.off{opacity:.55;cursor:not-allowed}
"""

_NF_JS = r"""
var NF=null, NF0={}, PEOPLE=[];
var TIMES=[['pre','Before the open','8:30am ET'],['post','After the close','4:30pm ET'],['both','Both',''],['none','No daily summary','']];
function nfInit(me){ var n=me.user.notify;
  NF={times:n.set?n.times:'pre', groups:{}, email:n.set?n.email:false, push:n.set?n.push:false, inapp:n.set?n.inapp:true, follows:{}};
  (n.groups.length?n.groups:me.user.groups).forEach(function(k){ NF.groups[k]=true; });
  (me.follows||[]).forEach(function(f){ NF.follows[f.pid]=f.name||f.pid; }); NF0=Object.assign({},NF.follows); }
function nfHTML(me, groups){
  var n=me.user.notify, isIOS=/iPhone|iPad/.test(navigator.userAgent), standalone=window.navigator.standalone===true;
  var pushOk=('serviceWorker' in navigator)&&('PushManager' in window)&&!!me.push_key;
  var emailNote=!me.email_ready?'Email isn\'t set up on this server yet.':
    (n.email_verified?'To '+esc(me.user.email):'To '+esc(me.user.email)+'. We\'ll send a link to confirm the address first.');
  var pushNote=pushOk?'Pop-up notifications from this browser, even when the site is closed.'+(me.push_count?' On for '+me.push_count+' browser'+(me.push_count>1?'s':'')+'.':''):
    (isIOS&&!standalone?'On iPhone and iPad: tap Share, then "Add to Home Screen", and open the site from there to turn this on.':'This browser can\'t show notifications.');
  return '<div class="wz-h">Daily market summary</div><div class="nf-seg" id="nf-times">'+TIMES.map(function(t){
      return '<button type="button" class="opt'+(NF.times===t[0]?' on':'')+'" data-t="'+t[0]+'"><b style="font-weight:500">'+t[1]+'</b>'+(t[2]?'<br><span class="small muted">'+t[2]+'</span>':'')+'</button>'; }).join('')+'</div>'+
   '<div id="nf-gwrap"><div class="wz-h">Sectors to cover</div><div class="nf-chipset" id="nf-groups">'+groups.map(function(g){
      return '<button type="button" class="nf-chip'+(NF.groups[g.key]?' on':'')+'" data-g="'+g.key+'">'+esc(g.label)+'</button>'; }).join('')+'</div>'+
   '<p class="small muted" style="margin:8px 0 0">Plus your watchlist\'s biggest movers, their earnings dates and the day\'s economic releases.</p></div>'+
   '<div class="wz-h">Follow politicians <span style="text-transform:none;letter-spacing:0">(optional)</span></div>'+
   '<p class="small muted" style="margin:0 0 8px">Get notified when their stock trades are disclosed. Members of Congress report up to 45 days after trading.</p>'+
   '<input class="inp" id="nf-q" placeholder="Search by name, state or party" autocomplete="off" style="max-width:360px">'+
   '<div class="nf-people" id="nf-people"><p class="small muted">Loading…</p></div>'+
   '<div class="wz-h">How should we reach you?</div>'+
   '<label class="nf-ch'+(me.email_ready?'':' off')+'"><input type="checkbox" id="nf-email"'+(NF.email&&me.email_ready?' checked':'')+(me.email_ready?'':' disabled')+'><span><b>Email</b><small>'+emailNote+'</small></span></label>'+
   '<label class="nf-ch'+(pushOk?'':' off')+'"><input type="checkbox" id="nf-push"'+(NF.push&&pushOk?' checked':'')+(pushOk?'':' disabled')+'><span><b>Browser notifications</b><small id="nf-push-note">'+pushNote+'</small></span></label>'+
   '<label class="nf-ch"><input type="checkbox" id="nf-inapp"'+(NF.inapp?' checked':'')+'><span><b>Today panel in the app</b><small>Your summary and alerts waiting on your watchlist when you sign in.</small></span></label>';
}
function nfPeople(){ var q=(document.getElementById('nf-q').value||'').trim().toLowerCase(), el=document.getElementById('nf-people');
  var list=PEOPLE.filter(function(p){ return !q || (p.name+' '+(p.state||'')+' '+(p.party||'')+' '+(p.chamber||'')).toLowerCase().indexOf(q)>=0; });
  var followed=PEOPLE.filter(function(p){ return NF.follows[p.id]; });
  if(!q){ list=followed.concat(list.filter(function(p){ return !NF.follows[p.id]; })).slice(0, Math.max(12, followed.length)); } else list=list.slice(0,24);
  if(!list.length){ el.innerHTML='<p class="small muted">'+(PEOPLE.length?'No one matches.':'Trade data is still loading. You can follow people later from the Trades page or your account.')+'</p>'; return; }
  el.innerHTML=list.map(function(p){ var on=!!NF.follows[p.id];
    var ini=(p.name||'?').split(' ').map(function(w){return w[0];}).slice(0,2).join('');
    return '<div class="nf-p">'+(p.photo?'<img src="'+esc(p.photo)+'" alt="" loading="lazy" onerror="this.outerHTML=\'<span class=&quot;ph&quot;>'+esc(ini)+'</span>\'">':'<span class="ph">'+esc(ini)+'</span>')+
      '<span class="who">'+esc(p.name)+'<small>'+esc([p.party?p.party[0]:'',p.chamber==='President'?'President':(p.chamber||''),p.state||''].filter(Boolean).join(' · '))+' · '+p.trades+' trades</small></span>'+
      '<button type="button" class="'+(on?'on':'')+'" data-pid="'+esc(p.id)+'" data-name="'+esc(p.name)+'">'+(on?'Following':'Follow')+'</button></div>'; }).join('');
}
function enablePush(key){
  return Notification.requestPermission().then(function(perm){
    if(perm!=='granted') throw new Error('Notifications are blocked in this browser\'s settings.');
    return navigator.serviceWorker.register('/sw.js');
  }).then(function(reg){ return navigator.serviceWorker.ready.then(function(){ return reg; }); })
  .then(function(reg){ return reg.pushManager.getSubscription().then(function(s){
    return s||reg.pushManager.subscribe({userVisibleOnly:true, applicationServerKey:unb64u(key)}); }); })
  .then(function(sub){ return post('/api/me/push',{subscription:sub.toJSON()}); })
  .then(function(d){ if(!d.ok) throw new Error(d.error); return d; });
}
function nfBind(me){
  function gw(){ document.getElementById('nf-gwrap').style.display=NF.times==='none'?'none':''; }
  document.querySelectorAll('#nf-times [data-t]').forEach(function(b){ b.onclick=function(){ NF.times=b.getAttribute('data-t');
    document.querySelectorAll('#nf-times [data-t]').forEach(function(x){ x.classList.toggle('on',x===b); }); gw(); }; }); gw();
  document.querySelectorAll('#nf-groups [data-g]').forEach(function(b){ b.onclick=function(){ var k=b.getAttribute('data-g'); NF.groups[k]=!NF.groups[k]; b.classList.toggle('on',!!NF.groups[k]); }; });
  document.getElementById('nf-q').oninput=nfPeople;
  document.getElementById('nf-people').onclick=function(e){ var b=e.target.closest('button[data-pid]'); if(!b) return;
    var id=b.getAttribute('data-pid'); if(NF.follows[id]) delete NF.follows[id]; else NF.follows[id]=b.getAttribute('data-name'); nfPeople(); };
  var pc=document.getElementById('nf-push');
  pc.onchange=function(){ if(!pc.checked) return; var note=document.getElementById('nf-push-note'); note.textContent='Asking your browser…';
    enablePush(me.push_key).then(function(){ note.textContent='On in this browser.'; })
      .catch(function(err){ pc.checked=false; note.textContent=(err&&err.message)||'Couldn\'t turn on notifications.'; }); };
  fetch('/api/politicians').then(function(r){return r.json();}).then(function(d){ PEOPLE=d.people||[]; nfPeople(); })
    .catch(function(){ PEOPLE=[]; nfPeople(); });
}
function nfSave(){
  NF.email=document.getElementById('nf-email').checked; NF.push=document.getElementById('nf-push').checked; NF.inapp=document.getElementById('nf-inapp').checked;
  var add=Object.keys(NF.follows).filter(function(k){ return !NF0[k]; }).map(function(k){ return {pid:k,name:NF.follows[k]}; });
  var rem=Object.keys(NF0).filter(function(k){ return !NF.follows[k]; });
  return post('/api/me/notify',{times:NF.times, groups:Object.keys(NF.groups).filter(function(k){return NF.groups[k];}),
    email:NF.email, push:NF.push, inapp:NF.inapp}).then(function(d){
      if(!d.ok) throw new Error(d.error);
      return post('/api/me/follows',{add:add, remove:rem}).then(function(){ NF0=Object.assign({},NF.follows); return d; }); });
}
"""
