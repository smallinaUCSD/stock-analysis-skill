"""Render the holdings dashboard (served locally only - never published).

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
    return "-" if x is None else "${:,.0f}".format(x)


def _price(x):
    return "-" if x is None else "${:,.2f}".format(x)


def _shares(x):
    if x is None:
        return "-"
    return f"{x:,.2f}" if x < 1000 else f"{x:,.0f}"


def _pct(x):
    if x is None:
        return '<span class="muted">-</span>'
    cls = "up" if x >= 0 else "down"
    return f'<span class="{cls}">{x*100:+.2f}%</span>'


def _sign_money(x):
    if x is None:
        return '<span class="muted">-</span>'
    cls = "up" if x >= 0 else "down"
    return f'<span class="{cls}">{"+" if x >= 0 else "-"}${abs(x):,.0f}</span>'


def _yld(x):
    if not x:
        return '<span class="muted">-</span>'
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
        '<td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td>'
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
<p style="font-size:13px;margin:-6px 0 14px">
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

<section class="h-risk">
  <div class="h-risk-h"><h2>Market risk and hedging</h2>
    <span class="seg" id="rk-bench"><button data-b="SPY" class="on">vs S&amp;P 500</button><button data-b="QQQ">vs Nasdaq-100</button></span></div>
  <div id="rk-body" class="muted">Measuring your portfolio's market risk…</div>
</section>

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

<p class="muted" style="font-size:13px;margin-top:14px">
Bookkeeping only - records what you did elsewhere; it does not place orders.
Prices are live (yfinance, may be delayed); shares are inferred from value when
not recorded with a price. Net gain needs a cost basis.</p>
</div>
<script>
// Return to the watchlist tab this was opened from (don't spawn a 2nd watchlist).
function goBack(e){{ if(e) e.preventDefault();
  // came here inside this tab: step back; opened as its own tab: close it
  var r=document.referrer||'';
  if(history.length>1 && r.indexOf(location.origin+'/')===0 && r!==location.href){{ history.back(); return false; }}
  try{{ if(window.opener && !window.opener.closed) window.opener.focus(); }}catch(_){{}}
  window.close();
  setTimeout(function(){{ location.href='/'; }}, 200);          // the browser refused to close it
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
    if(d.ok){{ _msg('tmsg',(side==='buy'?'Bought ':'Sold ')+'$'+amt+' '+tk+(d.note?' - '+d.note:''),true);
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
<script>""" + _RISK_JS + """</script>
</body></html>"""


