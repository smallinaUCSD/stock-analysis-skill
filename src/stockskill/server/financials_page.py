"""Financials page: ten fiscal years of income statement, balance sheet,
cash flow and ratios as filed in 10-Ks (the Bloomberg FA view).
Data from /api/financials/<ticker>; every figure is computed server-side."""

from __future__ import annotations

import html
import json

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def financials_html(initial: str = "") -> str:
    t = html.escape((initial or "AAPL").upper()[:12])
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Financials</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Financials</h1>"
            "<span class=\"sub\" style=\"margin:0\">Ten years of annual reports, side by side</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div class=\"fa-bar\"><input id=\"ft\" value=\"" + t + "\" placeholder=\"Ticker (e.g. AAPL)\" autocomplete=\"off\">"
            "<button class=\"fa-go\" onclick=\"go()\">Show</button>"
            "<span class=\"seg\" id=\"fa-tabs\"><button data-s=\"income\" class=\"on\">Income</button>"
            "<button data-s=\"balance\">Balance sheet</button><button data-s=\"cashflow\">Cash flow</button>"
            "<button data-s=\"ratios\">Ratios</button></span></div>"
            "<h2 id=\"fa-title\" class=\"fa-title\"></h2>"
            "<div id=\"fa-sum\" class=\"fa-sum\"></div>"
            "<div id=\"fa-chart\" class=\"fa-chart\"></div>"
            "<div id=\"fa-table\" class=\"fa-box muted\">Loading…</div>"
            "<p id=\"fa-note\" class=\"fa-note\"></p>"
            "</div><script>var INIT=" + json.dumps(t) + ";\n" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.fa-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0 10px}
.fa-bar input{width:160px;height:38px;padding:0 12px;border-radius:var(--r);border:1px solid var(--border);
  background:var(--surface);color:var(--ink);font:14px var(--font);text-transform:uppercase}
