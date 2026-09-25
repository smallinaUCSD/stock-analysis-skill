"""Admin dashboard: who uses the site, what they use, and whether it's healthy.
Data from /api/admin/report (admins only)."""

from __future__ import annotations

from ..dashboard.render import _CSS, _THEME_BOOT, icon


def admin_html() -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Admin</title>" + _THEME_BOOT + "<style>" + _CSS + _EXTRA_CSS +
            "</style></head><body><div class=\"wrap\">"
            "<header><h1>Admin</h1><span class=\"sub\" style=\"margin:0\">Usage and health</span>"
            "<span class=\"seg ad-seg\" id=\"ad-days\"><button data-d=\"7\">7 days</button><button data-d=\"30\" class=\"on\">30 days</button>"
            "<button data-d=\"90\">90 days</button></span>"
            "<button class=\"page-x\" onclick=\"location.href='/'\" title=\"Close\" aria-label=\"Close\">" + icon("x", 17) + "</button></header>"
            "<div id=\"ad\" class=\"muted\">Loading…</div>"
            "<p class=\"ad-note\">First-party counts from this server's own logs. People = signed-in accounts plus anonymous "
            "visitors (a daily hash of IP and browser; the IP isn't stored). Bots and scripts are left out. Data is kept 90 days, as the Privacy Policy says.</p>"
            "</div><script>" + _JS + "</script></body></html>")


_EXTRA_CSS = """
.ad-seg{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-left:auto}
.ad-seg button{height:34px;padding:0 12px;border:none;background:var(--surface);color:var(--muted);font:500 13px var(--font);cursor:pointer}
.ad-seg button.on{background:var(--surface-3);color:var(--ink)}
.ad-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:6px 0 14px}
.ad-kpis.k8{grid-template-columns:repeat(4,1fr)}
.ad-k{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:10px 14px}
.ad-k span{display:block;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted)}
.ad-k b{font-size:24px;font-weight:500;font-variant-numeric:tabular-nums} .ad-k small{display:block;color:var(--muted);font-size:12px}
.ad-k.bad{border-color:var(--down)} .ad-k.bad b{color:var(--down)}
.ad-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.ad-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 14px;min-width:0}
.ad-card h3{font-size:12px;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted);font-weight:500;margin:0 0 8px}
.ad-card svg{display:block;width:100%;height:auto}
.ad-t{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
.ad-t td,.ad-t th{padding:5px 6px;border-top:1px solid var(--border);text-align:right;white-space:nowrap}
.ad-t th{border-top:none;color:var(--muted);font-weight:500;font-size:12px}
.ad-t td:first-child,.ad-t th:first-child{text-align:left;white-space:normal;word-break:break-all}
.ad-bar{display:inline-block;height:7px;border-radius:4px;background:var(--accent);vertical-align:middle;margin-right:6px}
.ad-leg{display:flex;gap:14px;font-size:12px;color:var(--muted);margin-top:4px} .ad-leg i{display:inline-block;width:12px;height:3px;margin-right:5px;vertical-align:3px}
.ad-note{font-size:13px;color:var(--muted);line-height:1.55}
.ad-t td small{color:var(--muted);margin-left:6px}
@media (max-width:800px){.ad-grid{grid-template-columns:1fr}.ad-kpis.k8{grid-template-columns:repeat(2,1fr)}.ad-t td small{display:none}}
"""

