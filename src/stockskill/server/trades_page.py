"""Trades page: what members of Congress and well-known hedge funds are buying
and selling, with one search box for a ticker, a politician or a fund.

Politicians: STOCK Act periodic transaction reports (House Clerk + Senate eFD).
Funds: SEC Form 13F quarterly holdings and the change vs the prior quarter.
Data from /api/congress, /api/funds, /api/funds/<cik>, /api/funds/search and
/api/holders/<ticker>.
"""

from __future__ import annotations

import html
import json

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def trades_html(q: str = "") -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Trades</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Trades</h1>"
            "<span class=\"sub\" style=\"margin:0\">What politicians and big funds are buying and selling</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" "
            "aria-label=\"Close\">" + icon("x", 17) + "</button></header>"
            "<div class=\"tr-bar\"><span class=\"seg\" id=\"tabs\">"
            "<button data-t=\"pol\" class=\"on\">Politicians</button><button data-t=\"fund\">Hedge funds</button></span>"
            "<input id=\"q\" placeholder=\"Search a ticker, politician or fund\" autocomplete=\"off\" "
            "value=\"" + html.escape(q) + "\"><button class=\"tr-go\" onclick=\"search()\">Search</button></div>"
            "<div id=\"tk-view\"></div>"
            "<div id=\"pol\">"
            "<div id=\"people\" class=\"people\"></div>"
            "<div class=\"tr-filters\"><span class=\"seg\" id=\"chamber\"><button data-c=\"\" class=\"on\">All</button>"
            "<button data-c=\"House\">House</button><button data-c=\"Senate\">Senate</button>"
            "<button data-c=\"President\">President</button></span>"
            "<span class=\"seg\" id=\"kind\"><button data-k=\"\" class=\"on\">All</button><button data-k=\"buy\">Buys</button>"
            "<button data-k=\"sell\">Sells</button></span><span id=\"pol-meta\" class=\"muted tr-meta\"></span></div>"
            "<div id=\"pol-top\"></div><div id=\"pol-t\" class=\"tr-tw muted\">Loading…</div>"
            "<p class=\"tr-note\">From members' periodic transaction reports (House Clerk and Senate). Members have up to "
            "45 days to report, amounts are ranges, and trades by spouses and dependents count too. Research finds members' "
            "trades have not beaten the market on average since the 2012 STOCK Act (Belmont et al., 2022). Scanned paper "
            "filings are skipped. By law these reports can't be used for commercial purposes.</p></div>"
            "<div id=\"fund\" style=\"display:none\">"
            "<div id=\"fund-search\"></div><div id=\"fund-grid\" class=\"fund-grid\"></div><div id=\"fund-detail\"></div>"
            "<p class=\"tr-note\">From SEC Form 13F: long US stock and option positions of managers with $100M+, filed up "
            "to 45 days after each quarter. It doesn't show short positions, cash, bonds or foreign stocks, so it's a "
            "partial and delayed picture of a fund.</p></div>"
            "</div><script>var INITQ=" + json.dumps(q) + ";\n" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.tr-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:4px 0 12px}
.tr-bar input{flex:1 1 260px;height:38px;padding:0 12px;border-radius:var(--r);border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font:14px var(--font)}
.tr-go{height:38px;padding:0 16px;border-radius:var(--r);border:none;background:var(--accent);color:var(--accent-ink);
  font:500 14px var(--font);cursor:pointer}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.seg button{font:500 13px var(--font);padding:0 12px;height:36px;border:none;background:var(--surface);color:var(--muted);cursor:pointer}
.seg button:hover{color:var(--ink)} .seg button.on{background:var(--surface-3);color:var(--ink)}
.tr-filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.tr-meta{font-size:13px;margin-left:4px}
.tr-tw{overflow-x:auto;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
.tr-tw.muted{padding:14px;font-size:14px}
.tr-t{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
.tr-t th,.tr-t td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap;vertical-align:top}
.tr-t th{font-size:12px;font-weight:500;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px}
.tr-t tr:last-child td{border-bottom:none}
.tr-t .r{text-align:right} .tr-t .wrap{white-space:normal;min-width:180px}
.tr-t .up{color:var(--up)} .tr-t .down{color:var(--down)} .tr-t .mu{color:var(--muted)}
.tr-t a{color:var(--link);text-decoration:none} .tr-t a:hover{text-decoration:underline}
.tr-t .sub{display:block;font-size:12px;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px;align-items:center}
.chips .lbl{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-right:4px}
.chip-b{height:30px;padding:0 10px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);
  font:500 13px var(--font);color:var(--ink);cursor:pointer}
