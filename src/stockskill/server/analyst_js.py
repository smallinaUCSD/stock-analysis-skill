"""Shared browser code that draws the analyst-ratings summary from
/api/analysts/<ticker> (used by the quick-look card and the analysis page)."""

ANALYST_CSS = """
.dv-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px 14px;margin:4px 0 8px}
.dv-grid div{font-size:13px;color:var(--muted)} .dv-grid b{display:block;font-size:16px;font-weight:500;color:var(--ink)}
.dv-bars{display:flex;align-items:flex-end;gap:3px;height:46px;margin:6px 0 2px} .dv-bars i{flex:1;background:var(--axis);border-radius:2px}
.dv-bars i:last-child{background:var(--accent)} .dv-yrs{display:flex;justify-content:space-between;font-size:11px;color:var(--muted)}
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
function dvHTML(d){
  if(!d || !d.ok) return '<div class="an-note">'+((d&&d.error)||'No dividend data.')+'</div>';
  if(!d.pays) return '<div class="an-line">Doesn\'t pay a dividend'+(d.last_date?' <span class="m">(last paid '+d.last_date+')</span>':'')+'.</div>';
  var pct=function(x,dp){ return x==null?'n/a':(x*100).toFixed(dp==null?1:dp)+'%'; };
  var mon=function(s){ return new Date(s+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); };
  var h='<div class="dv-grid"><div><b>'+pct(d.yield,2)+'</b>yield</div><div><b>$'+d.ttm.toFixed(2)+'</b>paid, last 12 months</div>'+
    '<div><b>'+(d.frequency||'n/a')+'</b>payments</div><div><b>'+(d.growth_5y!=null?(d.growth_5y>=0?'+':'')+pct(d.growth_5y):'n/a')+'</b>growth a year, 5 years</div>'+
    '<div><b>'+(d.streak?d.streak+' yr'+(d.streak>1?'s':''):'None')+'</b>raised in a row</div>'+
    '<div><b>'+(d.payout_ratio!=null?pct(d.payout_ratio,0):'n/a')+'</b>of earnings paid out</div></div>';
  var ys=(d.years||[]).slice(-10), mx=Math.max.apply(null,ys.map(function(y){return y.total;}))||1;
  if(ys.length>2) h+='<div class="dv-bars">'+ys.map(function(y){ return '<i style="height:'+Math.max(4,y.total/mx*100).toFixed(0)+'%" title="'+y.year+': $'+y.total.toFixed(2)+'"></i>'; }).join('')+
    '</div><div class="dv-yrs"><span>'+ys[0].year+'</span><span>'+ys[ys.length-1].year+' (so far)</span></div>';
  h+='<div class="an-line" style="margin-top:8px"><span class="m">Last paid $'+d.last_amount.toFixed(2)+' on '+mon(d.last_date)+
    (d.next_ex?' · next ex-dividend date '+mon(d.next_ex):'')+'</span></div>';
  return h+'<div class="an-note">Paying since '+d.since+' in Yahoo\'s history (older records can have gaps). Payout ratio uses trailing earnings.</div>';
}
function loadAnalysts(el, tkr){
  if(!el||!tkr) return;
  fetch('/api/analysts/'+encodeURIComponent(tkr)).then(function(r){return r.json();})
    .then(function(d){ el.innerHTML=anHTML(d); }).catch(function(){ el.innerHTML='<div class="an-note">Analyst ratings unavailable.</div>'; });
}
"""