_JS = r"""
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
var DAYS=30;
var PAGES={'/':'Watchlist board','/analysis/<ticker>':'Stock page','/financials':'Financials','/earnings':'Earnings calendar',
  '/graph':'Connections graph','/screener':'Screener','/trades':'Politicians and funds','/politician/<pid>':'Politician profile',
  '/fund/<int:cik>':'Hedge-fund profile','/markets':'Markets','/economy':'Economy','/account':'Profile and settings',
  '/welcome':'Sign-up setup','/login':'Sign in','/signup':'Create account','/admin':'Admin','/terms':'Terms','/privacy':'Privacy',
  '/forgot':'Forgot password','/reset':'Reset password','/alerts':'Alerts','/breakouts':'Breakouts','/compare':'Compare',
  '/ipos':'IPOs','/indicators':'Indicators','/holdings':'Holdings','/analyze':'Analyze'};
var FEATS={quicklook:'Opened a quick look',menu_open:'Opened the profile menu',today_open:'Opened Today',watch_add:'Added to watchlist',
  watch_remove:'Removed from watchlist',view_card:'Switched to cards',view_table:'Switched to table',view_heatmap:'Switched to heatmap',density_simple:'Simple view',
  density_detailed:'Detailed view',screen_preset:'Screener preset',screen_export:'Screener CSV export',landing_signup:'Landing: sign-up click',
  landing_login:'Landing: sign-in click'};
function pageName(r){ return PAGES[r]||r; }
function featName(n){ return FEATS[n]||(n.indexOf('tab_')===0?'Stock tab: '+n.slice(4):n.indexOf('ql_')===0?'Quick look: '+n.slice(3).replace(/_/g,' '):n); }
function kpi(l,v,s,bad){ return '<div class="ad-k'+(bad?' bad':'')+'"><span>'+l+'</span><b>'+v+'</b><small>'+(s||'')+'</small></div>'; }
function table(rows, cols){ if(!rows||!rows.length) return '<div class="muted small">Nothing yet.</div>';
  var mx=Math.max.apply(null,rows.map(function(r){return r[cols[1][0]]||0;}))||1;
  return '<table class="ad-t"><thead><tr>'+cols.map(function(c){return '<th>'+c[1]+'</th>';}).join('')+'</tr></thead><tbody>'+
    rows.map(function(r){ return '<tr>'+cols.map(function(c,i){ var v=r[c[0]];
      if(i===1) return '<td><span class="ad-bar" style="width:'+Math.max(2,(v||0)/mx*80).toFixed(0)+'px"></span>'+(v==null?'':v)+'</td>';
      if(i===0&&c[2]){ var nm=c[2](v); return '<td>'+esc(nm)+(nm!==v?'<small>'+esc(v)+'</small>':'')+'</td>'; }
      return '<td>'+esc(c[2]?c[2](v):v)+'</td>'; }).join('')+'</tr>'; }).join('')+'</tbody></table>'; }
function lines(series, keys, cols){ if(!series.length) return '<div class="muted small">No data yet.</div>';
  var W=560,H=170,L=34,B=20,T=8, n=series.length, mx=1;
  series.forEach(function(r){ keys.forEach(function(k){ mx=Math.max(mx,r[k]||0); }); });
  var X=function(i){ return L+(n>1?i/(n-1):0.5)*(W-L-8); }, Y=function(v){ return T+(1-v/mx)*(H-T-B); };
  var s='<svg viewBox="0 0 '+W+' '+H+'">'+[0,0.5,1].map(function(f){ var v=Math.round(mx*f); return '<line x1="'+L+'" x2="'+(W-8)+'" y1="'+Y(v)+'" y2="'+Y(v)+'" stroke="var(--border)"/>'+
    '<text x="'+(L-4)+'" y="'+(Y(v)+4)+'" text-anchor="end" font-size="10" fill="var(--muted)">'+v+'</text>'; }).join('');
  keys.forEach(function(k,j){ s+='<polyline fill="none" stroke="'+cols[j]+'" stroke-width="2" points="'+series.map(function(r,i){ return X(i).toFixed(1)+','+Y(r[k]||0).toFixed(1); }).join(' ')+'"/>';
    if(n<=31) series.forEach(function(r,i){ s+='<circle cx="'+X(i).toFixed(1)+'" cy="'+Y(r[k]||0).toFixed(1)+'" r="3" fill="'+cols[j]+'"><title>'+esc(r.day)+': '+(r[k]||0)+'</title></circle>'; }); });
  s+='<text x="'+L+'" y="'+(H-4)+'" font-size="10" fill="var(--muted)">'+esc(series[0].day)+'</text><text x="'+(W-8)+'" y="'+(H-4)+'" text-anchor="end" font-size="10" fill="var(--muted)">'+esc(series[n-1].day)+'</text>';
  return s+'</svg>'; }
function ms(v){ return v==null?'n/a':v>=1000?(v/1000).toFixed(1)+' s':Math.round(v)+' ms'; }
function ago(s){ return s==null?'n/a':s<90?Math.round(s)+' s':s<5400?Math.round(s/60)+' min':(s/3600).toFixed(1)+' h'; }
function render(d){
  var h=d.health||{}, b=h.board||{}, errRate=d.requests_24h?d.errors_24h/d.requests_24h:0, ret=(d.retention||[]).filter(function(r){return r.signups;});
  var r7=ret.length?ret.reduce(function(a,r){return a+r.returned;},0)/Math.max(1,ret.reduce(function(a,r){return a+r.signups;},0)):null;
  var el=document.getElementById('ad'); el.className='';
  el.innerHTML='<div class="ad-kpis k8">'+kpi('Online now',d.active_now,'last 5 minutes')+kpi('Active today',d.dau,'signed-in people')+
    kpi('This week',d.wau,'signed-in people')+kpi('This month',d.mau,d.mau?'daily/monthly '+Math.round(d.dau/d.mau*100)+'%':'')+
    kpi('Anonymous today',d.visitors_today,'visitors not signed in')+kpi('Accounts',d.accounts==null?'n/a':d.accounts,(d.new_accounts||0)+' new in '+d.days+' days')+
    kpi('Finished sign-up',d.new_accounts?Math.round(d.new_onboarded/d.new_accounts*100)+'%':'n/a','of new accounts')+
    kpi('Came back in week 1',r7==null?'n/a':Math.round(r7*100)+'%','after signing up')+'</div>'+
    '<div class="ad-kpis">'+kpi('Requests, 24h',d.requests_24h,'p50 '+ms(d.p50_ms)+' · p95 '+ms(d.p95_ms))+
    kpi('Server errors, 24h',d.errors_24h,(errRate*100).toFixed(2)+'% of requests',errRate>0.02)+
    kpi('Board age',ago(b.age),(b.session||'')+(b.building?' · rebuilding':''),b.session==='open'&&b.age>2700)+
    kpi('Live prices',(h.quotes||{}).count||0,'median age '+ago((h.quotes||{}).median_age))+kpi('Analytics data',(h.db_mb||0)+' MB','')+'</div>'+
    '<div class="ad-grid"><div class="ad-card"><h3>People per day</h3>'+lines(d.daily||[],['users','visitors'],['var(--accent)','var(--axis)'])+
      '<div class="ad-leg"><span><i style="background:var(--accent)"></i>Signed in</span><span><i style="background:var(--axis)"></i>Anonymous</span></div></div>'+
    '<div class="ad-card"><h3>Page views and sign-ups per day</h3>'+lines((d.daily||[]).map(function(r){ var s=(d.signups||[]).find(function(x){return x.day===r.day;}); return {day:r.day,pages:r.pages,signups:(s?s.n:0)*10}; }),['pages','signups'],['var(--ink)','var(--up)'])+
      '<div class="ad-leg"><span><i style="background:var(--ink)"></i>Page views</span><span><i style="background:var(--up)"></i>Sign-ups (x10)</span></div></div></div>'+
    '<div class="ad-grid"><div class="ad-card"><h3>Most used pages, last 7 days</h3>'+table(d.top_pages,[['route','Page',pageName],['views','Views'],['people','People']])+'</div>'+
    '<div class="ad-card"><h3>Most used features, last 7 days</h3>'+table(d.top_features,[['name','Feature',featName],['uses','Uses'],['people','People']])+'</div></div>'+
    '<div class="ad-grid"><div class="ad-card"><h3>Most looked-at stocks, last 7 days</h3>'+table(d.top_stocks,[['ticker','Stock'],['people','People'],['views','Views']])+'</div>'+
    '<div class="ad-card"><h3>Busiest data requests, last 7 days</h3>'+table(d.top_api,[['route','Endpoint'],['calls','Calls'],['people','People']])+'</div></div>'+
    '<div class="ad-grid"><div class="ad-card"><h3>Devices</h3>'+table(d.devices,[['name','Device'],['people','People']])+
      '<h3 style="margin-top:12px">Browsers</h3>'+table(d.browsers,[['name','Browser'],['people','People']])+'</div>'+
    '<div class="ad-card"><h3>Operating systems</h3>'+table(d.os,[['name','System'],['people','People']])+
      '<h3 style="margin-top:12px">Where visitors came from</h3>'+table(d.referrers,[['name','Site'],['visits','Visits']])+'</div></div>'+
    '<div class="ad-grid"><div class="ad-card"><h3>Kinds of investor</h3>'+table(d.investor_types,[['name','Type'],['n','Accounts']])+'</div>'+
    '<div class="ad-card"><h3>Sign-in and notifications</h3>'+table([
      {k:'Google sign-in',v:(d.sign_in||{}).google},{k:'Password',v:(d.sign_in||{}).password},{k:'Passkey',v:(d.sign_in||{}).passkey},
      {k:'2-step verification',v:(d.sign_in||{}).two_step},{k:'Daily summary on',v:(d.notify||{}).summary},{k:'Email (confirmed)',v:(d.notify||{}).email},
      {k:'Browser notifications',v:(d.notify||{}).push},{k:'Follows (people and funds)',v:(d.notify||{}).follows}],[['k',''],['v','Accounts']])+'</div></div>'+
    '<div class="ad-grid"><div class="ad-card"><h3>Slowest routes, last 24h (p95)</h3>'+table(d.slow_routes,[['route','Route'],['p95','p95 ms',Math.round],['p50','p50 ms',Math.round],['count','Calls']])+'</div>'+
    '<div class="ad-card"><h3>Recent server errors</h3>'+table((d.recent_errors||[]).map(function(e){ return {when:new Date(e.ts*1000).toLocaleString(),path:e.path,status:e.status}; }),
      [['path','Path'],['status','Status'],['when','When']])+'</div></div>'+
    '<div class="ad-card"><h3>Weekly sign-up cohorts: came back within a week</h3>'+table((d.retention||[]).map(function(r){ return {week:r.week,signups:r.signups,returned:r.returned}; }),
      [['week','Week of'],['signups','Sign-ups'],['returned','Came back']])+'</div>';
}
function load(){ fetch('/api/admin/report?days='+DAYS).then(function(r){return r.json();}).then(function(d){ if(d.ok) render(d); else document.getElementById('ad').textContent='Not available.'; }); }
document.querySelectorAll('#ad-days button').forEach(function(b){ b.onclick=function(){ DAYS=+b.dataset.d;
  document.querySelectorAll('#ad-days button').forEach(function(x){ x.classList.toggle('on',x===b); }); load(); }; });
load(); setInterval(function(){ if(!document.hidden) load(); }, 60000);
"""
