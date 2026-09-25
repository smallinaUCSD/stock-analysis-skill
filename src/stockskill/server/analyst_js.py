"""Shared browser code that draws the analyst-ratings summary from
/api/analysts/<ticker> (used by the quick-look card and the analysis page)."""

ANALYST_CSS = """
.mx-an{margin-top:16px}
.an-bar{display:flex;height:12px;border-radius:6px;overflow:hidden;margin:8px 0 6px;background:var(--surface-2)}
.an-bar i{display:block;height:100%}
.an-leg{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12px;color:var(--muted)}
.an-leg b{font-weight:500;color:var(--ink)}
.an-line{font-size:14px;line-height:1.5;margin:2px 0}
.an-line .m{color:var(--muted)}
.an-note{font-size:12px;color:var(--muted);margin-top:6px}
"""

ANALYST_JS = r"""
function anHTML(d){
  if(!d || !d.ok) return '<div class="an-note">'+((d&&d.error)||'No analyst coverage.')+'</div>';
  var h='', pct=function(x){ return Math.round(x*100)+'%'; };
  if(d.analysts){
    var t=d.trend[d.trend.length-1], n=d.analysts;
    var seg=[['strong_buy','var(--up)','Strong buy'],['buy','color-mix(in srgb,var(--up) 55%,var(--surface))','Buy'],
             ['hold','var(--axis)','Hold'],['sell','color-mix(in srgb,var(--down) 55%,var(--surface))','Sell'],['strong_sell','var(--down)','Strong sell']];
    var mon=new Date(d.period+'T12:00:00').toLocaleDateString('en-US',{month:'short',year:'numeric'});
    h+='<div class="an-line"><b>'+d.label+'</b> <span class="m">· '+n+' analysts, '+mon+'</span></div>';
    h+='<div class="an-bar" role="img" aria-label="'+pct(d.buy_pct)+' buy, '+pct(d.hold_pct)+' hold, '+pct(d.sell_pct)+' sell">'+
      seg.map(function(s){ var c=t[s[0]]||0; return c?'<i style="width:'+(c/n*100).toFixed(1)+'%;background:'+s[1]+'" title="'+s[2]+': '+c+'"></i>':''; }).join('')+'</div>';
    h+='<div class="an-leg"><span><b>'+pct(d.buy_pct)+'</b> buy</span><span><b>'+pct(d.hold_pct)+'</b> hold</span><span><b>'+pct(d.sell_pct)+'</b> sell</span>'+
      (d.buy_change!=null && d.months>1?'<span>buy share '+(d.buy_change>=0?'+':'')+Math.round(d.buy_change*100)+' pts over '+d.months+' months</span>':'')+'</div>';
  }
  if(d.target_mean){
    h+='<div class="an-line" style="margin-top:8px">Average price target <b>$'+d.target_mean.toFixed(2)+'</b>'+
      (d.upside!=null?' <span class="m">('+(d.upside>=0?'+':'')+(d.upside*100).toFixed(0)+'% vs the last close)</span>':'')+'</div>';
  }
  return h+'<div class="an-note">Reported third-party opinions (Finnhub, Yahoo), not our view.</div>';
}
function loadAnalysts(el, tkr){
  if(!el||!tkr) return;
  fetch('/api/analysts/'+encodeURIComponent(tkr)).then(function(r){return r.json();})
    .then(function(d){ el.innerHTML=anHTML(d); }).catch(function(){ el.innerHTML='<div class="an-note">Analyst ratings unavailable.</div>'; });
}
"""
