"""Render the holdings dashboard (served locally only — never published).

Accounts are stacked vertically; each position shows shares, live price, today's
gain, net gain, cost basis, value and % of account. Cash is shown as Fidelity
SPAXX. Forms record trades (bookkeeping) and deposit/withdraw cash. All numbers
come from holdings.csv enriched with live prices; this only lays them out.
"""

from __future__ import annotations

import html

from ..dashboard.render import _CSS

_ACCOUNTS = [("brokerage", "Brokerage"), ("roth", "Roth IRA"), ("401k", "401(k)")]


def _money(x):
    return "—" if x is None else "${:,.0f}".format(x)


def _price(x):
    return "—" if x is None else "${:,.2f}".format(x)


def _shares(x):
    if x is None:
        return "—"
    return f"{x:,.2f}" if x < 1000 else f"{x:,.0f}"


def _pct(x):
    if x is None:
        return '<span class="muted">—</span>'
    cls = "up" if x >= 0 else "down"
    return f'<span class="{cls}">{x*100:+.2f}%</span>'


def _sign_money(x):
    if x is None:
        return '<span class="muted">—</span>'
    cls = "up" if x >= 0 else "down"
    return f'<span class="{cls}">{"+" if x >= 0 else "-"}${abs(x):,.0f}</span>'


def _yld(x):
    if not x:
        return '<span class="muted">—</span>'
    return f"{x*100:.2f}%"


def _account_options(selected: str = "") -> str:
    return "".join(
        f'<option value="{k}"{" selected" if k == selected else ""}>{html.escape(v)}</option>'
        for k, v in _ACCOUNTS)


def _positions_table(acct: dict, cash_symbol: str) -> str:
    rows = []
    for p in acct["positions"]:
        rows.append(
            "<tr>"
            f'<td class="h-tk">{html.escape(p["ticker"])}</td>'
            f'<td>{_shares(p["shares"])}</td>'
            f'<td>{_price(p["price"])}</td>'
            f'<td>{_pct(p["today_pct"])}</td>'
            f'<td>{_sign_money(p["today_dollar"])}</td>'
            f'<td>{_price(p["cost_basis"])}</td>'
            f'<td>{_money(p["cost_total"])}</td>'
            f'<td>{_pct(p["net_pct"])}</td>'
            f'<td>{_yld(p["div_yield"])}</td>'
            f'<td class="h-mv">{_money(p["market_value"])}</td>'
            f'<td class="h-pct">{p["pct_of_account"]*100:.1f}%</td>'
            "</tr>")
    cash_pct = (acct["cash"] / acct["total"]) if acct["total"] else 0.0
    rows.append(
        '<tr class="h-cash">'
        f'<td class="h-tk">{html.escape(cash_symbol)} <span class="muted">cash</span></td>'
        '<td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>'
        f'<td class="h-mv">{_money(acct["cash"])}</td>'
        f'<td class="h-pct">{cash_pct*100:.1f}%</td></tr>')
    return ('<table class="htable"><thead><tr>'
            '<th>Position</th><th>Shares</th><th>Price</th><th>Today</th>'
            '<th>Day $</th><th>Cost</th><th>Cost tot</th><th>Net</th><th>Yield</th>'
            '<th>Value</th><th>% acct</th>'
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>')


def _account_card(acct: dict, cash_symbol: str) -> str:
    return (
        f'<section class="h-acct"><div class="h-acct-h">'
        f'<span class="h-acct-name">{html.escape(acct["label"])}</span>'
        f'<span class="h-acct-meta">day {_sign_money(acct.get("today_dollar"))} &nbsp;·&nbsp; '
        f'cost {_money(acct.get("cost_total"))} &nbsp;·&nbsp; value {_money(acct["positions_total"])} '
        f'&nbsp;·&nbsp; div/yr {_money(acct.get("div_income"))} '
        f'&nbsp; <b class="h-acct-total">{_money(acct["total"])}</b></span></div>'
        f'<div class="htable-wrap">{_positions_table(acct, cash_symbol)}</div></section>')


def holdings_html(snap: dict, updated: str = "") -> str:
    accounts = snap.get("accounts", [])
    cash_symbol = snap.get("cash_symbol", "SPAXX")
    cards = "".join(_account_card(a, cash_symbol) for a in accounts) or \
        '<p class="muted">No holdings found. Add a trade below to start.</p>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Holdings</title><style>{_CSS}{_EXTRA_CSS}</style></head>
<body><div class="wrap">
<header><h1>Holdings</h1>
  <span class="status closed">LOCAL ONLY</span>
  <span class="sub" style="margin:0">Updated {html.escape(updated)}</span>
  <button class="h-close" onclick="window.close()" title="Close tab" style="margin-left:auto">✕</button></header>
<p style="font-size:12px;margin:-6px 0 14px">
  <a class="h-back" href="/" onclick="return goBack(event)">← back to watchlist</a></p>

<div class="h-tiles">
  <div class="h-tile"><span>Total</span><b>{_money(snap.get("grand_total"))}</b></div>
  <div class="h-tile"><span>Current value</span><b>{_money(snap.get("grand_positions"))}</b></div>
  <div class="h-tile"><span>Cost basis</span><b>{_money(snap.get("grand_cost_basis"))}</b></div>
  <div class="h-tile"><span>Cash ({html.escape(cash_symbol)})</span><b>{_money(snap.get("grand_cash"))}</b></div>
  <div class="h-tile"><span>Day change</span><b>{_sign_money(snap.get("grand_today_dollar"))}</b></div>
  <div class="h-tile"><span>Dividends / yr</span><b>{_money(snap.get("grand_div_income"))}</b></div>
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
      <input id="tprice" placeholder="Price/share (opt)" inputmode="decimal">
      <label class="h-chk"><input type="checkbox" id="settle" checked> settle w/ cash</label>
      <button class="tbtn add" onclick="doTrade()">Record</button>
    </div>
    <div class="h-hint muted">Add price/share to track shares &amp; cost basis (net gain).</div>
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
Prices are live (yfinance, may be delayed); shares are inferred from value when
not recorded with a price. Net gain needs a cost basis.</p>
</div>
<script>
// Return to the watchlist tab this was opened from (don't spawn a 2nd watchlist).
function goBack(e){{ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){{ try{{ window.opener.focus(); }}catch(_){{}} window.close(); }}
  else {{ location.href='/'; }}
  return false; }}
