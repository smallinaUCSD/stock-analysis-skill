"""Full-page deep analysis for one ticker - roomier and larger-text than the
card modal, opened from the card via a button. Reuses the board's *tested* render
helpers (valuation, trade setup + sizing + regime, options); adds no new math.
"""

from __future__ import annotations

import html as _html

from ..dashboard.render import _CSS
from ..watchlist.render import (
    _CSS_EXTRA, _valuation_html, _trade_setup_html, _options_html, _pct, _SIG_CLASS,
)

_ANALYSIS_CSS = """
body{font-size:15px}
.wrap{max-width:min(1100px,100%);padding:20px clamp(16px,3vw,40px)}
.a-head{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin:4px 0 2px}
.a-head h1{margin:0;font-size:26px}
.a-price{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums;margin-left:auto}
.agrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px;margin-top:12px;align-items:start}
.asec{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 22px}
.asec .det-sec{margin:0}
.asec .det-h{font-size:16px;font-weight:700;margin:0 0 12px}
.asec .det-row{font-size:14.5px;padding:7px 0;border-top:1px solid var(--border);
  display:flex;justify-content:space-between;gap:12px}
.asec .det-row:first-of-type{border-top:none}
.asec .det-note{font-size:13px;margin-top:10px;line-height:1.5}
.asec .tsetup{border:none;background:none;padding:0;margin:0}
.asec .ts-h{font-size:16px;font-weight:700;margin-bottom:10px}
.asec .ts-row{font-size:14.5px;padding:5px 0}
.asec .ts-sub{font-size:13px;margin:6px 0;line-height:1.5}
.asec .fvtable{width:100%;font-size:14.5px;margin:2px 0 4px}
.asec .fvtable td,.asec .fvtable th{padding:7px 10px}
.a-back{display:inline-block;margin:14px 0;color:var(--muted);text-decoration:none;font-size:14px}
.a-back:hover{color:var(--ink);text-decoration:underline}
.a-note{color:var(--muted);font-size:12.5px;margin-top:16px;line-height:1.5}
.h-help{color:var(--accent);text-decoration:none;font-weight:600}.h-help:hover{text-decoration:underline}
.a-foot{color:var(--muted);font-size:12px;text-align:center;margin:26px 0 6px;
  padding-top:14px;border-top:1px solid var(--border)}
"""


def analysis_html(row) -> str:
    tk = _html.escape(row.ticker)
    name = _html.escape((row.name or row.ticker)[:60])
    price = f"${row.price:,.2f}" if row.price else "n/a"
    dcls, dtxt = _pct(row.changes.get("1d"))
    sig_cls = _SIG_CLASS.get(row.signal, "hold")

    val_sec = f'<div class="asec">{_valuation_html(row)}</div>'
    trade = _trade_setup_html(row)
    trade_sec = f'<div class="asec">{trade}</div>' if trade else ""
    opts = _options_html(row)
    opts_sec = f'<div class="asec">{opts}</div>' if opts else ""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{tk} analysis</title><style>{_CSS}{_CSS_EXTRA}{_ANALYSIS_CSS}</style></head>
<body><div class="wrap">
<div class="a-head"><h1>{tk}</h1><span class="nm">{name}</span>
  <span class="badge {sig_cls}">{_html.escape(row.signal)}</span>
  <span class="a-price">{price} <span class="{dcls}" style="font-size:16px">{dtxt}</span></span></div>
<div class="agrid">{val_sec}{trade_sec}{opts_sec}</div>
<p class="a-note">Analysis, not advice. Valuation, edge estimates, and regime reads
are model outputs on free data; the decision is yours. See the board card for the
price chart and recent news. <a class="h-help" href="/interpret" onclick="return openHelp(event)">How to read these →</a></p>
<a class="a-back" href="/" onclick="return goBack(event)">← back to board</a>
<div class="a-foot">2026 SMI Investments. All rights reserved.</div>
</div>
<script>
function goBack(e){{ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){{ try{{window.opener.focus();}}catch(_){{}}; window.close(); }}
  else location.href='/'; return false; }}
function openHelp(e){{ if(e) e.preventDefault(); window.open('/interpret','_blank'); return false; }}
</script>
</body></html>"""
