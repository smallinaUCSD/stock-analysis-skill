"""Earnings page: who on the watchlist reports in the next five weeks, and for
one company its report history - EPS vs estimate, and how the stock moved the
session after each report. Data from /api/earnings/*."""

from __future__ import annotations

import html
import json

from ..dashboard.render import _CSS, _THEME_BOOT, icon
from .embed import EMBED_CSS, EMBED_JS


def earnings_html(initial: str = "") -> str:
    t = html.escape((initial or "").upper()[:12])
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Earnings</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS + EMBED_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Earnings</h1>"
            "<span class=\"sub\" style=\"margin:0\">When they report, and how the stock usually reacts</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div class=\"er-bar\"><span class=\"seg\" id=\"er-tabs\"><button data-v=\"cal\" class=\"on\">Upcoming</button>"
            "<button data-v=\"co\">Company</button></span>"
            "<input id=\"et\" value=\"" + t + "\" placeholder=\"Ticker (e.g. NVDA)\" autocomplete=\"off\">"
            "<button class=\"er-go\" onclick=\"go()\">Show</button></div>"
            "<div id=\"er-cal\"><div class=\"er-box muted\">Loading the calendar…</div></div>"
            "<div id=\"er-co\" hidden></div>"
            "<p class=\"er-note\">Report dates and times are from each company's SEC 8-K earnings filings; the move is the "
            "stock's change over the first full session after the release (after-close reports react the next day). "
            "EPS estimates, surprises and analyst ratings are from Finnhub (free tier: the last four quarters). "
            "A typical move is the average size of past moves in either direction, not a forecast.</p>"
            "</div><script>" + EMBED_JS + "var INIT=" + json.dumps(t) + ";\n" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.er-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0 14px}
.er-bar .seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-right:auto}
.er-bar .seg button{font:500 13px var(--font);padding:0 14px;height:38px;border:none;background:var(--surface);color:var(--muted);cursor:pointer}
.er-bar .seg button:hover{color:var(--ink)}
.er-bar .seg button.on{background:var(--surface-3,var(--band));color:var(--ink)}
.er-bar input{width:160px;height:38px;padding:0 12px;border-radius:var(--r);border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font:14px var(--font);text-transform:uppercase}
.er-go{height:38px;padding:0 16px;border-radius:var(--r);border:none;background:var(--accent);color:var(--accent-ink);font:500 14px var(--font);cursor:pointer}
.er-box{border:1px solid var(--border);border-radius:12px;background:var(--surface);overflow-x:auto}
.er-box.muted{padding:14px;font-size:14px;color:var(--muted)}
.er-t tr.er-dh td{text-align:left;font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:1.4px;
  color:var(--muted);background:var(--bg);padding:12px 12px 6px}
.er-t tbody tr.er-dh:hover td{background:var(--bg)}
.er-t{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
.er-t th,.er-t td{padding:8px 12px;text-align:right;white-space:nowrap;border-top:1px solid var(--border)}
.er-t thead th{border-top:none;font-weight:500;color:var(--muted);font-size:12px}
.er-t th:first-child,.er-t td:first-child,.er-t th:nth-child(2),.er-t td:nth-child(2){text-align:left}
.er-t tbody tr:hover td{background:var(--bg)}
.er-t a{color:var(--link);text-decoration:none;cursor:pointer} .er-t a:hover{text-decoration:underline}
.er-t .m{color:var(--muted)} .er-t .up{color:var(--up)} .er-t .dn{color:var(--down)}
.er-t td.nm{max-width:240px;overflow:hidden;text-overflow:ellipsis;color:var(--muted)}
.er-title{font-family:var(--font-display);font-weight:500;font-size:28px;margin:2px 0 10px}
.er-sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-bottom:12px}
.er-kpi{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:10px 14px}
.er-kpi .l{font-size:12px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted)}
.er-kpi .v{font-size:20px;margin-top:2px;font-variant-numeric:tabular-nums}
.er-kpi .s{font-size:12px;color:var(--muted);margin-top:2px}
.er-grid{display:grid;grid-template-columns:3fr 2fr;gap:12px;margin-bottom:12px}
.er-card{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:10px 14px}
.er-card h3{font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);margin:0 0 6px}
.er-card svg{display:block;width:100%;height:auto}
.er-legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--muted);margin-top:6px}
.er-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.er-note{font-size:13px;color:var(--muted);line-height:1.55;margin:12px 0 0}
@media (max-width:760px){.er-grid{grid-template-columns:1fr}.er-bar .seg{width:100%;margin-right:0}.er-bar .seg button{flex:1}
  .er-bar input{flex:1}.er-sum{grid-template-columns:1fr 1fr;gap:8px}.er-kpi .v{font-size:17px}}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  // came here inside this tab: step back; opened as its own tab: close it
  var r=document.referrer||'';
  if(history.length>1 && r.indexOf(location.origin+'/')===0 && r!==location.href){ history.back(); return false; }
  try{ if(window.opener && !window.opener.closed) window.opener.focus(); }catch(_){}
  window.close();
  setTimeout(function(){ location.href='/'; }, 200);          // the browser refused to close it
  return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function pct(v,d){ return v==null?'—':(v>0?'+':'')+(v*100).toFixed(d==null?1:d)+'%'; }