.chip-b:hover{background:var(--surface-2)} .chip-b span{color:var(--muted);margin-left:4px}
.tr-more{margin:10px 0;height:36px;padding:0 14px;border:1px solid var(--border);border-radius:var(--r);
  background:var(--surface);font:500 13px var(--font);color:var(--ink);cursor:pointer}
.tr-note{font-size:13px;color:var(--muted);line-height:1.55;margin:10px 0 0}
.people{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:0 0 14px}
.person{display:flex;flex-direction:column;align-items:center;text-align:center;gap:4px;padding:12px 8px;
  border:1px solid var(--border);border-radius:12px;background:var(--surface);color:var(--ink);text-decoration:none;
  transition:background-color .15s ease,border-color .15s ease}
.person:hover{background:var(--surface-2);border-color:var(--ink-2)}
.person img,.person .mono{width:72px;height:88px;border-radius:10px;object-fit:cover;background:var(--surface-2)}
.person .mono{display:flex;align-items:center;justify-content:center;font:500 24px var(--font-display);color:var(--ink-2)}
.person b{font-size:14px;font-weight:500;line-height:1.25}
.person small{font-size:12px;color:var(--muted);line-height:1.35}
.pty{display:inline-block;border-radius:5px;padding:0 5px;font-size:11px;font-weight:500}
.pty.R{background:color-mix(in srgb,#c0392b 16%,transparent);color:#b03a2e}
.pty.D{background:color-mix(in srgb,#2e6db4 16%,transparent);color:#2e6db4}
.pty.I{background:var(--surface-3);color:var(--ink-2)}
.people-h{display:flex;justify-content:space-between;align-items:baseline;margin:0 0 8px}
.people-h h2{font-family:var(--font-display);font-weight:500;font-size:28px;margin:0}
.people-more{height:32px;padding:0 12px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);
  font:500 13px var(--font);color:var(--ink);cursor:pointer}
.fund-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin-bottom:14px}
.fund-card{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:12px 14px;cursor:pointer;text-align:left;
  font:14px var(--font);color:var(--ink)}
.fund-card:hover{background:var(--surface-2)} .fund-card.on{border-color:var(--accent)}
.fund-card b{font-weight:500;font-size:15px;display:block} .fund-card .m{color:var(--muted);font-size:13px}
.fund-card .n{font-size:13px;margin-top:6px}
.fd-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;margin:6px 0 10px}
.fd-h h2{font-family:var(--font-display);font-weight:500;font-size:28px;margin:0}
.tk-box{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:12px 14px;margin-bottom:14px}
.tk-box h2{font-family:var(--font-display);font-weight:500;font-size:28px;margin:0 0 8px}
.tk-box h3{font-size:15px;font-weight:500;margin:12px 0 6px}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function fdate(iso){ if(!iso) return '-'; var p=iso.split('-'); return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+p[1]-1]+' '+(+p[2])+(p[0]!==String(new Date().getFullYear())?' '+p[0]:''); }
function big(v){ if(v==null) return '-'; var a=Math.abs(v); return a>=1e9?'$'+(v/1e9).toFixed(1)+'B':(a>=1e6?'$'+(v/1e6).toFixed(0)+'M':'$'+Math.round(v).toLocaleString()); }
function daysBetween(a,b){ if(!a||!b) return null; return Math.round((new Date(b)-new Date(a))/86400000); }
function tkLink(t){ return t?'<a href="/analysis/'+encodeURIComponent(t)+'" target="_blank" rel="noopener">'+esc(t)+'</a>':'<span class="mu">-</span>'; }
function typeCell(t){ var c=(t||'').indexOf('Buy')===0?'up':((t||'').indexOf('Sell')===0?'down':'mu'); return '<span class="'+c+'">'+esc(t)+'</span>'; }
var TAB='pol', CH='', KIND='', FILTER={ticker:'',member:''}, SHOWN=100, POL=null;

// ---- tabs / search ---------------------------------------------------------
function setTab(t){ TAB=t; document.getElementById('pol').style.display=t==='pol'?'':'none';
  document.getElementById('fund').style.display=t==='fund'?'':'none';
  [].forEach.call(document.querySelectorAll('#tabs button'),function(b){ b.classList.toggle('on',b.dataset.t===t); });
  if(t==='fund') loadFunds(); }
