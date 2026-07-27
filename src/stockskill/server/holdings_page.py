"""Render the holdings dashboard (served locally only — never published).

Shows positions split by account (brokerage / Roth IRA / 401k) with per-account
and grand totals, plus forms to record trades (bookkeeping) and deposit/withdraw
cash. All numbers come from holdings.csv; this only lays them out.
"""

from __future__ import annotations

import html

from ..dashboard.render import _CSS

_ACCOUNTS = [("brokerage", "Brokerage"), ("roth", "Roth IRA"), ("401k", "401(k)")]


def _usd(x: float | None) -> str:
    if x is None:
        return "—"
    return "${:,.0f}".format(x)


def _account_options(selected: str = "") -> str:
    return "".join(
        f'<option value="{k}"{" selected" if k == selected else ""}>{html.escape(v)}</option>'
        for k, v in _ACCOUNTS)


def _positions_table(acct: dict) -> str:
    total = acct["total"] or 1.0
    rows = []
    for p in acct["positions"]:
        share = p["market_value"] / total if total else 0.0
        rows.append(
            f'<tr><td class="h-tk">{html.escape(p["ticker"])}</td>'
            f'<td class="h-mv">{_usd(p["market_value"])}</td>'
            f'<td class="h-pct">{share*100:.1f}%</td></tr>')
    cash_share = acct["cash"] / total if total else 0.0
    rows.append(
        f'<tr class="h-cash"><td class="h-tk">Cash</td>'
        f'<td class="h-mv">{_usd(acct["cash"])}</td>'
        f'<td class="h-pct">{cash_share*100:.1f}%</td></tr>')
    return ('<table class="htable"><thead><tr><th>Position</th><th>Value</th>'
            '<th>% acct</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>')


def _account_card(acct: dict) -> str:
    return (
        f'<section class="h-acct"><div class="h-acct-h">'
        f'<span class="h-acct-name">{html.escape(acct["label"])}</span>'
        f'<span class="h-acct-total">{_usd(acct["total"])}</span></div>'
        f'{_positions_table(acct)}</section>')


def holdings_html(snap: dict, updated: str = "") -> str:
    accounts = snap.get("accounts", [])
    cards = "".join(_account_card(a) for a in accounts) or \
        '<p class="muted">No holdings found. Add a trade below to start.</p>'
    grand = _usd(snap.get("grand_total"))
    gpos = _usd(snap.get("grand_positions"))
    gcash = _usd(snap.get("grand_cash"))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Holdings</title><style>{_CSS}{_EXTRA_CSS}</style></head>
<body><div class="wrap">
<header><h1>Holdings</h1>
  <span class="status closed">LOCAL ONLY</span>
  <span class="sub" style="margin:0">Updated {html.escape(updated)}</span></header>
<p class="muted" style="font-size:12px;margin:-6px 0 14px">
  <a href="/">← back to watchlist</a> &nbsp;·&nbsp; Private &amp; local — never published.
  Trades here are bookkeeping to mirror your brokerage; nothing is sent to a broker.</p>

<div class="h-tiles">
  <div class="h-tile"><span>Total</span><b>{grand}</b></div>
  <div class="h-tile"><span>Invested</span><b>{gpos}</b></div>
  <div class="h-tile"><span>Cash</span><b>{gcash}</b></div>
</div>

<div class="h-accounts">{cards}</div>

<div class="h-forms">
  <section class="h-form">
    <div class="h-form-h">Record a trade</div>
    <div class="t-row">
      <input id="tk" placeholder="Ticker e.g. FNGU" autocomplete="off">
      <select id="acct">{_account_options("brokerage")}</select>
      <select id="side"><option value="buy">Buy</option><option value="sell">Sell</option></select>
    </div>
    <div class="t-row">
      <input id="amt" placeholder="Amount $" inputmode="decimal">
      <label class="h-chk"><input type="checkbox" id="settle" checked> settle with cash</label>
      <button class="tbtn add" onclick="doTrade()">Record</button>
    </div>
    <div id="tmsg" class="h-msg"></div>
  </section>
  <section class="h-form">
    <div class="h-form-h">Deposit / withdraw cash</div>
    <div class="t-row">
      <select id="cacct">{_account_options("brokerage")}</select>
      <select id="cdir"><option value="deposit">Deposit</option><option value="withdraw">Withdraw</option></select>
      <input id="camt" placeholder="Amount $" inputmode="decimal">
      <button class="tbtn add" onclick="doCash()">Apply</button>
    </div>
    <div id="cmsg" class="h-msg"></div>
  </section>