function usd(v){ if(v==null) return '—'; var a=Math.abs(v), s=v<0?'-':'';
  return a>=1e9?s+'$'+(a/1e9).toFixed(a>=1e11?0:1)+'B':a>=1e6?s+'$'+(a/1e6).toFixed(0)+'M':s+'$'+a.toFixed(2); }
function eps(v){ return v==null?'—':(v<0?'-':'')+'$'+Math.abs(v).toFixed(2); }
var WHEN={pre:'Before open',post:'After close',during:'During market'};
function when(t,usual){ return t?WHEN[t]:(usual?'<span class="m">Usually '+WHEN[usual].toLowerCase()+'</span>':'<span class="m">Time not set</span>'); }
function dayLabel(s){ var d=new Date(s+'T12:00:00'), t=new Date(); t.setHours(12,0,0,0);
  var n=Math.round((d-t)/864e5), w=d.toLocaleDateString('en-US',{weekday:'long',month:'short',day:'numeric'});
  return w+(n===0?' · today':n===1?' · tomorrow':' · in '+n+' days'); }
var VIEW='cal', CAL=null;
function setView(v){ VIEW=v; document.querySelectorAll('#er-tabs button').forEach(function(b){ b.classList.toggle('on',b.getAttribute('data-v')===v); });
  document.getElementById('er-cal').hidden=v!=='cal'; document.getElementById('er-co').hidden=v!=='co'; }
document.querySelectorAll('#er-tabs button').forEach(function(b){ b.addEventListener('click',function(){
  var v=b.getAttribute('data-v'); setView(v);
  if(v==='co' && !document.getElementById('er-co').innerHTML){ var t=document.getElementById('et').value.trim(); if(t) company(t.toUpperCase()); else document.getElementById('er-co').innerHTML='<div class="er-box muted">Type a ticker above.</div>'; }
  if(v==='cal') try{ history.replaceState(null,'','/earnings'); }catch(_){}; }); });
function go(){ var t=(document.getElementById('et').value||'').trim().toUpperCase(); if(t){ setView('co'); company(t); } }
document.getElementById('et').addEventListener('keydown',function(e){ if(e.key==='Enter') go(); });

function loadCal(){
  fetch('/api/earnings/calendar').then(function(r){return r.json();}).then(function(d){
    var el=document.getElementById('er-cal');
    if(!d.ok){ el.innerHTML='<div class="er-box muted">'+esc(d.error||'Unavailable.')+'</div>'; return; }
    if(!d.rows.length){ el.innerHTML='<div class="er-box muted">No watchlist company reports in the next five weeks.</div>'; return; }
    var by={}; d.rows.forEach(function(r){ (by[r.date]=by[r.date]||[]).push(r); });
    el.innerHTML='<div class="er-box"><table class="er-t"><thead><tr>'+
      '<th>Ticker</th><th>Company</th><th>When</th><th>EPS estimate</th><th>Revenue estimate</th><th>Typical move</th><th>Rose after</th></tr></thead><tbody>'+
      Object.keys(by).sort().map(function(day){
        var rows=by[day].sort(function(a,b){ return (b.rev_est||0)-(a.rev_est||0); });
        return '<tr class="er-dh"><td colspan="7">'+esc(dayLabel(day))+'</td></tr>'+
          rows.map(function(r){ return '<tr><td><a onclick="setView(\'co\');company(\''+esc(r.ticker)+'\')"><b>'+esc(r.ticker)+'</b></a></td>'+
            '<td class="nm">'+esc(r.name)+'</td><td>'+when(r.timing,r.usual_timing)+'</td><td>'+eps(r.eps_est)+'</td><td>'+usd(r.rev_est)+'</td>'+
            '<td>'+(r.avg_move!=null?'±'+(r.avg_move*100).toFixed(1)+'%':'—')+'</td>'+
            '<td class="m">'+(r.n?r.up+' of '+r.n:'—')+'</td></tr>'; }).join('');
      }).join('')+'</tbody></table></div>';
  }).catch(function(){ document.getElementById('er-cal').innerHTML='<div class="er-box muted">Could not load the calendar.</div>'; });
}