document.getElementById('tabs').addEventListener('click',function(e){ var b=e.target.closest('button'); if(b) setTab(b.dataset.t); });
function seg(id,key,cb){ document.getElementById(id).addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return;
  [].forEach.call(this.querySelectorAll('button'),function(x){x.classList.toggle('on',x===b);}); cb(b.dataset[key]); }); }
seg('chamber','c',function(v){ CH=v; loadPol(); renderPeople(); }); seg('kind','k',function(v){ KIND=v; loadPol(); });
document.getElementById('q').addEventListener('keydown',function(e){ if(e.key==='Enter') search(); });
function search(){ var q=(document.getElementById('q').value||'').trim();
  try{ history.replaceState(null,'','/trades'+(q?'?q='+encodeURIComponent(q):'')); }catch(_){}
  FILTER={ticker:'',member:''}; document.getElementById('tk-view').innerHTML='';
  if(!q){ loadPol(); return; }
  if(/^[A-Za-z.\-]{1,6}$/.test(q) && q===q.toUpperCase()){ FILTER.ticker=q; tickerView(q); loadPol(); return; }
  if(/^[A-Za-z.\-]{1,5}$/.test(q)){ FILTER.ticker=q.toUpperCase(); tickerView(q.toUpperCase()); loadPol(); return; }
  FILTER.member=q; loadPol(); renderPeople(); fundSearch(q); }

// ---- ticker view: funds holding it + politicians trading it ---------------------
function tickerView(t){ var box=document.getElementById('tk-view');
  box.innerHTML='<div class="tk-box muted">Looking up '+esc(t)+'…</div>';
  fetch('/api/holders/'+encodeURIComponent(t)).then(function(r){return r.json();}).then(function(d){
    var f=d.funds||[], c=d.congress||[];
    var h='<div class="tk-box"><h2>'+esc(t)+'</h2><h3>Tracked funds holding it</h3>'+(f.length?'<div class="tr-tw"><table class="tr-t"><thead><tr><th>Fund</th><th>Quarter</th><th class="r">Value</th><th class="r">% of fund</th><th>Change</th></tr></thead><tbody>'+
      f.map(function(x){ return '<tr><td>'+esc(x.fund)+'<span class="sub">'+esc(x.manager)+'</span></td><td>'+fdate(x.period)+'</td><td class="r">'+big(x.value)+'</td><td class="r">'+(x.weight*100).toFixed(1)+'%</td><td>'+changeCell(x)+'</td></tr>'; }).join('')+
      '</tbody></table></div>':'<p class="muted" style="font-size:14px;margin:0">None of the tracked funds report it (or their filings are still loading).</p>')+
      '<h3>Congress trades in it (last 90 days)</h3>'+(c.length?c.length+' trades listed below.':'<span class="muted" style="font-size:14px">None reported.</span>')+'</div>';
    box.innerHTML=h; }).catch(function(){ box.innerHTML=''; }); }

// ---- people -------------------------------------------------------------------
var PEOPLE=null, PSHOW=17;
function initials(n){ return (n||'?').split(' ').filter(Boolean).map(function(w){return w[0];}).slice(0,2).join(''); }
function yrs(iso){ if(!iso) return ''; var y=Math.floor((new Date()-new Date(iso))/3.15576e10); return y<1?'under a year':y+' yr'+(y===1?'':'s'); }
function loadPeople(){ fetch('/api/politicians').then(function(r){return r.json();}).then(function(d){ PEOPLE=d; renderPeople();
  if(d.loading && !(d.people||[]).length) setTimeout(loadPeople,8000); }); }