_EXTRA_CSS = """
.h-tiles{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.h-tile{flex:1 1 140px;background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:12px 16px}
.h-tile>span{display:block;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px}
.h-tile b{font-size:22px;font-weight:500;font-variant-numeric:tabular-nums}
/* softer back link + circular close (matches the card modal ✕) */
.h-back{color:var(--muted);text-decoration:none}
.h-back:hover{color:var(--ink);text-decoration:underline}
.h-close{width:34px;height:34px;border:1px solid var(--border);border-radius:50%;
  background:var(--surface-2);color:var(--ink);font-size:18px;cursor:pointer;line-height:1;
  display:flex;align-items:center;justify-content:center}
.h-close:hover{background:var(--crit);color:#fff;border-color:transparent}
/* accounts stacked vertically */
.h-accounts{display:flex;flex-direction:column;gap:12px;margin-bottom:18px}
.h-acct{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 16px}
.h-acct-h{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;gap:10px;flex-wrap:wrap}
.h-acct-name{font-weight:500;font-size:16px}
.h-acct-meta{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.h-acct-total{font-size:16px;color:var(--accent)}
.htable-wrap{overflow-x:auto}
.htable{width:100%;border-collapse:collapse;font-size:13px;min-width:780px}
.htable th{text-align:right;color:var(--muted);font-size:12px;text-transform:uppercase;
  letter-spacing:1.5px;padding:3px 8px;border-bottom:1px solid var(--border)}
.htable th:first-child{text-align:left}
.htable td{padding:5px 8px;text-align:right;font-variant-numeric:tabular-nums;border-bottom:1px dashed var(--border)}
.htable td.h-tk{text-align:left;font-weight:500}
.htable td.h-mv{font-weight:500} .htable td.h-pct{color:var(--muted);width:56px}
.htable tr.h-cash td{color:var(--muted)}
.up{color:var(--up)} .down{color:var(--down)}
.h-forms{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:640px){.h-forms{grid-template-columns:1fr}}
.h-form{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 16px}
.h-form-h{font-size:12px;font-weight:500;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px}
.t-row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px;align-items:center}
.t-row input,.t-row select{padding:8px 10px;border-radius:8px;border:1px solid var(--border);
  background:var(--bg);color:var(--ink);font-size:14px}
.t-row input{flex:1 1 100px;min-width:80px}
.t-row input:focus,.t-row select:focus{outline:none;border-color:var(--accent)}
.h-chk{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:4px}
.h-hint{font-size:13px;margin:2px 0}
.tbtn.add{background:var(--accent);color:#fff;border:none;font-weight:500;padding:8px 14px;border-radius:8px;cursor:pointer}
.h-msg{font-size:13px;min-height:16px;margin-top:2px}
.h-msg.ok{color:var(--up)} .h-msg.bad{color:var(--down)}
.h-risk{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:18px}
.h-risk-h{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.h-risk-h h2{font-family:var(--font-display);font-weight:500;font-size:28px;margin:0}
.h-risk .seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-left:auto}
.h-risk .seg button{font:500 13px var(--font);padding:0 12px;height:34px;border:none;background:var(--bg);color:var(--muted);cursor:pointer}
.h-risk .seg button.on{background:var(--surface-3);color:var(--ink)}
.rk-tiles{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.rk-tiles .h-tile{background:var(--bg)}
.rk-tiles .h-tile small{display:block;font-size:13px;color:var(--muted);margin-top:2px}
.rk-cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:760px){.rk-cols{grid-template-columns:1fr}}
.rk-h{font-size:16px;font-weight:500;margin:4px 0 8px}
.rk-row{display:grid;grid-template-columns:70px 1fr 64px 76px;gap:8px;align-items:center;font-size:13px;margin:5px 0;font-variant-numeric:tabular-nums}
.rk-row.lt{grid-template-columns:70px 1fr 56px}
.rk-row .bar{height:6px;border-radius:3px;background:var(--surface-3);overflow:hidden}
.rk-row .bar b{display:block;height:100%;background:var(--accent);border-radius:3px}
.rk-row .r{text-align:right;color:var(--muted)}
.rk-hedge{margin-top:16px;padding-top:14px;border-top:1px solid var(--border)}
.rk-slider{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:14px;margin-bottom:10px}
.rk-slider input{width:220px;accent-color:var(--accent)}
.rk-t{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
.rk-t th{text-align:right;color:var(--muted);font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;padding:4px 8px;border-bottom:1px solid var(--border)}
.rk-t td{text-align:right;padding:7px 8px;border-bottom:1px dashed var(--border)}
.rk-t th:first-child,.rk-t td:first-child{text-align:left}
.rk-note{font-size:13px;color:var(--muted);line-height:1.55;margin-top:10px}
"""

