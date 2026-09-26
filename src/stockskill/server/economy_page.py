"""Economy page: the release calendar (CPI, jobs, GDP, the Fed...) with each
indicator's latest reading, and the Treasury yield curve with its spreads.
Data from /api/economy."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def economy_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Economy</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Economy</h1>"
            "<span class=\"sub\" style=\"margin:0\">Interest rates and the data that moves them</span>"
            "<button class=\"page-x\" onclick=\"return goBack(event)\" title=\"Close\" aria-label=\"Close\">"
            + icon("x", 17) + "</button></header>"
            "<div id=\"ec-rates\" class=\"ec-kpis\"></div>"
            "<div class=\"ec-grid\"><div class=\"ec-card\"><h3>Treasury yield curve</h3><div id=\"ec-curve\" class=\"muted\">Loading…</div></div>"
            "<div class=\"ec-card\"><h3>Long minus short rates</h3><div id=\"ec-spread\"></div></div></div>"
            "<div class=\"ec-head\"><h2>Release calendar</h2><span class=\"seg\" id=\"ec-imp\">"
            "<button data-i=\"2\" class=\"on\">Market-moving</button><button data-i=\"1\">All releases</button></span></div>"
            "<div id=\"ec-cal\" class=\"ec-box muted\">Loading…</div>"
            "<p class=\"ec-note\">Release dates and times (Eastern) are from the Bureau of Labor Statistics and Bureau of "
            "Economic Analysis calendars, the Federal Reserve's meeting schedule and the Labor Department's weekly claims "
            "release. Readings are the latest published values (via FRED), shown once per indicator; consensus forecasts "
            "aren't free, so none are shown. Yields are the Treasury's daily par yield curve. When long rates sit below "
            "short rates (a negative spread) the curve is inverted, which has often come before recessions, though with "
            "long and uneven lags.</p>"
            "</div><script>" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.ec-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:4px 0 12px}
.ec-kpi{border:1px solid var(--border);border-radius:10px;background:var(--surface);padding:10px 14px}
.ec-kpi .l{font-size:12px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted)}
.ec-kpi .v{font-size:22px;margin-top:2px;font-variant-numeric:tabular-nums}
.ec-kpi .s{font-size:12px;color:var(--muted);margin-top:2px;font-variant-numeric:tabular-nums}
.ec-kpi .s b{font-weight:500} .up{color:var(--up)} .dn{color:var(--down)}
.ec-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px}
.ec-card{border:1px solid var(--border);border-radius:12px;background:var(--surface);padding:10px 14px}
.ec-card h3{font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);margin:0 0 6px}
.ec-card svg{display:block;width:100%;height:auto}
.ec-legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--muted);margin-top:4px}
.ec-legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:3px}
.ec-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 8px}
.ec-head h2{font-family:var(--font-display);font-weight:500;font-size:24px;margin:0;flex:1}
.ec-head .seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden}
.ec-head .seg button{font:500 13px var(--font);padding:0 14px;height:34px;border:none;background:var(--surface);color:var(--muted);cursor:pointer}
.ec-head .seg button:hover{color:var(--ink)} .ec-head .seg button.on{background:var(--surface-3,var(--band));color:var(--ink)}
.ec-box{border:1px solid var(--border);border-radius:12px;background:var(--surface);overflow-x:auto}
.ec-box.muted{padding:14px;font-size:14px;color:var(--muted)}
.ec-t{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
.ec-t th,.ec-t td{padding:8px 12px;text-align:left;white-space:nowrap;border-top:1px solid var(--border)}
.ec-t thead th{border-top:none;font-weight:500;color:var(--muted);font-size:12px}
.ec-t tr.dh td{font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:1.4px;color:var(--muted);background:var(--bg);padding:12px 12px 6px}
.ec-t tr.dh.today td{color:var(--accent)}
.ec-t tr.past td:not(.x){opacity:.6}
.ec-t td.imp{width:40px} .ec-t td.nm{white-space:normal;min-width:180px}
.ec-t td.nm small{display:block;color:var(--muted);font-size:12px}
.ec-t .m{color:var(--muted)}
.dots{display:inline-flex;gap:3px} .dots i{width:6px;height:6px;border-radius:50%;background:var(--border-strong)} .dots i.on{background:var(--accent)}
.ec-note{font-size:13px;color:var(--muted);line-height:1.55;margin:12px 0 0}
.muted{color:var(--muted);font-size:14px}
@media (max-width:760px){.ec-grid{grid-template-columns:1fr}.ec-kpis{grid-template-columns:1fr 1fr}.ec-kpi .v{font-size:19px}}
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
var D=null, MIN=2;
// neutral: higher yields are good for savers and bad for borrowers
function bp(v){ if(v==null) return '—'; var b=Math.round(v*100); return '<b>'+(b>0?'+':'')+b+'</b>'; }
function rates(){
  var k=D.curve.key||{}, sp=(D.curve.spread||[]), last=sp[sp.length-1]||{}, names={'3 Mo':'3-month','2 Yr':'2-year','10 Yr':'10-year','30 Yr':'30-year'};
  var h=Object.keys(names).filter(function(t){return k[t]&&k[t].now!=null;}).map(function(t){ var x=k[t];
    return '<div class="ec-kpi"><div class="l">'+names[t]+' Treasury</div><div class="v">'+x.now.toFixed(2)+'%</div>'+
      '<div class="s" title="Change in basis points (0.01%) over a week, a month and a year">1w '+bp(x['1w'])+' · 1m '+bp(x['1m'])+' · 1y '+bp(x['1y'])+' bp</div></div>'; }).join('');
  if(last.s10_2!=null) h+='<div class="ec-kpi"><div class="l">10-year minus 2-year</div><div class="v">'+(last.s10_2>0?'+':'')+last.s10_2.toFixed(2)+'</div>'+
    '<div class="s">'+(last.s10_2<0?'Inverted: short rates above long':'Normal: long rates above short')+'</div></div>';
  document.getElementById('ec-rates').innerHTML=h;
}
function curveChart(){
  var c=D.curve, el=document.getElementById('ec-curve');
  if(!c.curves||!c.curves.now){ el.textContent='Yield data unavailable.'; return; }
  el.className='';
  var ser=[['now','Today','var(--accent)'],['1m','A month ago','var(--ink)'],['1y','A year ago','var(--axis)']].filter(function(s){return c.curves[s[0]];});
  var all=[]; ser.forEach(function(s){ c.curves[s[0]].y.forEach(function(v){ if(v!=null) all.push(v); }); });
  var lo=Math.floor(Math.min.apply(null,all)*4)/4-0.1, hi=Math.ceil(Math.max.apply(null,all)*4)/4+0.1;
  var W=520,H=230,pl=40,pr=10,pt=10,pb=28, n=c.tenors.length;
  var sx=function(i){ return pl+i*(W-pl-pr)/(n-1); }, sy=function(v){ return pt+(hi-v)/(hi-lo)*(H-pt-pb); };
  var s='';
  for(var g=0;g<=4;g++){ var v=lo+(hi-lo)*g/4, y=sy(v);
    s+='<line x1="'+pl+'" x2="'+(W-pr)+'" y1="'+y.toFixed(1)+'" y2="'+y.toFixed(1)+'" stroke="var(--border)"/><text x="'+(pl-5)+'" y="'+(y+4).toFixed(1)+'" text-anchor="end" font-size="10" fill="var(--muted)">'+v.toFixed(1)+'%</text>'; }
  c.tenors.forEach(function(t,i){ if(i%2===0||i===n-1) s+='<text x="'+sx(i).toFixed(1)+'" y="'+(H-8)+'" text-anchor="middle" font-size="10" fill="var(--muted)">'+t.replace(' Mo','m').replace(' Yr','y')+'</text>'; });
  ser.slice().reverse().forEach(function(se){ var ys=c.curves[se[0]].y, pts=[];
    ys.forEach(function(v,i){ if(v!=null) pts.push(sx(i).toFixed(1)+','+sy(v).toFixed(1)); });
    s+='<polyline points="'+pts.join(' ')+'" fill="none" stroke="'+se[2]+'" stroke-width="'+(se[0]==='now'?2.4:1.5)+'"'+(se[0]==='1y'?' stroke-dasharray="4 3"':'')+'/>';
    if(se[0]==='now') ys.forEach(function(v,i){ if(v!=null) s+='<circle cx="'+sx(i).toFixed(1)+'" cy="'+sy(v).toFixed(1)+'" r="2.6" fill="var(--accent)"><title>'+c.tenors[i]+': '+v.toFixed(2)+'%</title></circle>'; }); });
  el.innerHTML='<svg viewBox="0 0 '+W+' '+H+'">'+s+'</svg><div class="ec-legend">'+ser.map(function(se){ return '<span><i style="background:'+se[2]+'"></i>'+se[1]+' ('+new Date(c.curves[se[0]].date+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})+')</span>'; }).join('')+'</div>';
}
function spreadChart(){
  var sp=(D.curve.spread||[]).filter(function(r){return r.s10_2!=null||r.s10_3m!=null;}), el=document.getElementById('ec-spread');
  if(sp.length<2){ el.innerHTML=''; return; }
  var all=[]; sp.forEach(function(r){ if(r.s10_2!=null) all.push(r.s10_2); if(r.s10_3m!=null) all.push(r.s10_3m); });
  var lo=Math.min(0,Math.min.apply(null,all))-0.1, hi=Math.max(0,Math.max.apply(null,all))+0.1;
  var W=520,H=230,pl=40,pr=10,pt=10,pb=28, n=sp.length;
  var sx=function(i){ return pl+i*(W-pl-pr)/(n-1); }, sy=function(v){ return pt+(hi-v)/(hi-lo)*(H-pt-pb); };
  var s='<rect x="'+pl+'" y="'+sy(0).toFixed(1)+'" width="'+(W-pl-pr)+'" height="'+(sy(lo)-sy(0)).toFixed(1)+'" fill="var(--down)" opacity="0.06"/>';
  for(var g=0;g<=4;g++){ var v=lo+(hi-lo)*g/4, y=sy(v);
    s+='<text x="'+(pl-5)+'" y="'+(y+4).toFixed(1)+'" text-anchor="end" font-size="10" fill="var(--muted)">'+(v>0?'+':'')+v.toFixed(1)+'</text>'; }
  s+='<line x1="'+pl+'" x2="'+(W-pr)+'" y1="'+sy(0).toFixed(1)+'" y2="'+sy(0).toFixed(1)+'" stroke="var(--ink)" stroke-width="1" opacity="0.5"/>';
  var yrs={}; sp.forEach(function(r,i){ var y=r.date.slice(0,4); if(!yrs[y]){ yrs[y]=1; if(i>0) s+='<text x="'+sx(i).toFixed(1)+'" y="'+(H-8)+'" text-anchor="middle" font-size="10" fill="var(--muted)">'+y+'</text>'; } });
  [['s10_3m','10-year minus 3-month','var(--axis)'],['s10_2','10-year minus 2-year','var(--accent)']].forEach(function(se){
    var pts=[]; sp.forEach(function(r,i){ if(r[se[0]]!=null) pts.push(sx(i).toFixed(1)+','+sy(r[se[0]]).toFixed(1)); });
    s+='<polyline points="'+pts.join(' ')+'" fill="none" stroke="'+se[2]+'" stroke-width="1.6"/>'; });
  el.innerHTML='<svg viewBox="0 0 '+W+' '+H+'">'+s+'</svg><div class="ec-legend"><span><i style="background:var(--accent)"></i>10-year minus 2-year</span><span><i style="background:var(--axis)"></i>10-year minus 3-month</span><span class="m">Below zero (shaded): inverted</span></div>';
}
function calendar(){
  var rows=D.calendar.filter(function(e){return e.importance>=MIN;}), el=document.getElementById('ec-cal');
  if(!rows.length){ el.className='ec-box muted'; el.textContent='No releases in this window.'; return; }
  // one reading per indicator: on its latest release so far, else its next one
  var shown={}, today=D.today;
  rows.slice().reverse().forEach(function(e){ if(e.last && e.date<=today && !shown[e.name]) shown[e.name]=e; });
  rows.forEach(function(e){ if(e.last && !shown[e.name]) shown[e.name]=e; });
  var by={}; rows.forEach(function(e){ (by[e.date]=by[e.date]||[]).push(e); });
  var h='<table class="ec-t"><thead><tr><th>Time (ET)</th><th>Release</th><th>Impact</th><th>Latest reading</th><th>Before that</th><th>Source</th></tr></thead><tbody>';
  Object.keys(by).sort().forEach(function(d){ var dt=new Date(d+'T12:00:00'), n=Math.round((dt-new Date(today+'T12:00:00'))/864e5);
    h+='<tr class="dh'+(n===0?' today':'')+'"><td colspan="6">'+dt.toLocaleDateString('en-US',{weekday:'long',month:'short',day:'numeric'})+(n===0?' · today':n===1?' · tomorrow':n<0?'':' · in '+n+' days')+'</td></tr>';
    by[d].forEach(function(e){ var r=shown[e.name]===e?e.last:null;
      h+='<tr'+(d<today?' class="past"':'')+'><td>'+(e.time?esc(new Date('2000-01-01T'+e.time+':00').toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'})):'')+'</td>'+
        '<td class="nm"><b>'+esc(e.name)+'</b>'+(e.title!==e.name?'<small>'+esc(e.title)+'</small>':'')+'</td>'+
        '<td class="imp"><span class="dots" title="'+['','Minor','Notable','Major'][e.importance]+'">'+[1,2,3].map(function(i){return '<i'+(i<=e.importance?' class="on"':'')+'></i>';}).join('')+'</span></td>'+
        '<td>'+(r?esc(r.text)+' <span class="m">('+esc(r.period)+')</span>':'')+'</td><td class="m">'+(r&&r.prev?esc(r.prev):'')+'</td><td class="m">'+esc(e.source)+'</td></tr>'; }); });
  el.className='ec-box'; el.innerHTML=h+'</tbody></table>';
}
document.querySelectorAll('#ec-imp button').forEach(function(b){ b.addEventListener('click',function(){
  document.querySelectorAll('#ec-imp button').forEach(function(x){x.classList.toggle('on',x===b);}); MIN=+b.getAttribute('data-i'); if(D) calendar(); }); });
fetch('/api/economy').then(function(r){return r.json();}).then(function(d){
  if(!d.ok){ document.getElementById('ec-cal').textContent='Economic data is unavailable right now.'; document.getElementById('ec-curve').textContent=''; return; }
  D=d; rates(); curveChart(); spreadChart(); calendar();
}).catch(function(){ document.getElementById('ec-cal').textContent='Could not load economic data.'; });
"""