.fa-go{height:38px;padding:0 16px;border-radius:var(--r);border:none;background:var(--accent);color:var(--accent-ink);font:500 14px var(--font);cursor:pointer}
.fa-bar .seg{margin-left:auto;display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.fa-bar .seg button{font:500 13px var(--font);padding:0 14px;height:38px;border:none;background:var(--surface);color:var(--muted);cursor:pointer}
.fa-bar .seg button:hover{color:var(--ink)}
.fa-bar .seg button.on{background:var(--surface-3,var(--band));color:var(--ink)}
.fa-title{font-family:var(--font-display);font-weight:500;font-size:28px;margin:6px 0 8px}
.fa-sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:12px}
.fa-sum:empty{display:none}
.fa-kpi{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:10px 14px}
.fa-kpi .l{font-size:12px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted)}
.fa-kpi .v{font-size:20px;margin-top:2px;font-variant-numeric:tabular-nums}
.fa-kpi .s{font-size:12px;color:var(--muted);margin-top:2px}
.fa-chart{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:10px 12px 6px;margin-bottom:12px}
.fa-chart:empty{display:none}
.fa-chart svg{display:block;width:100%;height:auto}
.fa-legend{display:flex;gap:16px;font-size:12px;color:var(--muted);margin:0 0 4px 4px}
.fa-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.fa-box{border:1px solid var(--border);border-radius:12px;background:var(--surface);overflow-x:auto}
.fa-box.muted{padding:14px;font-size:14px}
.fa-t{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
.fa-t th,.fa-t td{padding:7px 10px;text-align:right;white-space:nowrap;border-top:1px solid var(--border)}
.fa-t thead th{border-top:none;font-weight:500;color:var(--muted);font-size:12px;vertical-align:bottom}
.fa-t thead th small{display:block;font-weight:400;font-size:11px}
.fa-t th:first-child,.fa-t td:first-child{text-align:left;position:sticky;left:0;background:var(--surface);min-width:190px}
.fa-t tbody tr:hover td{background:var(--bg)}
.fa-t td.neg{color:var(--down)}
.fa-t td.na{color:var(--muted)}
.fa-t tr.key td{font-weight:500}
.fa-t td.spark{width:92px;padding:4px 10px}
.fa-note{font-size:13px;color:var(--muted);line-height:1.55;margin:12px 0 0}
.fa-note a{color:var(--link)}
@media (max-width:640px){.fa-bar .seg{margin-left:0;width:100%}.fa-bar .seg button{flex:1;padding:0 6px;font-size:12px}
  .fa-sum{grid-template-columns:1fr 1fr;gap:8px}.fa-kpi{padding:8px 10px}.fa-kpi .v{font-size:17px}.fa-kpi .l{font-size:10px;letter-spacing:.8px}
  .fa-t th:first-child,.fa-t td:first-child{min-width:140px}}
"""

_JS = r"""
function goBack(e){ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){ try{window.opener.focus();}catch(_){}; window.close(); }
  else location.href='/'; return false; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
var D=null, SEC='income';
var KEY={revenue:1,gross_profit:1,op_income:1,net_income:1,eps:1,total_assets:1,equity:1,ocf:1,fcf:1,total_liabilities:1};
function fmt(v,kind){
  if(v==null||!isFinite(v)) return '—';
  if(kind==='pct') return (v*100).toFixed(1)+'%';
  if(kind==='x') return v.toFixed(2)+'x';
  if(kind==='eps') return (v<0?'-':'')+'$'+Math.abs(v).toFixed(2);
  var a=Math.abs(v), s=v<0?'-':'';
  if(kind==='sh') return a>=1e9?(a/1e9).toFixed(2)+'B':(a/1e6).toFixed(0)+'M';
  if(a>=1e12) return s+'$'+(a/1e12).toFixed(2)+'T';
  if(a>=1e9) return s+'$'+(a/1e9).toFixed(a>=1e11?0:1)+'B';
  if(a>=1e6) return s+'$'+(a/1e6).toFixed(0)+'M';
  return s+'$'+a.toFixed(0);
}
function fyLabel(end){ var d=new Date(end+'T00:00:00'); var y=d.getFullYear(), m=d.getMonth();
  // a fiscal year ending in early January belongs to the prior calendar year's label
  return 'FY'+(m===0&&d.getDate()<8?y-1:y); }
function mon(end){ return new Date(end+'T00:00:00').toLocaleString('en-US',{month:'short',year:'numeric'}); }
function spark(vals){
  var p=vals.map(function(v,i){return [i,v];}).filter(function(x){return x[1]!=null&&isFinite(x[1]);});
  if(p.length<2) return '';
  var lo=Math.min.apply(null,p.map(function(x){return x[1];})), hi=Math.max.apply(null,p.map(function(x){return x[1];}));
  var w=72,h=20,n=vals.length-1||1, rng=(hi-lo)||1;
  var pts=p.map(function(x){ return (x[0]/n*w).toFixed(1)+','+(h-2-(x[1]-lo)/rng*(h-4)).toFixed(1); }).join(' ');
  // neutral colour: a rising line is not always good (tax rate, share count)
  return '<svg width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'"><polyline points="'+pts+'" fill="none" stroke="var(--accent)" stroke-width="1.5"/></svg>';
}
function table(){
  var ys=D.years, rows=D.layout[SEC];
  var head='<tr><th>'+({income:'Income statement',balance:'Balance sheet',cashflow:'Cash flow',ratios:'Ratios'}[SEC])+'</th>'+
    ys.map(function(y){return '<th>'+fyLabel(y.end)+'<small>'+mon(y.end)+'</small></th>';}).join('')+'<th>Trend</th></tr>';
  var body=rows.filter(function(r){ return ys.some(function(y){return y[r[0]]!=null;}); }).map(function(r){
    var vals=ys.map(function(y){return y[r[0]];});
    return '<tr'+(KEY[r[0]]?' class="key"':'')+'><td>'+esc(r[1])+'</td>'+vals.map(function(v){
      return '<td class="'+(v==null?'na':(v<0?'neg':''))+'">'+fmt(v,r[2])+'</td>'; }).join('')+
      '<td class="spark">'+spark(vals)+'</td></tr>';
  }).join('');
  var box=document.getElementById('fa-table'); box.className='fa-box';
  box.innerHTML='<table class="fa-t"><thead>'+head+'</thead><tbody>'+body+'</tbody></table>';
  box.scrollLeft=box.scrollWidth;
}
function chart(){
  var ys=D.years, el=document.getElementById('fa-chart');
  var series=[['revenue','Revenue','var(--axis)'],['net_income','Net income','var(--accent)'],['fcf','Free cash flow','var(--up)']]
    .filter(function(se){ return ys.some(function(y){ return y[se[0]]!=null; }); });
  var all=[]; ys.forEach(function(y){ series.forEach(function(s){ if(y[s[0]]!=null) all.push(y[s[0]]); }); });
  if(!all.length){ el.innerHTML=''; return; }
  var hi=Math.max(0,Math.max.apply(null,all)), lo=Math.min(0,Math.min.apply(null,all));
  var W=900,H=190,pl=56,pr=8,pt=8,pb=24, cw=(W-pl-pr)/ys.length, ns=series.length, bw=Math.min(18,(cw-10)/ns);
  var sy=function(v){ return pt+(hi-v)/((hi-lo)||1)*(H-pt-pb); };
  var s='';
  [0,0.25,0.5,0.75,1].forEach(function(f){ var v=lo+(hi-lo)*f, y=sy(v);
    s+='<line x1="'+pl+'" x2="'+(W-pr)+'" y1="'+y.toFixed(1)+'" y2="'+y.toFixed(1)+'" stroke="var(--border)" stroke-width="1"/>'+
       '<text x="'+(pl-6)+'" y="'+(y+4).toFixed(1)+'" text-anchor="end" font-size="11" fill="var(--muted)">'+fmt(v,'usd')+'</text>'; });
  ys.forEach(function(y,i){ var x0=pl+i*cw+(cw-bw*ns-(ns-1)*2)/2;
    series.forEach(function(se,j){ var v=y[se[0]]; if(v==null) return;
      var a=sy(Math.max(v,0)), b=sy(Math.min(v,0));
      s+='<rect x="'+(x0+j*(bw+2)).toFixed(1)+'" y="'+a.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+Math.max(1,b-a).toFixed(1)+'" rx="2" fill="'+se[2]+'"><title>'+fyLabel(y.end)+' '+se[1]+': '+fmt(v,'usd')+'</title></rect>'; });
    s+='<text x="'+(pl+i*cw+cw/2).toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle" font-size="11" fill="var(--muted)">'+fyLabel(y.end)+'</text>'; });
  el.innerHTML='<div class="fa-legend">'+series.map(function(se){return '<span><i style="background:'+se[2]+'"></i>'+se[1]+'</span>';}).join('')+'</div>'+
    '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet">'+s+'</svg>';
}
function summary(){
  var ys=D.years, last=ys[ys.length-1], c=D.cagr||{};
  function g(k){ var o=c[k]||{}, parts=[]; [3,5,10].forEach(function(n){ if(o[n]!=null) parts.push((o[n]*100).toFixed(Math.abs(o[n])<0.1?1:0)+'% over '+n+'y'); });
    return parts.length?'Yearly growth '+parts.join(', '):'Yearly growth: n/a'; }
  var k=[['Revenue',fmt(last.revenue,'usd'),g('revenue')],
         ['Net income',fmt(last.net_income,'usd'),last.net_margin!=null?'Net margin '+(last.net_margin*100).toFixed(1)+'%':''],
         ['Free cash flow',fmt(last.fcf,'usd'),g('fcf')],
         ['EPS (diluted)',fmt(last.eps,'eps'),g('eps')]];
  if(last.roic!=null) k.push(['ROIC',(last.roic*100).toFixed(1)+'%','Return on invested capital']);
  document.getElementById('fa-sum').innerHTML=k.filter(function(x){ return x[1]!=='—'; }).map(function(x){ return '<div class="fa-kpi"><div class="l">'+x[0]+' · '+fyLabel(last.end)+'</div><div class="v">'+x[1]+'</div><div class="s">'+esc(x[2])+'</div></div>'; }).join('');
}
function note(){
  var sp=(D.splits||[]).filter(function(s){ return s.filed>=D.years[0].end; });
  var t='As filed in the company\'s 10-K annual reports (SEC XBRL); a later restatement replaces the original figure. '+
    'Ratios are computed here from those figures. A dash means the company did not report that line under a standard tag that year (banks, for example, have no gross profit). ';
  if(sp.length) t+='EPS and share counts are restated for stock splits ('+sp.map(function(s){ var r=s.ratio>=1?s.ratio+'-for-1':'1-for-'+Math.round(1/s.ratio)+' reverse'; return r+' before '+s.filed.slice(0,7); }).join(', ')+'). ';
  t+='<a href="'+esc(D.source)+'" target="_blank" rel="noopener">Filings on SEC EDGAR</a>.';
  document.getElementById('fa-note').innerHTML=t;
}
function go(){ var t=(document.getElementById('ft').value||'').trim().toUpperCase(); if(t) load(t); }
document.getElementById('ft').addEventListener('keydown',function(e){ if(e.key==='Enter') go(); });
document.querySelectorAll('#fa-tabs button').forEach(function(b){ b.addEventListener('click',function(){
  document.querySelectorAll('#fa-tabs button').forEach(function(x){x.classList.toggle('on',x===b);});
  SEC=b.getAttribute('data-s'); try{ localStorage.setItem('fa-sec',SEC); }catch(_){}; if(D) table(); }); });
try{ var s0=localStorage.getItem('fa-sec'); if(s0){ var b0=document.querySelector('#fa-tabs button[data-s="'+s0+'"]'); if(b0){ SEC=s0; document.querySelectorAll('#fa-tabs button').forEach(function(x){x.classList.toggle('on',x===b0);}); } } }catch(_){}
function load(t){
  document.getElementById('ft').value=t;
  try{ history.replaceState(null,'','/financials?t='+encodeURIComponent(t)); }catch(_){}
  var box=document.getElementById('fa-table'); box.className='fa-box muted'; box.textContent='Loading '+t+'…';
  ['fa-sum','fa-chart','fa-note'].forEach(function(id){ document.getElementById(id).innerHTML=''; });
  document.getElementById('fa-title').textContent='';
  fetch('/api/financials/'+encodeURIComponent(t)).then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ box.textContent=d.error||'Not found.'; return; }
    D=d; document.getElementById('fa-title').textContent=d.name||d.ticker;
    summary(); chart(); table(); note();
  }).catch(function(){ box.textContent='Could not load financials.'; });
}
load(INIT);
"""