_RISK_JS = r"""
var RK={bench:'SPY', pct:50, t:null, d:null};
function rkMoney(v){ return (v<0?'-$':'$')+Math.round(Math.abs(v)).toLocaleString(); }
function rkEsc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function rkLoad(){
  fetch('/api/holdings/risk?bench='+RK.bench+'&pct='+RK.pct).then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ document.getElementById('rk-body').textContent='Risk view unavailable.'; return; }
    RK.d=d; rkRender(); }).catch(function(){ document.getElementById('rk-body').textContent='Risk view unavailable right now.'; });
}
function rkRender(){
  var d=RK.d, p=d.portfolio, lt=d.lookthrough, body=document.getElementById('rk-body'); body.className='';
  var topU=lt.top.length?lt.top[0]:null;
  var tiles='<div class="rk-tiles">'+
    '<div class="h-tile"><span>Portfolio beta</span><b>'+(p.beta==null?'n/a':p.beta.toFixed(2))+'</b><small>vs the '+d.bench_name+', cash counted as 0</small></div>'+
    '<div class="h-tile"><span>Moves like</span><b>'+rkMoney(p.exposure)+'</b><small>of the '+d.bench_name+'</small></div>'+
    '<div class="h-tile"><span>Look-through leverage</span><b>'+(lt.leverage?lt.leverage.toFixed(2)+'x':'n/a')+'</b><small>'+rkMoney(lt.notional)+' of underlying stock</small></div>'+
    (topU?'<div class="h-tile"><span>Largest underlying</span><b>'+rkEsc(topU.underlying)+' '+(topU.share*100).toFixed(0)+'%</b><small>of look-through exposure</small></div>':'')+
    '</div>';
  var mx=Math.max.apply(null,p.rows.map(function(r){return r.share;}).concat([0.0001]));
  var risk='<div><div class="rk-h">Where the market risk comes from</div>'+p.rows.slice(0,10).map(function(r){
    return '<div class="rk-row"><b>'+rkEsc(r.ticker)+'</b><span class="bar"><b style="width:'+(r.share/mx*100).toFixed(1)+'%"></b></span>'+
      '<span class="r">beta '+r.beta.toFixed(2)+'</span><span class="r">'+(r.share*100).toFixed(0)+'%</span></div>'; }).join('')+
    (p.missing.length?'<div class="rk-note">No price history to measure: '+p.missing.map(rkEsc).join(', ')+' (left out).</div>':'')+'</div>';
  var mx2=Math.max.apply(null,lt.top.map(function(r){return r.share;}).concat([0.0001]));
  var own='<div><div class="rk-h">What you really own (look-through)</div>'+lt.top.map(function(u){
    return '<div class="rk-row lt"><b>'+rkEsc(u.underlying)+'</b><span class="bar"><b style="width:'+(u.share/mx2*100).toFixed(1)+'%"></b></span>'+
      '<span class="r">'+(u.share*100).toFixed(1)+'%</span></div>'; }).join('')+
    '<div class="rk-note">Leveraged funds expanded into the stocks they hold, times their leverage.</div></div>';
  var rows=d.hedges.map(function(h){ var dr=h.drag_1y;
    var drag=dr?('<span class="'+(dr.drag<0?'down':'up')+'">'+(dr.drag*100>0?'+':'')+(dr.drag*100).toFixed(1)+' pts</span>'):'<span class="muted">-</span>';
    return '<tr><td>'+rkEsc(h.label)+'</td><td>'+h.action+'</td><td>'+rkMoney(h.dollars)+'</td><td>'+(h.shares==null?'-':Math.round(h.shares).toLocaleString())+'</td><td>'+drag+'</td></tr>'; }).join('');
  var puts=d.puts&&d.puts.contracts!=null?('<div class="rk-note">Or with options: about <b>'+d.puts.contracts.toFixed(1)+'</b> at-the-money '+d.bench+
    ' put contracts (delta about 0.5, so approximate; the count drifts as the market moves, and puts cost a premium).</div>'):'';
  var hedge='<div class="rk-hedge"><div class="rk-h">Hedge calculator</div>'+
    '<div class="rk-slider"><span>Offset</span><input type="range" id="rk-pct" min="0" max="100" step="5" value="'+RK.pct+'">'+
    '<b id="rk-pv">'+RK.pct+'%</b><span class="muted">of your '+rkMoney(p.exposure)+' market exposure ('+rkMoney(p.exposure*RK.pct/100)+')</span></div>'+
    '<div class="htable-wrap"><table class="rk-t"><thead><tr><th>Instrument</th><th>Action</th><th>Amount</th><th>&asymp; Shares</th><th>Past-year reset effect</th></tr></thead><tbody>'+rows+'</tbody></table></div>'+puts+
    '<div class="rk-note">Any one row does the job on its own; they are alternatives, not a combination. Inverse funds reset daily, so '+
    'held for weeks they drift from their multiple: the "reset effect" is how far each landed from its multiple of the index over the past year '+
    '(negative means the reset cost you, as in choppy markets; it can help in a steady trend). '+
    'A hedge cuts the downside and the upside alike. Analysis only; nothing here places a trade.</div></div>';
  body.innerHTML=tiles+'<div class="rk-cols">'+risk+own+'</div>'+hedge;
  var sl=document.getElementById('rk-pct');
  sl.addEventListener('input',function(){ RK.pct=+this.value; document.getElementById('rk-pv').textContent=RK.pct+'%';
    clearTimeout(RK.t); RK.t=setTimeout(rkLoad,200); });
}
document.getElementById('rk-bench').addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return;
  [].forEach.call(this.querySelectorAll('button'),function(x){x.classList.toggle('on',x===b);}); RK.bench=b.dataset.b;
  document.getElementById('rk-body').className='muted'; document.getElementById('rk-body').textContent='Measuring…'; rkLoad(); });
rkLoad();
"""
