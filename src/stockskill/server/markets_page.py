"""Markets page: stocks around the world, Treasury yields, bond funds,
commodities, currencies and crypto on one screen. Data from /api/markets."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def markets_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Markets</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Markets</h1>"
            "<span class=\"sub\" style=\"margin:0\">Stocks, bonds, commodities, currencies and crypto</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<nav class=\"mk-nav\" id=\"mk-nav\"></nav>"
            "<div id=\"mk\" class=\"mk-box muted\">Loading markets…</div>"
            "<p class=\"mk-note\">Delayed prices from Yahoo, refreshed every 10 minutes while markets are open. "
            "Yield moves are in basis points (0.01 percentage point). Futures prices switch to the next contract each "
            "month or quarter, which can show up as a one-day jump. Click any row for its one-year chart. "
            "<a href=\"/economy\" onclick=\"window.open(this.href,'_blank');return false\">Yield curve and economic calendar</a></p>"
            "</div><script>" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.mk-nav{position:sticky;top:0;z-index:5;display:flex;gap:6px;flex-wrap:wrap;padding:8px 0;background:var(--bg);margin-bottom:6px}
.mk-nav a{height:32px;display:inline-flex;align-items:center;padding:0 12px;border-radius:16px;border:1px solid var(--border);
  background:var(--surface);color:var(--ink);text-decoration:none;font-size:13px}
.mk-nav a:hover{border-color:var(--border-strong)}
.mk-sec{margin:0 0 18px} .mk-sec h2{font-family:var(--font-display);font-weight:500;font-size:24px;margin:0 0 8px;scroll-margin-top:56px}
.mk-box{border:1px solid var(--border);border-radius:12px;background:var(--surface);overflow-x:auto}
.mk-box.muted{padding:14px;color:var(--muted);font-size:14px}
.mk-t{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
.mk-t th,.mk-t td{padding:9px 12px;text-align:right;white-space:nowrap;border-top:1px solid var(--border)}
.mk-t thead th{border-top:none;font-weight:500;color:var(--muted);font-size:12px}
.mk-t th:first-child,.mk-t td:first-child{text-align:left}
.mk-t tbody tr.r{cursor:pointer} .mk-t tbody tr.r:hover td{background:var(--bg)}
.mk-t .up{color:var(--up)} .mk-t .dn{color:var(--down)} .mk-t .na{color:var(--muted)}
.mk-t td.sp{width:120px;padding:4px 12px}
.mk-t tr.ch td{background:var(--bg);padding:10px 14px}
.mk-t tr.ch svg{display:block;width:100%;height:auto}
.mk-note{font-size:13px;color:var(--muted);line-height:1.55;margin:12px 0 0} .mk-note a{color:var(--link)}
@media (max-width:760px){.mk-t .hide-s{display:none}}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function lvl(r){ var v=r.last;
  if(r.kind==='yield') return v.toFixed(2)+'%';
  if(r.kind==='fx') return v<10?v.toFixed(4):v.toFixed(2);
  return v>=1000?v.toLocaleString('en-US',{maximumFractionDigits:0}):v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
function mv(r,k){ var v=r[k]; if(v==null) return '<td class="na">—</td>';
  var up=v>=0, t=r.kind==='yield'?(v>=0?'+':'')+Math.round(v*100)+' bp':(v>=0?'+':'')+(v*100).toFixed(Math.abs(v)<0.1?2:1)+'%';
  // for yields, a rise is shown neutrally (good for savers, bad for borrowers)
  return '<td class="'+(r.kind==='yield'?'':(up?'up':'dn'))+(k==='d1'?'':' hide-s')+'">'+t+'</td>'; }
function spark(v, w, h, strong){ if(!v||v.length<2) return '';
  var lo=Math.min.apply(null,v), hi=Math.max.apply(null,v), rg=(hi-lo)||1, n=v.length-1;
  var pts=v.map(function(x,i){ return (i/n*w).toFixed(1)+','+(h-3-(x-lo)/rg*(h-6)).toFixed(1); }).join(' ');
  return '<svg viewBox="0 0 '+w+' '+h+'"'+(strong?'':' width="'+w+'" height="'+h+'"')+'><polyline points="'+pts+'" fill="none" stroke="var(--accent)" stroke-width="'+(strong?2:1.5)+'"/></svg>'; }
function render(d){
  var box=document.getElementById('mk');
  if(!d.ok||!d.sections.length){ box.className='mk-box muted'; box.textContent=d.error||'Market data is unavailable right now.'; return; }
  document.getElementById('mk-nav').innerHTML=d.sections.map(function(s,i){ return '<a href="#s'+i+'">'+esc(s.name)+'</a>'; }).join('');
  box.className=''; box.innerHTML=d.sections.map(function(s,i){
    return '<section class="mk-sec"><h2 id="s'+i+'">'+esc(s.name)+'</h2><div class="mk-box"><table class="mk-t"><thead><tr><th>'+
      '</th><th>Last</th><th>Day</th><th class="hide-s">Week</th><th class="hide-s">Month</th><th class="hide-s">This year</th><th class="hide-s">1 year</th><th class="hide-s">3 months</th></tr></thead><tbody>'+
      s.rows.map(function(r,j){ return '<tr class="r" data-k="'+i+'-'+j+'"><td>'+esc(r.name)+'</td><td>'+lvl(r)+'</td>'+mv(r,'d1')+mv(r,'w1')+mv(r,'m1')+mv(r,'ytd')+mv(r,'y1')+
        '<td class="sp hide-s">'+spark(r.spark,110,26)+'</td></tr>'; }).join('')+'</tbody></table></div></section>'; }).join('');
  box.onclick=function(e){ var tr=e.target.closest('tr.r'); if(!tr) return;
    var nx=tr.nextElementSibling; if(nx&&nx.classList.contains('ch')){ nx.remove(); return; }
    var k=tr.getAttribute('data-k').split('-'), r=d.sections[+k[0]].rows[+k[1]];
    tr.insertAdjacentHTML('afterend','<tr class="ch"><td colspan="8"><div class="small muted" style="margin-bottom:4px">'+esc(r.name)+
      ', last 12 months (weekly)</div>'+spark(r.line,600,120,true)+'</td></tr>'); };
}
function load(){ fetch('/api/markets').then(function(r){return r.json();}).then(render)
  .catch(function(){ document.getElementById('mk').textContent='Could not load market data.'; }); }
load(); setInterval(function(){ if(!document.hidden) load(); }, 600000);
"""
