"""Shared SVG renderer for the knowledge graph (full page and the card's mini map).

drawGraph(el, data, opts): suppliers on the left, customers on the right, the
company's own investments below, same-industry competitors above; every link
carries its source in a hover title. opts.onNode(ticker) handles clicks.
"""

GRAPH_JS = r"""
var GROUPS={suppliers:{col:'#5db8a6',label:'Suppliers',side:'left'},customers:{col:'var(--accent)',label:'Customers',side:'right'},
  competitors:{col:'var(--muted)',label:'Competitors',side:'top'},investments:{col:'#e8a55a',label:'Invests in',side:'bottom'}};
function gEsc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
function drawGraph(el, d, opts){
  opts=opts||{}; var sm=!!opts.small, W=opts.width||900, max=opts.max||(sm?5:8), r=sm?14:20, gap=sm?40:54;
  var cols=Math.max((d.suppliers||[]).slice(0,max).length,(d.customers||[]).slice(0,max).length,1);
  var hasTop=(d.competitors||[]).length>0, hasBot=(d.investments||[]).length>0;
  var top=hasTop?(sm?58:78):24, bot=hasBot?(sm?58:84):24;
  var H=Math.max(sm?220:360, top+bot+26+cols*gap), cx=W/2, cy=top+13+(H-top-bot)/2;
  var ment={}; (d.mentions||[]).forEach(function(m){ if(m.ticker) ment[m.ticker]=1; });
  var lx=sm?150:190, rx=W-lx, s='<svg class="kg-svg" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+gEsc(d.ticker)+' connections">', nodes='';
  function place(g){ var G=GROUPS[g], all=d[g]||[], items=all.slice(0,max), n=items.length; if(!n) return;
    var more=all.length>n?' (+'+(all.length-n)+')':'';
    items.forEach(function(it,i){ var x,y,tx,ty,anc;
      if(G.side==='left'||G.side==='right'){ x=G.side==='left'?lx:rx; y=top+26+(H-top-bot-26)*(i+0.5)/n;
        tx=G.side==='left'?x-r-8:x+r+8; ty=y+4; anc=G.side==='left'?'end':'start'; }
      else { var x0=lx+60, x1=rx-60; x=n===1?cx:x0+(x1-x0)*i/(n-1); y=G.side==='top'?top-(sm?28:40):H-bot+(sm?28:40);
        tx=x; ty=G.side==='top'?y-r-6:y+r+14; anc='middle'; }
      var dash=g==='investments'?' stroke-dasharray="5 4"':(g==='competitors'?' stroke-dasharray="2 4"':'');
      s+='<line x1="'+cx+'" y1="'+cy+'" x2="'+x.toFixed(1)+'" y2="'+y.toFixed(1)+'" stroke="'+G.col+'" stroke-width="1.3" opacity="0.6"'+dash+'/>';
      var label=it.ticker||it.name||'', sub=(it.name&&it.ticker&&it.name!==it.ticker)?it.name:'';
      var tip=(it.name||'')+(it.what?' - '+it.what:'')+(it.basis?' ('+it.basis+')':'')+(it.ticker&&ment[it.ticker]?' · also named in its 10-K':'');
      var side=(G.side==='left'||G.side==='right');
      nodes+='<g class="kg-node'+(it.ticker?' click':'')+'" data-t="'+gEsc(it.ticker||'')+'"><title>'+gEsc(tip)+'</title>'+
        '<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="'+r+'" fill="var(--surface)" stroke="'+G.col+'" stroke-width="'+(it.on_watchlist?2.4:1.4)+'"/>'+
        (it.ticker&&ment[it.ticker]?'<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="'+(r+4)+'" fill="none" stroke="'+G.col+'" stroke-width="0.8" opacity="0.7"/>':'')+
        '<text x="'+x.toFixed(1)+'" y="'+(y+4).toFixed(1)+'" text-anchor="middle" class="kg-t">'+gEsc(it.ticker?label.slice(0,5):(it.short||(label.split(' ')[0]||'').slice(0,5)))+'</text>'+
        (side?'<text x="'+tx.toFixed(1)+'" y="'+ty.toFixed(1)+'" text-anchor="'+anc+'" class="kg-s">'+gEsc((it.ticker?(sub||''):(it.pct!=null?it.pct+'% of revenue'+(sm?'':' (10-K)'):label)).slice(0,sm?20:30))+'</text>'
             :(it.ticker?'':'<text x="'+tx.toFixed(1)+'" y="'+ty.toFixed(1)+'" text-anchor="middle" class="kg-s">'+gEsc(label.slice(0,12))+'</text>'))+'</g>';
    });
    var gl, gx, gy, ga;
    if(G.side==='left'){ gx=lx; gy=top+10; ga='middle'; } else if(G.side==='right'){ gx=rx; gy=top+10; ga='middle'; }
    else { gx=16; gy=G.side==='top'?top-(sm?24:36):H-bot+(sm?32:44); ga='start'; }
    if(G.side==='left'||G.side==='right'){ gy=Math.max(14,gy); }
    s+='<text x="'+gx+'" y="'+gy+'" text-anchor="'+ga+'" class="kg-grp" fill="'+G.col+'">'+G.label+more+'</text>';
  }
  ['competitors','investments','suppliers','customers'].forEach(place);
  s+=nodes+'<g class="kg-center"><circle cx="'+cx+'" cy="'+cy+'" r="'+(sm?26:36)+'" fill="var(--accent)"/>'+
    '<text x="'+cx+'" y="'+(cy+5)+'" text-anchor="middle" class="kg-c">'+gEsc(d.ticker)+'</text></g></svg>';
  el.innerHTML=s;
  [].forEach.call(el.querySelectorAll('.kg-node.click'),function(g){ g.addEventListener('click',function(){ if(opts.onNode) opts.onNode(g.dataset.t); }); });
}
"""

GRAPH_CSS = """
.kg-svg{width:100%;height:auto;display:block}
.kg-svg text{font-family:var(--font)}
.kg-grp{font-size:13px;font-weight:500;text-transform:uppercase;letter-spacing:1.5px}
.kg-t{font-size:12px;font-weight:500;fill:var(--ink)} .kg-s{font-size:11px;fill:var(--muted)}
.kg-c{font-size:15px;font-weight:500;fill:var(--accent-ink)}
.kg-node.click{cursor:pointer} .kg-node.click:hover circle:first-of-type{fill:var(--surface-2)}
"""
