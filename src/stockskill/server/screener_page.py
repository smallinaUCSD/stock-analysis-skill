"""Screener page: filter every US-listed common stock by size, sector,
valuation, profitability and growth. The whole table comes from
/api/screener once; filtering and sorting run in the browser."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def screener_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Screener</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Screener</h1>"
            "<span class=\"sub\" style=\"margin:0\">Every US-listed stock, filtered your way</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div class=\"sc-presets\" id=\"sc-presets\"></div>"
            "<div class=\"sc-panel\">"
            "<div class=\"sc-row\">"
            "<input id=\"sc-q\" class=\"sc-in\" placeholder=\"Search name, ticker or industry\" autocomplete=\"off\">"
            "<select id=\"sc-sector\" class=\"sc-in\"><option value=\"\">All sectors</option></select>"
            "<select id=\"sc-cap\" class=\"sc-in\"><option value=\"\">Any size</option>"
            "<option value=\"mega\">Mega (over $200B)</option><option value=\"large\">Large ($10B to $200B)</option>"
            "<option value=\"mid\">Mid ($2B to $10B)</option><option value=\"small\">Small ($300M to $2B)</option>"
            "<option value=\"micro\">Micro (under $300M)</option></select>"
            "<label class=\"sc-chk\"><input type=\"checkbox\" id=\"sc-watch\"> Watchlist only</label>"
            "</div>"
            "<div id=\"sc-filters\"></div>"
            "<div class=\"sc-row\"><select id=\"sc-add\" class=\"sc-in\"><option value=\"\">+ Add a filter…</option></select>"
            "<button class=\"sc-link\" onclick=\"resetAll()\">Clear all</button>"
            "<span class=\"sc-count\" id=\"sc-count\"></span>"
            "<button class=\"sc-btn\" onclick=\"exportCsv()\">Export CSV</button></div>"
            "</div>"
            "<div id=\"sc-table\" class=\"sc-box muted\">Loading the market…</div>"
            "<div id=\"sc-more\"></div>"
            "<p class=\"sc-note\" id=\"sc-note\">Prices, market values and sectors are from Nasdaq's public stock screener "
            "(delayed). Fundamentals are from SEC filings: each company's fiscal year closest to the last calendar year, "
            "with growth against the year before. Foreign companies that file under IFRS show no fundamentals. "
            "Momentum columns (1M, 3M, 1Y) are only filled for your watchlist.</p>"
            "</div><script>" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.sc-presets{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 12px}
.sc-chip{height:32px;padding:0 14px;border-radius:16px;border:1px solid var(--border);background:var(--surface);
  color:var(--ink);font:13px var(--font);cursor:pointer;transition:background .15s var(--ease-out),border-color .15s var(--ease-out)}
.sc-chip:hover{border-color:var(--border-strong)} .sc-chip.on{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.sc-panel{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:10px 12px;margin-bottom:12px}
.sc-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:4px 0}
.sc-in{height:36px;padding:0 10px;border-radius:var(--r);border:1px solid var(--border);background:var(--bg);color:var(--ink);font:13px var(--font)}
#sc-q{flex:1;min-width:200px}
.sc-chk{font-size:13px;display:flex;gap:6px;align-items:center;color:var(--muted);cursor:pointer}
.sc-f{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:6px 0;border-top:1px solid var(--border);font-size:13px}
.sc-f:first-child{border-top:none}
.sc-f .lbl{min-width:170px}
.sc-f input{width:92px;height:32px;padding:0 8px;border-radius:var(--r);border:1px solid var(--border);background:var(--bg);color:var(--ink);font:13px var(--font)}
.sc-f .u{color:var(--muted);min-width:24px}
.sc-f .x{border:none;background:none;color:var(--muted);cursor:pointer;font-size:18px;line-height:1;padding:0 6px}
.sc-f .x:hover{color:var(--ink)}
.sc-link{border:none;background:none;color:var(--link);font:13px var(--font);cursor:pointer}
.sc-count{margin-left:auto;font-size:13px;color:var(--muted)}
.sc-btn{height:34px;padding:0 14px;border-radius:var(--r);border:1px solid var(--border);background:var(--bg);color:var(--ink);font:13px var(--font);cursor:pointer}
.sc-btn:hover{border-color:var(--border-strong)}
.sc-box{border:1px solid var(--border);border-radius:12px;background:var(--surface);overflow-x:auto}
.sc-box.muted{padding:14px;font-size:14px;color:var(--muted)}
.sc-t{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
.sc-t th,.sc-t td{padding:7px 10px;text-align:right;white-space:nowrap;border-top:1px solid var(--border)}
.sc-t thead th{border-top:none;font-weight:500;color:var(--muted);font-size:12px;cursor:pointer;user-select:none;position:sticky;top:0;background:var(--surface)}
.sc-t thead th:hover{color:var(--ink)} .sc-t thead th.on{color:var(--ink)}
.sc-t th.l,.sc-t td.l{text-align:left}
.sc-t td.nm{max-width:220px;overflow:hidden;text-overflow:ellipsis}
.sc-t td.sec{max-width:150px;overflow:hidden;text-overflow:ellipsis;color:var(--muted)}
.sc-t tbody tr{cursor:pointer} .sc-t tbody tr:hover td{background:var(--bg)}
.sc-t .up{color:var(--up)} .sc-t .dn{color:var(--down)} .sc-t .na{color:var(--muted)}
.sc-t .dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);margin-left:5px;vertical-align:2px}
.sc-t .add{border:1px solid var(--border);background:var(--bg);color:var(--ink);border-radius:var(--r);height:26px;padding:0 9px;font:12px var(--font);cursor:pointer}
.sc-t .add:hover{border-color:var(--border-strong)}
#sc-more{text-align:center;margin:10px 0}
.sc-note{font-size:13px;color:var(--muted);line-height:1.55;margin:12px 0 0}
@media (max-width:640px){.sc-f{gap:6px}.sc-f .lbl{min-width:100%}.sc-f input{width:64px}.sc-f .u{min-width:14px}.sc-count{margin-left:0;width:100%}}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
function openTab(u){ var w=window.open(u,'_blank'); if(!w) location.href=u; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
// key, label, kind: pct (filter in %), usd (filter in $B), x (multiple), px (price), n (plain)
var M=[['mcap','Market cap','usd'],['price','Price','px'],['chg','Day change','pct'],['pe','P/E','x'],['ps','Price / sales','x'],
  ['pb','Price / book','x'],['pfcf','Price / free cash flow','x'],['fcf_yield','Free cash flow yield','pct'],['ev_sales','EV / sales','x'],
  ['rev_growth','Revenue growth','pct'],['ni_growth','Net income growth','pct'],['gross_margin','Gross margin','pct'],
  ['op_margin','Operating margin','pct'],['net_margin','Net margin','pct'],['roe','Return on equity','pct'],['debt_equity','Debt / equity','x'],
  ['div_yield','Dividend yield','pct'],
  ['revenue','Revenue','usd'],['net_income','Net income','usd'],['fcf','Free cash flow','usd'],['volume','Volume','n'],
  ['r1m','1-month return','pct'],['r3m','3-month return','pct'],['r1y','1-year return','pct']];
var MK={}; M.forEach(function(m){ MK[m[0]]=m; });
var SHORT={mcap:'Mkt cap',price:'Price',chg:'Day',pe:'P/E',ps:'P/S',pb:'P/B',pfcf:'P/FCF',fcf_yield:'FCF yld',ev_sales:'EV/S',
  rev_growth:'Rev gr',ni_growth:'NI gr',gross_margin:'Gross m',op_margin:'Op m',net_margin:'Net m',roe:'ROE',debt_equity:'D/E',
  revenue:'Revenue',net_income:'Net inc',fcf:'FCF',volume:'Volume',r1m:'1M',r3m:'3M',r1y:'1Y',div_yield:'Div yld'};
var MOVES={chg:1,r1m:1,r3m:1,r1y:1};   // price moves get up/down colour; ratios don't
var BASE=['mcap','price','chg','pe','ps','fcf_yield','rev_growth','net_margin','roe'];
var PRESETS=[
  ['Profitable growth',{f:[['rev_growth',20,null],['net_margin',10,null],['mcap',1,null]],sort:'rev_growth'}],
  ['Quality at a fair price',{f:[['roe',15,null],['pe',null,25],['debt_equity',null,1],['mcap',1,null]],sort:'roe'}],
  ['Cash machines',{f:[['fcf_yield',6,null],['mcap',2,null]],sort:'fcf_yield'}],
  ['Dividend payers',{f:[['div_yield',3,null],['mcap',2,null]],sort:'div_yield'}],
  ['Cheap by earnings',{f:[['pe',0.01,12],['mcap',1,null],['ni_growth',0,null]],sort:'pe',asc:true}],
  ['Big movers today',{f:[['chg',5,null],['mcap',2,null]],sort:'chg'}],
  ['Biggest losers today',{f:[['chg',null,-5],['mcap',2,null]],sort:'chg',asc:true}],
  ['Mega caps',{f:[],cap:'mega',sort:'mcap'}],
  ['Your watchlist',{f:[],watch:true,sort:'mcap'}]];
var COLS=null, ROWS=[], S={q:'',sector:'',cap:'',watch:false,f:[],sort:'mcap',asc:false}, SHOWN=100, VIEW=[];
function col(r,k){ return r[COLS[k]]; }
function fmt(v,kind){
  if(v==null||!isFinite(v)) return '—';
  if(kind==='pct') return (v>0?'+':'')+(v*100).toFixed(Math.abs(v)<0.1?1:0)+'%';
  if(kind==='x') return v.toFixed(v<10?1:0)+'x';
  if(kind==='px') return '$'+(v<1000?v.toFixed(2):Math.round(v).toLocaleString('en-US'));
  if(kind==='n') return v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(0)+'K':String(v);
  var a=Math.abs(v), s=v<0?'-':'';
  return a>=1e12?s+'$'+(a/1e12).toFixed(2)+'T':a>=1e9?s+'$'+(a/1e9).toFixed(a>=1e11?0:1)+'B':a>=1e6?s+'$'+(a/1e6).toFixed(0)+'M':s+'$'+a.toFixed(0);
}
function toVal(x,kind){ if(x===''||x==null) return null; var n=parseFloat(x); if(!isFinite(n)) return null;
  return kind==='pct'?n/100:kind==='usd'?n*1e9:n; }
function fromVal(v,kind){ if(v==null) return ''; return kind==='pct'?+(v*100).toFixed(4):kind==='usd'?+(v/1e9).toFixed(4):v; }
var CAP={mega:[200e9,null],large:[10e9,200e9],mid:[2e9,10e9],small:[3e8,2e9],micro:[null,3e8]};
function apply(){
  if(!COLS) return;                                  // still loading; the load handler applies
  var q=S.q.toLowerCase(), cap=CAP[S.cap];
  var fs=S.f.map(function(f){ var k=MK[f[0]][2]; return [COLS[f[0]], toVal(f[1],k), toVal(f[2],k)]; });
  VIEW=ROWS.filter(function(r){
    if(S.watch && !col(r,'watch')) return false;
    if(S.sector && col(r,'sector')!==S.sector) return false;
    if(cap){ var m=col(r,'mcap'); if(m==null || (cap[0]!=null&&m<cap[0]) || (cap[1]!=null&&m>=cap[1])) return false; }
    if(q){ var h=(col(r,'ticker')+' '+(col(r,'name')||'')+' '+(col(r,'industry')||'')).toLowerCase(); if(h.indexOf(q)<0) return false; }
    for(var i=0;i<fs.length;i++){ var v=r[fs[i][0]]; if(fs[i][1]==null&&fs[i][2]==null) continue;
      if(v==null) return false; if(fs[i][1]!=null&&v<fs[i][1]) return false; if(fs[i][2]!=null&&v>fs[i][2]) return false; }
    return true; });
  var si=COLS[S.sort], dir=S.asc?1:-1;
  VIEW.sort(function(a,b){ var x=a[si], y=b[si]; if(x==null&&y==null) return 0; if(x==null) return 1; if(y==null) return -1;
    return typeof x==='string'?dir*x.localeCompare(y):dir*(x-y); });
  SHOWN=100; render(); save();
}
function shownCols(){ var c=BASE.slice(); S.f.forEach(function(f){ if(c.indexOf(f[0])<0) c.push(f[0]); });
  if(S.watch) ['r1m','r3m','r1y'].forEach(function(k){ if(c.indexOf(k)<0) c.push(k); }); return c; }
function render(){
  document.getElementById('sc-count').textContent=VIEW.length.toLocaleString()+' of '+ROWS.length.toLocaleString()+' stocks';
  var cs=shownCols();
  var th='<tr><th class="l" data-k="ticker">Ticker</th><th class="l" data-k="name">Company</th><th class="l" data-k="sector">Sector</th>'+
    cs.map(function(k){ return '<th data-k="'+k+'"'+(S.sort===k?' class="on"':'')+' title="'+esc(MK[k][1])+'">'+SHORT[k]+(S.sort===k?(S.asc?' ↑':' ↓'):'')+'</th>'; }).join('')+'<th></th></tr>';
  var body=VIEW.slice(0,SHOWN).map(function(r){ var t=col(r,'ticker');
    return '<tr data-t="'+esc(t)+'"><td class="l"><b>'+esc(t)+'</b>'+(col(r,'watch')?'<span class="dot" title="On your watchlist"></span>':'')+'</td>'+
      '<td class="l nm" title="'+esc(col(r,'name'))+'">'+esc(col(r,'name'))+'</td><td class="l sec" title="'+esc(col(r,'industry')||'')+'">'+esc(col(r,'sector')||'')+'</td>'+
      cs.map(function(k){ var v=col(r,k), kind=MK[k][2];
        var cls=v==null?'na':(MOVES[k]?(v>=0?'up':'dn'):'');
        return '<td class="'+cls+'">'+fmt(v,kind)+'</td>'; }).join('')+
      '<td>'+(col(r,'watch')?'':'<button class="add" data-add="'+esc(t)+'" title="Add to watchlist">+ Watch</button>')+'</td></tr>'; }).join('');
  var box=document.getElementById('sc-table'); box.className='sc-box';
  box.innerHTML=VIEW.length?'<table class="sc-t"><thead>'+th+'</thead><tbody>'+body+'</tbody></table>':'<div style="padding:14px" class="na">No stocks match. Loosen a filter.</div>';
  document.getElementById('sc-more').innerHTML=VIEW.length>SHOWN?'<button class="sc-btn" onclick="SHOWN+=200;render()">Show more ('+(VIEW.length-SHOWN).toLocaleString()+' left)</button>':'';
}
document.getElementById('sc-table').addEventListener('click',function(e){
  var a=e.target.closest('[data-add]'); if(a){ e.stopPropagation(); addWatch(a); return; }
  var h=e.target.closest('th[data-k]'); if(h){ var k=h.getAttribute('data-k'); if(S.sort===k) S.asc=!S.asc; else { S.sort=k; S.asc=(k==='ticker'||k==='name'||k==='sector'); } apply(); return; }
  var tr=e.target.closest('tr[data-t]'); if(tr) openTab('/analysis/'+encodeURIComponent(tr.getAttribute('data-t')));
});
function addWatch(b){ var t=b.getAttribute('data-add'); b.disabled=true; b.textContent='Adding…';
  fetch('/api/watchlist/add?ticker='+encodeURIComponent(t),{method:'POST'}).then(function(r){return r.json();}).then(function(d){
    b.textContent=d.ok?'Added':'Failed'; if(d.ok){ var r=ROWS.find(function(x){return col(x,'ticker')===t;}); if(r) r[COLS.watch]=true; } })
  .catch(function(){ b.textContent='Failed'; }); }
function filtersUi(){
  document.getElementById('sc-filters').innerHTML=S.f.map(function(f,i){ var m=MK[f[0]], u=m[2]==='pct'?'%':m[2]==='usd'?'$B':m[2]==='x'?'x':'';
    return '<div class="sc-f"><span class="lbl">'+esc(m[1])+'</span>at least <input data-i="'+i+'" data-j="1" value="'+esc(f[1]==null?'':f[1])+'" inputmode="decimal"><span class="u">'+u+'</span>'+
      'at most <input data-i="'+i+'" data-j="2" value="'+esc(f[2]==null?'':f[2])+'" inputmode="decimal"><span class="u">'+u+'</span>'+
      '<button class="x" data-rm="'+i+'" title="Remove">&times;</button></div>'; }).join('');
  var used={}; S.f.forEach(function(f){ used[f[0]]=1; });
  document.getElementById('sc-add').innerHTML='<option value="">+ Add a filter…</option>'+M.filter(function(m){return !used[m[0]];}).map(function(m){ return '<option value="'+m[0]+'">'+esc(m[1])+'</option>'; }).join('');
}
var tmr=null;
document.getElementById('sc-filters').addEventListener('input',function(e){ var el=e.target; if(!el.hasAttribute('data-i')) return;
  S.f[+el.getAttribute('data-i')][+el.getAttribute('data-j')]=el.value===''?null:el.value; clearPreset(); clearTimeout(tmr); tmr=setTimeout(apply,200); });
document.getElementById('sc-filters').addEventListener('click',function(e){ var b=e.target.closest('[data-rm]'); if(!b) return;
  S.f.splice(+b.getAttribute('data-rm'),1); clearPreset(); filtersUi(); apply(); });
document.getElementById('sc-add').addEventListener('change',function(e){ if(!e.target.value) return; S.f.push([e.target.value,null,null]); clearPreset(); filtersUi(); apply();
  var ins=document.querySelectorAll('#sc-filters input'); if(ins.length) ins[ins.length-2].focus(); });
document.getElementById('sc-q').addEventListener('input',function(e){ S.q=e.target.value; clearTimeout(tmr); tmr=setTimeout(apply,150); });
document.getElementById('sc-sector').addEventListener('change',function(e){ S.sector=e.target.value; clearPreset(); apply(); });
document.getElementById('sc-cap').addEventListener('change',function(e){ S.cap=e.target.value; clearPreset(); apply(); });
document.getElementById('sc-watch').addEventListener('change',function(e){ S.watch=e.target.checked; clearPreset(); apply(); });
function syncControls(){ document.getElementById('sc-q').value=S.q; document.getElementById('sc-sector').value=S.sector;
  document.getElementById('sc-cap').value=S.cap; document.getElementById('sc-watch').checked=S.watch; filtersUi(); }
function clearPreset(){ document.querySelectorAll('.sc-chip').forEach(function(c){ c.classList.remove('on'); }); }
function track(n,d){ try{ navigator.sendBeacon('/api/t', new Blob([JSON.stringify({name:n,detail:d||''})],{type:'application/json'})); }catch(_){} }
function preset(i){ var p=PRESETS[i][1]; track('screen_preset', PRESETS[i][0]);
  S={q:'',sector:'',cap:p.cap||'',watch:!!p.watch,f:p.f.map(function(x){return x.slice();}),sort:p.sort||'mcap',asc:!!p.asc};
  syncControls(); apply(); document.querySelectorAll('.sc-chip').forEach(function(c,j){ c.classList.toggle('on',j===i); }); }
function resetAll(){ S={q:'',sector:'',cap:'',watch:false,f:[],sort:'mcap',asc:false}; syncControls(); clearPreset(); apply(); }
function save(){ try{ localStorage.setItem('sc-state',JSON.stringify(S)); }catch(_){} }
function exportCsv(){ track('screen_export'); var cs=['ticker','name','sector','industry'].concat(shownCols());
  var lines=[cs.map(function(k){return MK[k]?MK[k][1]:k.charAt(0).toUpperCase()+k.slice(1);}).join(',')].concat(VIEW.map(function(r){
    return cs.map(function(k){ var v=col(r,k); if(v==null) return ''; return typeof v==='string'?'"'+v.replace(/"/g,'""')+'"':v; }).join(','); }));
  var a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/csv'}));
  a.download='screen-'+new Date().toISOString().slice(0,10)+'.csv'; document.body.appendChild(a); a.click(); a.remove(); }
document.getElementById('sc-presets').innerHTML=PRESETS.map(function(p,i){ return '<button class="sc-chip" onclick="preset('+i+')">'+esc(p[0])+'</button>'; }).join('');
function load(){
  fetch('/api/screener').then(function(r){return r.json();}).then(function(d){
    var box=document.getElementById('sc-table');
    if(!d.ok){ box.textContent=d.error||'Unavailable.'; return; }
    if(d.warming){ box.textContent=d.error?('Could not build the market table: '+d.error):'Gathering prices and SEC filings for about 6,000 stocks (first load takes about 30 seconds)…';
      if(!d.error) setTimeout(load,4000); return; }
    COLS={}; d.table.cols.forEach(function(c,i){ COLS[c]=i; }); ROWS=d.table.data;
    var secs={}; ROWS.forEach(function(r){ var s=col(r,'sector'); if(s) secs[s]=1; });
    document.getElementById('sc-sector').innerHTML='<option value="">All sectors</option>'+Object.keys(secs).sort().map(function(s){ return '<option>'+esc(s)+'</option>'; }).join('');
    try{ var s0=JSON.parse(localStorage.getItem('sc-state')||'null'); if(s0&&s0.f) S=s0; }catch(_){}
    if(S.sort && COLS[S.sort]==null) S.sort='mcap';
    syncControls(); apply();
    document.getElementById('sc-note').insertAdjacentHTML('beforeend',' Fundamentals: fiscal years closest to '+d.year+'.');
  }).catch(function(){ document.getElementById('sc-table').textContent='Could not load the screener.'; });
}
load();
"""