function _v(id){{ return (document.getElementById(id).value||'').trim(); }}
function _msg(id,t,ok){{ const m=document.getElementById(id); m.textContent=t; m.className='h-msg '+(ok?'ok':'bad'); }}
function doTrade(){{
  const tk=_v('tk').toUpperCase(), acct=_v('acct'), side=_v('side'), amt=_v('amt'), price=_v('tprice');
  const settle=document.getElementById('settle').checked;
  if(!tk||!amt){{ _msg('tmsg','enter a ticker and amount',false); return; }}
  let q='?ticker='+encodeURIComponent(tk)+'&account='+encodeURIComponent(acct)
    +'&side='+side+'&amount='+encodeURIComponent(amt)+'&settle='+(settle?'1':'0');
  if(price) q+='&price='+encodeURIComponent(price);
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
.h-tile>span{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.h-tile b{font-size:23px;font-weight:700;font-variant-numeric:tabular-nums}
/* softer back link + circular close (matches the card modal ✕) */
.h-back{color:var(--muted);text-decoration:none}
.h-back:hover{color:var(--ink);text-decoration:underline}
.h-close{width:34px;height:34px;border:1px solid var(--border);border-radius:50%;
  background:var(--surface-2);color:var(--ink);font-size:17px;cursor:pointer;line-height:1;
  display:flex;align-items:center;justify-content:center}
.h-close:hover{background:var(--crit);color:#fff;border-color:transparent}
/* accounts stacked vertically */
.h-accounts{display:flex;flex-direction:column;gap:12px;margin-bottom:18px}
.h-acct{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 16px}
.h-acct-h{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;gap:10px;flex-wrap:wrap}
.h-acct-name{font-weight:650;font-size:15px}
.h-acct-meta{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.h-acct-total{font-size:15px;color:var(--accent)}
.htable-wrap{overflow-x:auto}
.htable{width:100%;border-collapse:collapse;font-size:12.5px;min-width:780px}
.htable th{text-align:right;color:var(--muted);font-size:10px;text-transform:uppercase;
  letter-spacing:.04em;padding:3px 8px;border-bottom:1px solid var(--border)}
.htable th:first-child{text-align:left}
.htable td{padding:5px 8px;text-align:right;font-variant-numeric:tabular-nums;border-bottom:1px dashed var(--border)}
.htable td.h-tk{text-align:left;font-weight:600}
.htable td.h-mv{font-weight:600} .htable td.h-pct{color:var(--muted);width:56px}
.htable tr.h-cash td{color:var(--muted)}
.up{color:var(--up)} .down{color:var(--down)}
.h-forms{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:640px){.h-forms{grid-template-columns:1fr}}
.h-form{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 16px}
.h-form-h{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}
.t-row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px;align-items:center}
.t-row input,.t-row select{padding:8px 10px;border-radius:8px;border:1px solid var(--border);
  background:var(--bg);color:var(--ink);font-size:13px}
.t-row input{flex:1 1 100px;min-width:80px}
.t-row input:focus,.t-row select:focus{outline:none;border-color:var(--accent)}
.h-chk{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:4px}
.h-hint{font-size:11px;margin:2px 0}
.tbtn.add{background:var(--accent);color:#fff;border:none;font-weight:650;padding:8px 14px;border-radius:8px;cursor:pointer}
.h-msg{font-size:12px;min-height:16px;margin-top:2px}
.h-msg.ok{color:var(--up)} .h-msg.bad{color:var(--down)}
"""