function moveChart(h){
  var rows=h.filter(function(x){return x.move!=null;}).slice().reverse();
  if(!rows.length) return '<div class="m" style="font-size:13px">No price history around these reports.</div>';
  var mx=Math.max.apply(null,rows.map(function(x){return Math.max(Math.abs(x.move),Math.abs(x.market||0));}))||0.01;
  var W=560,H=200,pl=40,pr=6,pt=8,pb=26, cw=(W-pl-pr)/rows.length, bw=Math.min(26,cw*0.6), z=pt+(H-pt-pb)/2;
  var sy=function(v){ return z-v/mx*((H-pt-pb)/2); };
  var s='';
  [mx,mx/2,0,-mx/2,-mx].forEach(function(v){ var y=sy(v);
    s+='<line x1="'+pl+'" x2="'+(W-pr)+'" y1="'+y.toFixed(1)+'" y2="'+y.toFixed(1)+'" stroke="var(--border)" stroke-width="'+(v===0?1.4:1)+'"/>'+
       '<text x="'+(pl-5)+'" y="'+(y+4).toFixed(1)+'" text-anchor="end" font-size="11" fill="var(--muted)">'+(v>0?'+':'')+(v*100).toFixed(0)+'%</text>'; });
  rows.forEach(function(x,i){ var cx=pl+i*cw+cw/2, a=sy(Math.max(x.move,0)), b=sy(Math.min(x.move,0));
    s+='<rect x="'+(cx-bw/2).toFixed(1)+'" y="'+a.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+Math.max(1,b-a).toFixed(1)+'" rx="2" fill="'+(x.move>=0?'var(--up)':'var(--down)')+'"><title>'+esc(x.date)+': stock '+pct(x.move)+(x.market!=null?', market '+pct(x.market):'')+'</title></rect>';
    if(x.market!=null) s+='<circle cx="'+cx.toFixed(1)+'" cy="'+sy(x.market).toFixed(1)+'" r="3" fill="var(--surface)" stroke="var(--ink)" stroke-width="1.2"/>';
    s+='<text x="'+cx.toFixed(1)+'" y="'+(H-8)+'" text-anchor="middle" font-size="10" fill="var(--muted)">'+new Date(x.date+'T12:00:00').toLocaleDateString('en-US',{month:'short',year:'2-digit'})+'</text>'; });
  return '<svg viewBox="0 0 '+W+' '+H+'">'+s+'</svg><div class="er-legend"><span><i style="background:var(--up)"></i>Stock up</span><span><i style="background:var(--down)"></i>Stock down</span><span><i style="background:var(--surface);border:1.2px solid var(--ink);border-radius:50%"></i>S&amp;P 500 same session</span></div>';
}
var RC=[['strong_buy','Strong buy','var(--up)'],['buy','Buy','color-mix(in srgb,var(--up) 55%,var(--surface))'],['hold','Hold','var(--axis)'],
        ['sell','Sell','color-mix(in srgb,var(--down) 55%,var(--surface))'],['strong_sell','Strong sell','var(--down)']];