function renderPeople(){ var box=document.getElementById('people'); if(!PEOPLE) return;
  var ppl=(PEOPLE.people||[]).filter(function(p){ return !FILTER.member || (p.name||'').toLowerCase().indexOf(FILTER.member.toLowerCase())>=0; });
  if(CH) ppl=ppl.filter(function(p){ return p.chamber===CH; });
  if(!ppl.length){ box.innerHTML=''; return; }
  var cards=ppl.slice(0,PSHOW).map(function(p){ var party=(p.party||'I')[0];
    var where=p.chamber==='President'?'President':((p.chamber==='Senate'?'Senate':'House')+' · '+esc(p.state||''));
    return '<a class="person" href="/politician/'+encodeURIComponent(p.id)+'" target="_blank" rel="noopener">'+
      '<img src="'+esc(p.photo)+'" alt="" loading="lazy" onerror="this.outerHTML=\'<div class=&quot;mono&quot;>'+esc(initials(p.name))+'</div>\'">'+
      '<b>'+esc(p.name)+'</b><small><span class="pty '+party+'">'+esc(p.party||'')+'</span> '+where+'</small>'+
      '<small>In office '+yrs(p.since)+' · '+p.trades+' trade'+(p.trades===1?'':'s')+'</small></a>'; }).join('');
  box.innerHTML='<div class="people-h" style="grid-column:1/-1"><h2>Who is trading</h2><span class="muted" style="font-size:13px">Past year · click for their profile</span></div>'+cards+
    (ppl.length>PSHOW?'<div style="grid-column:1/-1"><button class="people-more" onclick="PSHOW+=24;renderPeople()">Show more ('+(ppl.length-PSHOW)+')</button></div>':''); }

// ---- politicians -----------------------------------------------------------
function loadPol(){ var q='?chamber='+CH+'&type='+KIND+'&ticker='+encodeURIComponent(FILTER.ticker)+'&member='+encodeURIComponent(FILTER.member);
  fetch('/api/congress'+q).then(function(r){return r.json();}).then(function(d){ POL=d; SHOWN=100; renderPol();
    if(d.loading && !(d.trades||[]).length) setTimeout(loadPol,8000);
    else if(d.error && !d.as_of) setTimeout(loadPol,60000); }).catch(function(){
    document.getElementById('pol-t').textContent='Congress data unavailable right now.'; }); }
