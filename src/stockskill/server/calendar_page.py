"""Calendar: your watchlist's earnings and the market's important dates
(economic releases, Fed decisions, holidays and early closes, options
expiration, IPOs) as a month grid or a list. Data from /api/calendar."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def calendar_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Calendar</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Calendar</h1>"
            "<span class=\"sub\" style=\"margin:0\">Your stocks' earnings and the market's important dates</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div class=\"cal-bar\"><span class=\"seg cal-seg\" id=\"cal-view\"><button data-v=\"month\" class=\"on\">Month</button>"
            "<button data-v=\"list\">List</button></span>"
            "<span class=\"cal-kinds\" id=\"cal-kinds\"></span>"
            "<a class=\"cal-ics\" href=\"/api/calendar.ics\" download>Add to my calendar (.ics)</a></div>"
            "<div id=\"cal\" class=\"muted\">Loading…</div><div id=\"cal-day\"></div>"
            "<p class=\"cal-note\">Times are Eastern. Earnings dates come from company announcements and estimates "
            "(Finnhub) and can move; economic releases from the BLS and BEA calendars; Fed decisions from the Federal "
            "Reserve. Holidays follow NYSE's schedule.</p>"
            "</div><script>" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.cal-bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:4px 0 14px}
.cal-seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.cal-seg button{height:34px;padding:0 14px;border:none;background:var(--surface);color:var(--muted);font:500 13px var(--font);cursor:pointer}
.cal-seg button.on{background:var(--surface-3);color:var(--ink)}
.cal-kinds{display:flex;flex-wrap:wrap;gap:6px;flex:1}
.cal-k{height:32px;padding:0 12px;border-radius:16px;border:1px solid var(--border);background:var(--surface);color:var(--ink);
  font:13px var(--font);cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.cal-k.off{opacity:.45}
.cal-k i,.cal-p i,.cal-li i{display:inline-block;width:8px;height:8px;border-radius:50%;flex:none}
.cal-ics{font-size:13px;color:var(--accent)}
.k-earnings{background:var(--accent)} .k-economy{background:#4f86d9} .k-fed{background:#a45fd0}
.k-market{background:var(--down)} .k-options{background:#c99a2e} .k-ipo{background:var(--up)}
.cal-nav{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.cal-nav h2{font-family:var(--font-display);font-weight:500;font-size:26px;margin:0;flex:1}
.cal-nav button{height:34px;min-width:34px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--ink);cursor:pointer;font:14px var(--font)}
.cal-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border:1px solid var(--border);border-radius:12px;overflow:hidden;background:var(--border);gap:1px}
.cal-dow{background:var(--surface);font-size:12px;color:var(--muted);padding:6px 8px;text-transform:uppercase;letter-spacing:1px}
.cal-c{background:var(--bg);min-height:112px;padding:6px 6px 8px;cursor:pointer;display:flex;flex-direction:column;gap:3px;min-width:0}
.cal-c:hover{background:var(--surface)}
.cal-c.out{background:var(--surface);opacity:.55}
.cal-c.past .cal-n{color:var(--muted)}
.cal-c.today .cal-n{background:var(--accent);color:var(--accent-ink);border-radius:12px;padding:0 7px}
.cal-c.sel{outline:2px solid var(--accent);outline-offset:-2px}
.cal-n{font-size:13px;font-weight:500;align-self:flex-start}
.cal-p{display:flex;align-items:center;gap:5px;font-size:12px;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cal-p span{overflow:hidden;text-overflow:ellipsis}
.cal-more{font-size:12px;color:var(--muted)}
.cal-list{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:4px 16px}
.cal-dh{font-family:var(--font-display);font-size:20px;margin:14px 0 4px}
.cal-li{display:grid;grid-template-columns:14px 70px 1fr;gap:8px;align-items:baseline;padding:8px 0;border-top:1px solid var(--border);font-size:14px}
.cal-li i{position:relative;top:1px}
.cal-li time{color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums}
.cal-li small{display:block;color:var(--muted);font-size:13px}
.cal-li a{color:var(--ink)}
#cal-day{margin-top:14px}
.cal-note{font-size:13px;color:var(--muted);line-height:1.55;margin-top:14px}
@media (max-width:760px){.cal-c{min-height:64px}.cal-p span{display:none}.cal-p{gap:2px}}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  // step back if the page before this one (in this tab) is ours; otherwise close the tab, or go /
  var here=location.href, back=false, nav=window.navigation;
  if(nav && nav.currentEntry && typeof nav.entries==='function'){
    var i=nav.currentEntry.index, en=nav.entries();
    back=i>0 && !!en[i-1] && en[i-1].url.indexOf(location.origin+'/')===0;
  } else {                                        // no Navigation API: the referrer, checked after the fact
    var r=document.referrer||''; back=history.length>1 && r.indexOf(location.origin+'/')===0 && r!==here;
  }
  function leave(){ try{ if(window.opener && !window.opener.closed) window.opener.focus(); }catch(_){}
    window.close(); setTimeout(function(){ location.href='/'; }, 250); }
  if(back){ history.back(); setTimeout(function(){ if(location.href===here) leave(); }, 450); }
  else leave();
  return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
var KINDS=[['earnings','Your earnings'],['economy','Economy'],['fed','Fed'],['market','Market hours'],['options','Options expiration'],['ipo','IPOs']];
var EV=[], OFF={}, VIEW=(window.innerWidth<700?'list':'month'), MON=null, SEL=null;
try{ OFF=JSON.parse(localStorage.getItem('cal-off')||'{}')||{}; }catch(_){}
function iso(d){ return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2); }
function today(){ return iso(new Date()); }
function shown(){ return EV.filter(function(e){ return !OFF[e.kind]; }); }
function tm(t){ if(!t) return 'All day'; var p=t.split(':'), h=+p[0]; return ((h+11)%12+1)+':'+p[1]+(h<12?' am':' pm'); }
function pretty(s){ var d=new Date(s+'T12:00:00'); return d.toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'}); }
function item(e){ var t=e.ticker&&e.kind==='earnings'?'<a href="/analysis/'+encodeURIComponent(e.ticker)+'">'+esc(e.title)+'</a>':
    (e.url?'<a href="'+esc(e.url)+'">'+esc(e.title)+'</a>':esc(e.title));
  return '<div class="cal-li"><i class="k-'+e.kind+'"></i><time>'+tm(e.time)+'</time><span>'+t+(e.detail?'<small>'+esc(e.detail)+'</small>':'')+'</span></div>'; }
function kinds(){ document.getElementById('cal-kinds').innerHTML=KINDS.map(function(k){
    var n=EV.filter(function(e){ return e.kind===k[0]; }).length;
    return '<button class="cal-k'+(OFF[k[0]]?' off':'')+'" data-k="'+k[0]+'"><i class="k-'+k[0]+'"></i>'+k[1]+' <span class="muted">'+n+'</span></button>'; }).join(''); }
function month(){
  var y=MON.getFullYear(), m=MON.getMonth(), first=new Date(y,m,1), start=new Date(y,m,1-first.getDay()), t=today(), by={};
  shown().forEach(function(e){ (by[e.date]=by[e.date]||[]).push(e); });
  var h='<div class="cal-nav"><button id="prev" aria-label="Previous month">‹</button><h2>'+first.toLocaleDateString(undefined,{month:'long',year:'numeric'})+
    '</h2><button id="today">Today</button><button id="next" aria-label="Next month">›</button></div><div class="cal-grid">'+
    ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(function(d){ return '<div class="cal-dow">'+d+'</div>'; }).join('');
  for(var i=0;i<42;i++){ var d=new Date(start); d.setDate(start.getDate()+i); var k=iso(d), es=by[k]||[];
    if(i===35 && d.getMonth()!==m) break;
    h+='<div class="cal-c'+(d.getMonth()!==m?' out':'')+(k<t?' past':'')+(k===t?' today':'')+(k===SEL?' sel':'')+'" data-d="'+k+'"><span class="cal-n">'+d.getDate()+'</span>'+
      es.slice(0,3).map(function(e){ return '<div class="cal-p" title="'+esc(e.title)+'"><i class="k-'+e.kind+'"></i><span>'+esc(e.ticker&&e.kind==='earnings'?e.ticker+' earnings':e.title)+'</span></div>'; }).join('')+
      (es.length>3?'<div class="cal-more">+'+(es.length-3)+' more</div>':'')+'</div>'; }
  document.getElementById('cal').innerHTML=h+'</div>';
  document.getElementById('prev').onclick=function(){ MON=new Date(y,m-1,1); render(); };
  document.getElementById('next').onclick=function(){ MON=new Date(y,m+1,1); render(); };
  document.getElementById('today').onclick=function(){ MON=new Date(); MON.setDate(1); SEL=today(); render(); };
  day(); }
function day(){ var el=document.getElementById('cal-day'); if(VIEW!=='month'||!SEL){ el.innerHTML=''; return; }
  var es=shown().filter(function(e){ return e.date===SEL; });
  el.innerHTML='<div class="cal-list"><div class="cal-dh">'+pretty(SEL)+'</div>'+(es.map(item).join('')||'<p class="muted small">Nothing on this day.</p>')+'</div>'; }
function list(){ var t=today(), es=shown().filter(function(e){ return e.date>=t; }), h='', last='';
  es.forEach(function(e){ if(e.date!==last){ h+='<div class="cal-dh">'+pretty(e.date)+(e.date===t?' · today':'')+'</div>'; last=e.date; } h+=item(e); });
  document.getElementById('cal').innerHTML='<div class="cal-list">'+(h||'<p class="muted">Nothing coming up.</p>')+'</div>'; day(); }
function render(){ document.querySelectorAll('#cal-view button').forEach(function(b){ b.classList.toggle('on',b.dataset.v===VIEW); });
  document.getElementById('cal').className=''; kinds(); if(VIEW==='month') month(); else list(); }
document.getElementById('cal-view').onclick=function(e){ var b=e.target.closest('button'); if(!b) return; VIEW=b.dataset.v; render(); };
document.getElementById('cal-kinds').onclick=function(e){ var b=e.target.closest('[data-k]'); if(!b) return;
  OFF[b.dataset.k]=!OFF[b.dataset.k]; try{ localStorage.setItem('cal-off',JSON.stringify(OFF)); }catch(_){} render(); };
document.getElementById('cal').addEventListener('click',function(e){ var c=e.target.closest('.cal-c'); if(!c) return;
  SEL=c.dataset.d; document.querySelectorAll('.cal-c.sel').forEach(function(x){ x.classList.remove('sel'); }); c.classList.add('sel'); day();
  document.getElementById('cal-day').scrollIntoView({block:'nearest',behavior:'smooth'}); });
MON=new Date(); MON.setDate(1); SEL=today();
fetch('/api/calendar').then(function(r){return r.json();}).then(function(d){
  if(!d.ok){ document.getElementById('cal').textContent=d.error||'Unavailable.'; return; } EV=d.events||[]; render(); })
  .catch(function(){ document.getElementById('cal').textContent='Calendar unavailable right now.'; });
"""