function ratings(rs){
  if(!rs||!rs.length) return '<div class="m" style="font-size:13px">No analyst ratings.</div>';
  var W=360,rh=22,gap=8,pl=58,H=rs.length*(rh+gap), s='';
  rs.forEach(function(r,i){ var tot=RC.reduce(function(a,c){return a+(r[c[0]]||0);},0)||1, x=pl, y=i*(rh+gap);
    s+='<text x="'+(pl-8)+'" y="'+(y+rh/2+4)+'" text-anchor="end" font-size="11" fill="var(--muted)">'+new Date(r.period+'T12:00:00').toLocaleDateString('en-US',{month:'short',year:'2-digit'})+'</text>';
    RC.forEach(function(c){ var n=r[c[0]]||0; if(!n) return; var w=n/tot*(W-pl);
      s+='<rect x="'+x.toFixed(1)+'" y="'+y+'" width="'+w.toFixed(1)+'" height="'+rh+'" fill="'+c[2]+'"><title>'+c[1]+': '+n+'</title></rect>';
      if(w>18) s+='<text x="'+(x+w/2).toFixed(1)+'" y="'+(y+rh/2+4)+'" text-anchor="middle" font-size="11" fill="var(--ink)">'+n+'</text>';
      x+=w; }); });
  return '<svg viewBox="0 0 '+W+' '+H+'">'+s+'</svg><div class="er-legend">'+RC.map(function(c){return '<span><i style="background:'+c[2]+'"></i>'+c[1]+'</span>';}).join('')+'</div>';
}
function company(t){
  document.getElementById('et').value=t;
  try{ history.replaceState(null,'','/earnings?t='+encodeURIComponent(t)); }catch(_){}
  var el=document.getElementById('er-co'); el.innerHTML='<div class="er-box muted">Loading '+esc(t)+'…</div>';
  fetch('/api/earnings/'+encodeURIComponent(t)).then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ el.innerHTML='<div class="er-box muted">'+esc(d.error||'Not found.')+'</div>'; return; }
    var st=d.stats||{}, nx=d.next, k=[];
    if(nx){ var dd=Math.round((new Date(nx.date+'T12:00:00')-new Date())/864e5);
      k.push(['Next report',new Date(nx.date+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}),
        (nx.timing?WHEN[nx.timing]:(d.usual_timing?'Usually '+WHEN[d.usual_timing].toLowerCase():'Time not set'))+(dd>=0?' · in '+dd+' days':'')]);
      if(nx.eps_est!=null) k.push(['EPS estimate',eps(nx.eps_est),(nx.quarter?'Q'+nx.quarter+' FY'+nx.year:'')+(nx.rev_est?' · revenue '+usd(nx.rev_est):'')]); }
    if(st.avg_abs_move!=null) k.push(['Typical move','±'+(st.avg_abs_move*100).toFixed(1)+'%','Average over the last '+st.n+' reports; rose after '+st.up+' of '+st.n]);
    if(st.beat_n) k.push(['Beat estimates',st.beats+' of '+st.beat_n,'EPS above consensus, last '+st.beat_n+' quarters']);
    if(st.max_move!=null) k.push(['Biggest move',pct(st.max_move),'Largest single-session reaction shown']);
    var rows=d.history.map(function(x){ var cls=x.move==null?'':(x.move>=0?'up':'dn');
      var sc=x.eps_surprise==null?'':(x.eps_surprise>=0?'up':'dn');
      return '<tr><td>'+esc(new Date(x.date+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}))+'</td>'+
        '<td class="m">'+esc(x.fq||'')+'</td><td>'+(WHEN[x.timing]||'')+'</td><td>'+eps(x.eps_est)+'</td><td>'+eps(x.eps_act)+'</td>'+
        '<td class="'+sc+'">'+(x.eps_surprise==null?'—':(x.eps_surprise>0?'+':'')+x.eps_surprise.toFixed(1)+'%')+'</td>'+
        '<td class="'+cls+'"><b>'+pct(x.move)+'</b></td><td class="m">'+pct(x.market)+'</td>'+
        '<td>'+(x.url?'<a href="'+esc(x.url)+'" target="_blank" rel="noopener">8-K</a>':'')+'</td></tr>'; }).join('');
    el.innerHTML='<h2 class="er-title">'+esc(d.name)+' <span class="m" style="font-size:18px">'+esc(d.ticker)+'</span></h2>'+
      '<div class="er-sum">'+k.map(function(x){ return '<div class="er-kpi"><div class="l">'+x[0]+'</div><div class="v">'+x[1]+'</div><div class="s">'+esc(x[2])+'</div></div>'; }).join('')+'</div>'+
      '<div class="er-grid"><div class="er-card"><h3>Move after each report</h3>'+moveChart(d.history)+'</div>'+
      '<div class="er-card"><h3>Analyst ratings by month</h3>'+ratings(d.ratings)+'</div></div>'+
      (rows?'<div class="er-box"><table class="er-t"><thead><tr><th>Reported</th><th>Quarter</th><th>When</th><th>EPS estimate</th><th>EPS actual</th><th>Surprise</th><th>Stock move</th><th>S&amp;P 500</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div>':'');
  }).catch(function(){ el.innerHTML='<div class="er-box muted">Could not load earnings.</div>'; });
}
if(!document.documentElement.classList.contains('embed')) loadCal();   // embedded: just this company
if(INIT){ setView('co'); company(INIT); }
"""