function renderPol(){ var d=POL, box=document.getElementById('pol-t');
  document.getElementById('pol-meta').textContent=(d.loading?'Updating… ':'')+(d.as_of?'Updated '+d.as_of.replace('T',' ')+' · ':'')+d.total+' trades'+(d.days?' filed in the last '+d.days+' days':'');
  var top=(d.most_bought||[]).map(function(x){ return '<button class="chip-b" onclick="pickTicker(\''+esc(x[0])+'\')">'+esc(x[0])+'<span>'+x[1]+'</span></button>'; }).join('');
  var act=(d.most_active||[]).slice(0,6).map(function(x){ return '<button class="chip-b" onclick="pickMember(\''+esc(x[0]).replace(/'/g,'')+'\')">'+esc(x[0])+'<span>'+x[1]+'</span></button>'; }).join('');
  document.getElementById('pol-top').innerHTML=(top?'<div class="chips"><span class="lbl">Most bought</span>'+top+'</div>':'')+(act?'<div class="chips"><span class="lbl">Most active</span>'+act+'</div>':'');
  var rows=(d.trades||[]).slice(0,SHOWN);
  if(!rows.length){ box.className='tr-tw muted'; box.textContent=d.loading?'Collecting the latest filings from the House and Senate (a few minutes the first time)…':
    (d.error&&!d.as_of?'Couldn\'t load the filings yet ('+d.error+'). Trying again in a few minutes.':'No trades match.'); return; }
  box.className='tr-tw';
  box.innerHTML='<table class="tr-t"><thead><tr><th>Member</th><th>Ticker</th><th>Asset</th><th>Type</th><th class="r">Amount</th><th>Traded</th><th>Reported</th><th>Owner</th></tr></thead><tbody>'+
    rows.map(function(t){ var lag=daysBetween(t.traded,t.filed);
      var who=t.member_id?'<a href="/politician/'+encodeURIComponent(t.member_id)+'" target="_blank" rel="noopener">'+esc(t.member)+'</a>':esc(t.member);
      return '<tr><td>'+who+'<span class="sub">'+esc(t.chamber)+(t.state?' · '+esc(t.state):'')+'</span></td><td>'+tkLink(t.ticker)+'</td><td class="wrap">'+esc(t.asset)+
        '</td><td>'+typeCell(t.type)+'</td><td class="r">'+esc(t.amount)+'</td><td>'+fdate(t.traded)+'</td><td><a href="'+esc(t.url)+'" target="_blank" rel="noopener">'+fdate(t.filed)+'</a>'+
        (lag!=null?'<span class="sub">'+lag+' days later</span>':'')+'</td><td>'+esc(t.owner)+'</td></tr>'; }).join('')+'</tbody></table>'+
    ((d.trades||[]).length>SHOWN?'<div style="padding:0 10px"><button class="tr-more" onclick="SHOWN+=100;renderPol()">Show more</button></div>':'');
}
function pickTicker(t){ document.getElementById('q').value=t; search(); }
function pickMember(m){ document.getElementById('q').value=m; search(); }

// ---- funds -------------------------------------------------------------------
var FUNDS=null, CUR=null;
function changeCell(x){ var c=x.change, s=x.share_change;
  if(c==='New') return '<span class="up">New</span>'; if(c==='Sold out') return '<span class="down">Sold out</span>';
  if(c==='Added') return '<span class="up">Added '+(s!=null?'+'+Math.round(s*100)+'%':'')+'</span>';
  if(c==='Trimmed') return '<span class="down">Trimmed '+(s!=null?Math.round(s*100)+'%':'')+'</span>';
  return '<span class="mu">Held</span>'; }
function loadFunds(){ fetch('/api/funds').then(function(r){return r.json();}).then(function(d){ FUNDS=d; renderFunds();
    if(d.warming) setTimeout(loadFunds,10000); }); }
function renderFunds(){ var g=document.getElementById('fund-grid');
  g.innerHTML=(FUNDS.funds||[]).map(function(f){ var c=f.counts||{};
    return '<button class="fund-card'+(CUR===f.cik?' on':'')+'" onclick="openFund('+f.cik+')"><b>'+esc(f.fund)+'</b><span class="m">'+esc(f.manager)+'</span>'+
      '<div class="n">'+(f.period?big(f.total_value)+' · '+f.positions+' positions · '+fdate(f.period):'<span class="m">Loading filings…</span>')+'</div>'+
      (f.period?'<div class="n m">'+(c.New||0)+' new, '+(c.Added||0)+' added, '+(c.Trimmed||0)+' trimmed, '+(c['Sold out']||0)+' sold</div>':'')+'</button>'; }).join(''); }
function openFund(cik){ CUR=cik; if(FUNDS) renderFunds(); var box=document.getElementById('fund-detail');
  box.innerHTML='<p class="muted">Loading the latest 13F…</p>';
  fetch('/api/funds/'+cik).then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ box.innerHTML='<p class="muted">'+esc(d.error)+'</p>'; return; }
    var hold=d.holdings.map(function(x){ return '<tr><td>'+tkLink(x.ticker)+(x.put_call?' <span class="mu">'+esc(x.put_call.toLowerCase())+'s</span>':'')+'</td><td class="wrap">'+esc(x.name)+'</td><td class="r">'+big(x.value)+'</td><td class="r">'+(x.weight*100).toFixed(1)+'%</td><td>'+changeCell(x)+'</td></tr>'; }).join('');
    var sold=d.sold_out.map(function(x){ return '<tr><td>'+tkLink(x.ticker)+'</td><td class="wrap">'+esc(x.name)+'</td><td class="r">'+big(x.prev_value)+'</td><td class="r mu">-</td><td>'+changeCell(x)+'</td></tr>'; }).join('');
    box.innerHTML='<div class="fd-h"><h2>'+esc(d.fund)+'</h2><span class="muted">'+esc(d.manager)+' · quarter ended '+fdate(d.period)+' · filed '+fdate(d.filed)+' · '+big(d.total_value)+' in '+d.positions+' positions</span></div>'+
      '<div class="tr-tw"><table class="tr-t"><thead><tr><th>Ticker</th><th>Company</th><th class="r">Value</th><th class="r">% of fund</th><th>vs '+fdate(d.prev_period)+'</th></tr></thead><tbody>'+hold+sold+'</tbody></table></div>';
    box.scrollIntoView({behavior:'smooth',block:'start'}); }).catch(function(){ box.innerHTML='<p class="muted">Could not load that fund.</p>'; }); }
function fundSearch(q){ var box=document.getElementById('fund-search');
  fetch('/api/funds/search?q='+encodeURIComponent(q)).then(function(r){return r.json();}).then(function(d){
    var r=d.results||[]; if(!r.length){ box.innerHTML=''; return; }
    box.innerHTML='<div class="chips"><span class="lbl">Funds matching "'+esc(q)+'"</span>'+r.map(function(x){
      return '<button class="chip-b" onclick="setTab(\'fund\');openFund('+x.cik+')">'+esc(x.name)+'<span>'+fdate(x.latest)+'</span></button>'; }).join('')+'</div>';
    if(r.length) setTab(TAB); }); }
(function(){ loadPeople(); if(INITQ){ search(); } else { loadPol(); } })();
"""