</div>

<p class="muted" style="font-size:11.5px;margin-top:14px">
Bookkeeping only — records what you did elsewhere; it does not place orders.
Values are what you enter; positions are not repriced automatically.</p>
</div>
<script>
function _v(id){{ return (document.getElementById(id).value||'').trim(); }}
function _msg(id,t,ok){{ const m=document.getElementById(id); m.textContent=t; m.className='h-msg '+(ok?'ok':'bad'); }}
function doTrade(){{
  const tk=_v('tk').toUpperCase(), acct=_v('acct'), side=_v('side'), amt=_v('amt');
  const settle=document.getElementById('settle').checked;
  if(!tk||!amt){{ _msg('tmsg','enter a ticker and amount',false); return; }}
  const q='?ticker='+encodeURIComponent(tk)+'&account='+encodeURIComponent(acct)
    +'&side='+side+'&amount='+encodeURIComponent(amt)+'&settle='+(settle?'1':'0');
  fetch('/api/holdings/trade'+q,{{method:'POST'}}).then(r=>r.json()).then(d=>{{
    if(d.ok){{ _msg('tmsg',(side==='buy'?'Bought ':'Sold ')+'$'+amt+' '+tk+(d.note?' — '+d.note:''),true);
      setTimeout(()=>location.reload(),650); }}
    else _msg('tmsg',d.error||'failed',false);
  }}).catch(()=>_msg('tmsg','network error',false));
}}
function doCash(){{
  const acct=_v('cacct'), dir=_v('cdir'), amt=_v('camt');
  if(!amt){{ _msg('cmsg','enter an amount',false); return; }}
  const q='?account='+encodeURIComponent(acct)+'&direction='+dir+'&amount='+encodeURIComponent(amt);
  fetch('/api/holdings/cash'+q,{{method:'POST'}}).then(r=>r.json()).then(d=>{{
    if(d.ok){{ _msg('cmsg',(dir==='deposit'?'Deposited ':'Withdrew ')+'$'+amt+' → balance '+
      (d.balance!=null?('$'+Math.round(d.balance).toLocaleString()):'')+(d.note?' ('+d.note+')':''),true);
      setTimeout(()=>location.reload(),650); }}
    else _msg('cmsg',d.error||'failed',false);
  }}).catch(()=>_msg('cmsg','network error',false));
}}
</script>
</body></html>"""


_EXTRA_CSS = """
.h-tiles{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.h-tile{flex:1 1 140px;background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:12px 16px}
.h-tile span{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.h-tile b{font-size:24px;font-variant-numeric:tabular-nums}
.h-accounts{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-bottom:18px}
.h-acct{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 16px}
.h-acct-h{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.h-acct-name{font-weight:650;font-size:15px}
.h-acct-total{font-variant-numeric:tabular-nums;font-weight:700;color:var(--accent)}
.htable{width:100%;border-collapse:collapse;font-size:13px}
.htable th{text-align:left;color:var(--muted);font-size:10px;text-transform:uppercase;
  letter-spacing:.04em;padding:2px 0;border-bottom:1px solid var(--border)}
.htable td{padding:4px 0;font-variant-numeric:tabular-nums;border-bottom:1px dashed var(--border)}
.htable td.h-tk{font-weight:600} .htable td.h-mv{text-align:right} .htable td.h-pct{text-align:right;color:var(--muted);width:56px}
.htable tr.h-cash td{color:var(--muted)}
.h-forms{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:640px){.h-forms{grid-template-columns:1fr}}
.h-form{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 16px}
.h-form-h{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}
.t-row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px;align-items:center}
.t-row input,.t-row select{padding:8px 10px;border-radius:8px;border:1px solid var(--border);
  background:var(--bg);color:var(--ink);font-size:13px}
.t-row input{flex:1 1 110px;min-width:80px}
.t-row input:focus,.t-row select:focus{outline:none;border-color:var(--accent)}
.h-chk{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:4px}
.tbtn.add{background:var(--accent);color:#fff;border:none;font-weight:650;padding:8px 14px;border-radius:8px;cursor:pointer}
.h-msg{font-size:12px;min-height:16px;margin-top:2px}
.h-msg.ok{color:var(--up)} .h-msg.bad{color:var(--down)}
"""
