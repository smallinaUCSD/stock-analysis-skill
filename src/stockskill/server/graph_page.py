"""Knowledge-graph page: a company's suppliers, customers, investments,
competitors and filing mentions. Click any company to recenter on it.
Data from /api/graph/<ticker>."""

from __future__ import annotations

import html
import json

from ..dashboard.render import _CSS, _THEME_BOOT, icon
from .graph_js import GRAPH_CSS, GRAPH_JS


def graph_html(initial: str = "") -> str:
    t = html.escape((initial or "NVDA").upper()[:12])
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Connections</title>" + _THEME_BOOT + "<style>" + _CSS + GRAPH_CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Connections</h1>"
            "<span class=\"sub\" style=\"margin:0\">Who supplies it, who buys from it, what it owns</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div class=\"kg-bar\"><input id=\"kt\" value=\"" + t + "\" placeholder=\"Ticker (e.g. NVDA)\" autocomplete=\"off\">"
            "<button class=\"kg-go\" onclick=\"go()\">Show</button><span id=\"kg-crumbs\" class=\"muted kg-crumbs\"></span></div>"
            "<h2 id=\"kg-title\" class=\"kg-title\"></h2>"
            "<div id=\"kg\" class=\"kg-box muted\">Loading…</div>"
            "<div id=\"kg-lists\" class=\"kg-lists\"></div>"
            "<p class=\"kg-note\">Sources are labeled on every link. Suppliers and customers come from a curated list of "
            "well-documented relationships (the company's own 10-K, public announcements or wide reporting), not an exhaustive "
            "supply chain. Customers also include every customer the company's latest 10-K reports at 10% or more of revenue (usually unnamed there). Investments are from the company's own SEC 13F filing (listed stakes it held last quarter). "
            "Competitors share its SEC industry code on this watchlist. A ring around a company means its latest 10-K also "
            "names this one. Click any company to recenter on it.</p>"
            "</div><script>var INIT=" + json.dumps(t) + ";\n" + GRAPH_JS + _JS + "</script></body></html>")


_EXTRA_CSS = """
.kg-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0 10px}
.kg-bar input{width:160px;height:38px;padding:0 12px;border-radius:var(--r);border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font:14px var(--font);text-transform:uppercase}
.kg-go{height:38px;padding:0 16px;border-radius:var(--r);border:none;background:var(--accent);color:var(--accent-ink);font:500 14px var(--font);cursor:pointer}
.kg-crumbs{font-size:13px} .kg-crumbs a{color:var(--link);cursor:pointer;text-decoration:none} .kg-crumbs a:hover{text-decoration:underline}
.kg-title{font-family:var(--font-display);font-weight:500;font-size:28px;margin:6px 0 8px}
.kg-box{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:8px}
.kg-box.muted{padding:14px;font-size:14px}
.kg-lists{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:14px}
.kg-list{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:10px 14px}
.kg-list h3{font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;margin:0 0 6px}
.kg-item{padding:6px 0;border-top:1px solid var(--border);font-size:13px;line-height:1.45}
.kg-item:first-of-type{border-top:none}
.kg-item b{font-weight:500} .kg-item .m{color:var(--muted)}
.kg-item a{color:var(--link);text-decoration:none;cursor:pointer} .kg-item a:hover{text-decoration:underline}
.kg-note{font-size:13px;color:var(--muted);line-height:1.55;margin:12px 0 0}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
var TRAIL=[];
function go(){ var t=(document.getElementById('kt').value||'').trim().toUpperCase(); if(t) load(t); }
document.getElementById('kt').addEventListener('keydown',function(e){ if(e.key==='Enter') go(); });
function load(t, back){
  if(!back){ if(TRAIL[TRAIL.length-1]!==t) TRAIL.push(t); } else { TRAIL=TRAIL.slice(0,TRAIL.indexOf(t)+1); }
  document.getElementById('kt').value=t;
  try{ history.replaceState(null,'','/graph?t='+encodeURIComponent(t)); }catch(_){}
  document.getElementById('kg-crumbs').innerHTML=TRAIL.length>1?'Path: '+TRAIL.map(function(x,i){ return i===TRAIL.length-1?gEsc(x):'<a onclick="load(\''+gEsc(x)+'\',true)">'+gEsc(x)+'</a>'; }).join(' &rsaquo; '):'';
  var box=document.getElementById('kg'); box.className='kg-box muted'; box.textContent='Loading '+t+'…';
  fetch('/api/graph/'+encodeURIComponent(t)).then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ box.textContent=d.error||'Not found.'; return; }
    document.getElementById('kg-title').textContent=(d.name||d.ticker)+(d.sector?' · '+d.sector:'');
    var total=['suppliers','customers','investments','competitors'].reduce(function(a,g){return a+(d[g]||[]).length;},0);
    box.className='kg-box';
    if(!total){ box.className='kg-box muted'; box.textContent='No documented connections for '+t+' yet.'; }
    else drawGraph(box, d, {onNode:function(x){ load(x); }});
    renderLists(d);
    if(d.customer_note){ document.getElementById('kg-lists').insertAdjacentHTML('afterbegin','<div class="kg-list"><h3>Customers</h3><div class="kg-item">'+gEsc(d.customer_note)+'</div></div>'); }
  }).catch(function(){ box.textContent='Could not load connections.'; });
}
function item(it){ var t=it.ticker?'<a onclick="load(\''+gEsc(it.ticker)+'\')"><b>'+gEsc(it.ticker)+'</b></a> ':'<b>'+gEsc(it.name)+'</b> ';
  return '<div class="kg-item">'+t+(it.ticker&&it.name&&it.name!==it.ticker?'<span class="m">'+gEsc(it.name)+'</span>':'')+'<br>'+gEsc(it.what||'')+
    ' <span class="m">('+(it.url?'<a href="'+gEsc(it.url)+'" target="_blank" rel="noopener">'+gEsc(it.basis)+'</a>':gEsc(it.basis||''))+')</span></div>'; }
function renderLists(d){
  var groups=[['suppliers','Suppliers'],['customers','Customers'],['investments','Invests in'],['competitors','Competitors'],['mentions','Names it in their annual report']];
  document.getElementById('kg-lists').innerHTML=groups.filter(function(g){return (d[g[0]]||[]).length;}).map(function(g){
    return '<div class="kg-list"><h3>'+g[1]+'</h3>'+d[g[0]].map(item).join('')+'</div>'; }).join('');
}
load(INIT);
"""
