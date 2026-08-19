"""Interpret: a plain-language guide to reading the dashboard's numbers.

A static help page (opened from the board's "Interpret" button, and linked from
each analysis-page box) that explains, for a non-finance reader, what each metric
is, how to read it, the "so what", and two opposite worked examples. No math here,
just prose; the tested engines produce the numbers elsewhere.
"""

from __future__ import annotations

from ..dashboard.render import _CSS

_INTERPRET_CSS = """
.wrap{max-width:min(900px,100%);padding:22px clamp(16px,3vw,40px)}
header h1{margin:0 0 4px;font-size:26px}
header .sub{color:var(--muted);font-size:14px;margin:0}
.toc{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 8px}
.toc a{font-size:13px;padding:5px 11px;border-radius:999px;text-decoration:none;
  background:var(--surface-2);border:1px solid var(--border);color:var(--ink)}
.toc a:hover{border-color:var(--accent);color:var(--accent)}
.guide{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:20px 24px;margin:14px 0;scroll-margin-top:12px}
.guide h2{margin:0 0 4px;font-size:19px}
.guide .lede{color:var(--muted);font-size:14.5px;margin:0 0 12px;font-style:italic}
.guide h3{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--accent);
  margin:16px 0 5px}
.guide p{font-size:15px;line-height:1.62;margin:6px 0}
.guide ul{font-size:15px;line-height:1.55;margin:6px 0 6px 2px;padding-left:18px}
.guide li{margin:5px 0}
.guide b{color:var(--ink)}
.ex{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;
  padding:10px 14px;margin:8px 0;font-size:14.5px;line-height:1.55}
.ex .tag{font-weight:700}.ex .a{color:var(--up)}.ex .b{color:var(--down)}
.arrow-key{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}
.arrow-key div{font-size:14px;background:var(--surface-2);border:1px solid var(--border);
  border-radius:8px;padding:6px 10px}
.arrow-key .u{color:var(--up)}.arrow-key .d{color:var(--down)}.arrow-key .m{color:var(--muted)}
.h-back{display:inline-block;margin:12px 0;color:var(--muted);text-decoration:none;font-size:14px}
.h-back:hover{color:var(--ink);text-decoration:underline}
.foot{color:var(--muted);font-size:12px;text-align:center;margin:26px 0 6px;
  padding-top:14px;border-top:1px solid var(--border)}
.disc{color:var(--muted);font-size:12.5px;line-height:1.5;margin-top:14px}
"""


def _ex(a, b):
    return (f'<div class="ex"><span class="tag a">Example A.</span> {a}</div>'
            f'<div class="ex"><span class="tag b">Example B.</span> {b}</div>')


def _section(sid, title, lede, blocks):
    body = f'<div class="lede">{lede}</div>'
    for head, html in blocks:
        body += f'<h3>{head}</h3>{html}'
    return f'<section id="{sid}" class="guide"><h2>{title}</h2>{body}</section>'


def interpret_html() -> str:
    reading = _section(
        "reading", "Reading the board at a glance",
        "The colors, arrows, and how the numbers stay current.",
        [("Arrows (trend direction)",
          '<div class="arrow-key">'
          '<div><span class="u">&#8593;</span> strong uptrend</div>'
          '<div><span class="u">&#8599;</span> uptrend</div>'
          '<div><span class="m">&#8594;</span> neutral / sideways</div>'
          '<div><span class="d">&#8600;</span> downtrend</div>'
          '<div><span class="d">&#8595;</span> strong downtrend</div></div>'
          "<p>The arrow blends several indicators (moving averages, MACD, RSI, "
          "momentum) into one <b>trend read</b>. A steeper arrow means the evidence "
          "leans harder that way. It describes the recent trend, it does not predict "
          "the next move.</p>"),
         ("Colors",
          "<p><b class='up'>Green</b> is good-direction (price up, a positive change, "
          "a cheap value score, an edge in your favor). <b class='down'>Red</b> is the "
          "opposite (down, expensive, against you). <b>Grey</b> means neutral or no "
          "data. Percentile scores also run cold-to-warm: higher is a stronger rank.</p>"),
         ("It updates itself",
          "<p>While the market is open the board refreshes on its own about every 15 "
          "minutes (30 in extended hours, hourly when closed) and swaps in the new "
          "prices without you reloading; the \"Updated\" time shows when. The alert "
          "strip at the top <b>rotates</b> through the day's notable moves (new highs, "
          "big jumps, volume spikes). Signal badges (BUY / HOLD / SELL / SHORT) are "
          "rule-based indicator states, not advice.</p>")])

    factors = _section(
        "factors", "Factors", "Ranking a stock against its peers on five proven traits.",
        [("What it is",
          "<p>Research finds a few measurable traits tend to line up with future returns. "
          "Every name is scored on five: <b>Value</b> (cheap for what you get?), "
          "<b>Quality</b> (strong, profitable business?), <b>Momentum</b> (trending up?), "
          "<b>Growth</b> (expanding fast?), and <b>Low-volatility</b> (calm, not wild?).</p>"),
         ("How to read it",
          "<p>Each is a <b>0 to 100 percentile versus the other stocks on the board</b>. "
          "A Value of 90 is cheaper than 90% of the list; 50 is average. The "
          "<b>Composite</b> blends them. <b>Sector-neutral</b> judges \"cheap\" inside a "
          "stock's own industry, so it is not just a bet on a cheap sector.</p>"),
         ("So what",
          "<p>Cheap <b>and</b> high-quality <b>and</b> trending up is the combination that "
          "has historically paid off. Cheap but low-quality and falling is the classic "
          "\"value trap\". Use it to shortlist, not as a buy button.</p>"),
         ("Two examples", _ex(
             "A chipmaker reads <b>Value 20, Quality 85, Momentum 90</b>. It is "
             "expensive, but a strong business the market already loves and that keeps "
             "rising. You would be paying up for quality and momentum, not buying a bargain.",
             "A telecom reads <b>Value 95, Quality 15, Momentum 25</b>. Statistically the "
             "cheapest name on the board, but weak and drifting lower. The low quality and "
             "momentum warn it may be cheap for a reason (a value trap)."))])

    dcf = _section(
        "dcf", "DCF (Discounted Cash Flow)", "What the business itself is worth, ignoring the hype.",
        [("What it is",
          "<p>A company is worth all the cash it will hand owners in the future, converted "
          "to today's dollars (a dollar in ten years is worth less than one today). DCF "
          "adds up projected future free cash flow discounted back to now, giving a "
          "<b>fair value per share</b>.</p>"),
         ("How to read it",
          "<p>Fair value well <b>above</b> the price looks undervalued; well <b>below</b>, "
          "overvalued. It leans on assumptions, so treat it as a reasoned estimate. The "
          "<b>reverse-DCF</b> flips it: <i>what growth does today's price already assume?</i> "
          "A very high number means you are paying for perfection.</p>"),
         ("So what",
          "<p>DCF anchors you to the worth of the business, apart from the mood of the "
          "market. The useful moments are when price and DCF disagree.</p>"),
         ("Two examples", _ex(
             "A steady payer: price $80, DCF fair value $105, reverse-DCF implies ~4% "
             "growth. The price assumes almost nothing, and the cash flows support more, "
             "so it looks undervalued with a margin of safety.",
             "A hot grower: price $300, DCF base case $120, reverse-DCF implies ~35% growth "
             "for a decade. The stock is priced for near-flawless execution; any stumble "
             "in that growth and the fair value is far below."))])

    montecarlo = _section(
        "montecarlo", "Monte Carlo valuation", "The DCF, but as a range of outcomes with odds.",
        [("What it is",
          "<p>A single DCF hides its uncertainty. Monte Carlo runs the DCF thousands of "
          "times, each nudging the assumptions (growth, margins, discount rate) at random, "
          "producing a whole <b>range</b> of fair values.</p>"),
         ("How to read it",
          "<p><b>P5 to P95</b> is the middle 90% of outcomes (the low-to-high band). "
          "<b>P(undervalued)</b> is the share of runs worth more than today's price. 80% "
          "means \"in about 8 of 10 plausible futures it is worth more than you pay\".</p>"),
         ("So what",
          "<p>More honest than one number. High P(undervalued) with a tight band is a "
          "confident cheap read; a coin-flip near 50%, or a very wide band, means the "
          "answer depends heavily on assumptions.</p>"),
         ("Two examples", _ex(
             "P(undervalued) <b>85%</b>, band $95 to $130, price $90. Nearly every "
             "scenario lands above the price and the spread is tight: a confident, "
             "well-supported \"cheap\".",
             "P(undervalued) <b>48%</b>, band $40 to $260, price $150. A coin flip with a "
             "huge spread: the verdict swings entirely on the growth assumption, so lean on "
             "the range and your own judgement, not a single figure."))])

    ptarget = _section(
        "ptarget", "P(target before stop)", "The odds a trade reaches its target before its stop.",
        [("What it is",
          "<p>A trade setup has an entry, a <b>stop</b> below (cut the loss) and a "
          "<b>target</b> above (take the profit). This estimates the chance price touches "
          "the <b>target first</b>, from the stock's recent drift and volatility (a classic "
          "\"first-passage\" calculation: which of two lines a wandering price hits first).</p>"),
         ("How to read it",
          "<p>60% means reaching the target first is more likely than getting stopped out, "
          "given how the stock has been moving. Below 50% the odds favor the stop. It "
          "assumes the recent trend and volatility continue, so it is an estimate of the "
          "edge, not a promise.</p>"),
         ("So what",
          "<p>It turns a stop and target into an honest edge number, and it feeds the "
          "position sizing below.</p>"),
         ("Two examples", _ex(
             "An uptrending name with a 2:1 target: <b>P(target before stop) 63%</b>. Its "
             "upward drift makes hitting the higher target first more likely, so the trade "
             "has a real edge.",
             "A downtrending name, same 2:1 setup for a long: <b>P(target before stop) "
             "34%</b>. The drift is against you, so the stop is the more likely touch first, "
             "and the edge is negative for a long."))])

    kelly = _section(
        "kelly", "Position sizing (Kelly and vol-targeting)", "How big a position the edge justifies.",
        [("What it is",
          "<p>Three ways to size a trade, shown side by side. <b>Fixed</b> risks a flat 2% "
          "of capital. <b>Kelly</b> sizes by the edge: it risks more when the win "
          "probability is higher and tells you to pass when there is no edge. "
          "<b>Vol-targeting</b> shrinks the position when the stock is jumpy so each trade "
          "carries similar risk.</p>"),
         ("How to read it",
          "<p>\"Half-Kelly risk 6%\" means bet so a stop-out costs about 6% of capital. We "
          "show <b>half</b>-Kelly on purpose: full Kelly is very aggressive and swings hard. "
          "\"No positive edge, pass\" means the odds do not justify the trade at all.</p>"),
         ("So what",
          "<p>It connects the edge to a disciplined size instead of guessing, and it "
          "refuses to size a trade that has no edge.</p>"),
         ("Two examples", _ex(
             "Strong edge (P(target) 63%, 2:1): half-Kelly suggests risking a meaningful "
             "slice, more than the flat 2%, because the odds and payoff are both in your "
             "favor. Vol-targeting still trims it if the stock is wild.",
             "No edge (P(target) 34%): Kelly says <b>pass</b>. The fixed rule would still "
             "hand you a 2% position, which is exactly the trap Kelly avoids: sizing a "
             "trade the odds are against."))])

    momentum = _section(
        "momentum", "Momentum (time-series)", "Does the stock's own trend tend to continue?",
        [("What it is",
          "<p>Time-series momentum looks at a stock <b>against its own past</b>: the sign of "
          "its trailing 12-month return. Historically, up tends to keep going up for a while, "
          "and down keeps going down, before eventually reversing.</p>"),
         ("How to read it",
          "<p>A positive 12-month return reads as an <b>uptrend</b> (lean long), negative as "
          "a <b>downtrend</b>. The suggested position is scaled down when the stock is more "
          "volatile, so a calm and a wild name carry comparable risk.</p>"),
         ("So what",
          "<p>A simple, robust trend check that pairs with the regime read below: when both "
          "agree, the trend signal is stronger; when they disagree, be cautious.</p>"),
         ("Two examples", _ex(
             "Trailing 12m <b>+28%</b>: a clear uptrend, so time-series momentum leans long, "
             "and because its volatility is moderate the suggested size is normal.",
             "Trailing 12m <b>-15%</b>: a downtrend, so momentum leans short or stand-aside. "
             "If it is also very volatile, the suggested size shrinks further."))])

    regime = _section(
        "regime", "Regime (Dai-Zhang-Zhu)", "Is the stock in a bull or bear phase, as a probability?",
        [("What it is",
          "<p>This model treats the market as a hidden switch between a <b>bull</b> phase "
          "(rising) and a <b>bear</b> phase (falling), and estimates the probability you are "
          "in the bull one from the price path.</p>"),
         ("How to read it",
          "<p><b>P(bull) above ~60%</b> reads bull (the up-trend is probably intact), "
          "<b>below ~40%</b> reads bear, in between is unclear. The phase is inferred from "
          "prices, so treat it as a considered opinion, not a certainty.</p>"),
         ("So what",
          "<p>A principled entry/exit lens: catch a trend early when P(bull) rises, step "
          "aside when it falls. Best used together with the momentum read.</p>"),
         ("Two examples", _ex(
             "After months of steady gains, <b>P(bull) 78%</b>: the model is confident the "
             "up-phase is intact, supporting staying with the trend.",
             "After a sharp drop, <b>P(bull) 22%</b>: the model reads a bear phase and would "
             "have you exit or avoid, even if the last few days bounced."))])

    stops = _section(
        "stops", "Stop study (Kaminski-Lo)", "Would a stop-loss have helped or hurt this stock?",
        [("What it is",
          "<p>Research shows a stop-loss <b>helps names that trend cleanly but hurts choppy "
          "ones</b> (you get whipsawed out and miss the rebound). This backtests a trailing "
          "stop on <b>this specific stock's</b> history and reports which it was.</p>"),
         ("How to read it",
          "<p>\"Helped +3%/yr\" means a stop would have improved this stock's risk-adjusted "
          "return; \"hurt -6%/yr\" means it would have cost you. It is in-sample and ignores "
          "trading costs, so treat it as a guide, not a rule.</p>"),
         ("So what",
          "<p>It tells you whether a stop-loss is a tool this particular stock rewards, "
          "rather than applying one blindly.</p>"),
         ("Two examples", _ex(
             "A stock that trended up then crashed hard: the stop study reads <b>helped</b>, "
             "because a stop would have carried you out near the top and avoided the crash.",
             "A steady, gently-rising large-cap: the stop study reads <b>hurt</b>, because "
             "normal dips would have stopped you out only to rebound, costing return to "
             "whipsaw."))])

    voc = _section(
        "voc", "Virtue of Complexity (experimental)", "A complex model's stab at the next month, reported honestly.",
        [("What it is",
          "<p>An <b>experimental</b> research method that uses a deliberately complex model "
          "(many features, more parameters than data points) to predict the next month's "
          "return. The idea is that, with the right shrinkage, complexity can help.</p>"),
         ("How to read it",
          "<p>Trust the <b>out-of-sample R-squared</b>, not the headline read. Near zero "
          "means the model has <b>no reliable edge</b> here, which is the usual and honest "
          "result: predicting returns is genuinely hard. A positive timing Sharpe versus "
          "buy-and-hold would be the only thing worth noticing.</p>"),
         ("So what",
          "<p>It is here for completeness and honesty. Most of the time it will tell you "
          "\"no edge\", which is exactly the point: the tool reports what it finds rather "
          "than pretending to see the future.</p>"),
         ("Two examples", _ex(
             "OOS R-squared <b>+0.00</b>, timing Sharpe below buy-and-hold: the normal case. "
             "The model found no usable signal, so ignore its directional guess.",
             "OOS R-squared <b>+0.05</b>, timing Sharpe above buy-and-hold: rare and "
             "interesting, but still only a modest, fragile edge worth watching, not "
             "trusting outright."))])

    consensus = _section(
        "consensus", "Analyst consensus", "What professional analysts collectively expect.",
        [("What it is",
          "<p>Wall Street analysts publish ratings (buy / hold / sell) and price targets. "
          "The consensus is their average.</p>"),
         ("How to read it",
          "<p>The <b>target vs price</b> shows the upside or downside the Street sees. We "
          "show it <b>separately</b> from our own valuation because the two often disagree.</p>"),
         ("So what",
          "<p>A useful second opinion and a read on expectations, not truth. A big gap "
          "between our valuation and the Street tells you how much optimism is priced in.</p>"),
         ("Two examples", _ex(
             "Our DCF says \"fairly valued\" and analysts' target is <b>+8%</b>: broad "
             "agreement, a calmer setup.",
             "Our DCF says \"expensive\" but analysts say Strong Buy with a <b>+30%</b> "
             "target: the market is pricing in heavy optimism, which is upside if it plays "
             "out and downside risk if it fades."))])

    sections = [reading, factors, dcf, montecarlo, ptarget, kelly, momentum,
                regime, stops, voc, consensus]
    toc = "".join(
        f'<a href="#{sid}">{label}</a>' for sid, label in
        [("reading", "The board"), ("factors", "Factors"), ("dcf", "DCF"),
         ("montecarlo", "Monte Carlo"), ("ptarget", "P(target before stop)"),
         ("kelly", "Position sizing"), ("momentum", "Momentum"),
         ("regime", "Regime"), ("stops", "Stop study"), ("voc", "Virtue of Complexity"),
         ("consensus", "Analyst consensus")])
    back = '<a class="h-back" href="/" onclick="return goBack(event)">&larr; back to board</a>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>How to read the dashboard</title><style>{_CSS}{_INTERPRET_CSS}</style></head>
<body><div class="wrap">
<header><h1>How to read the dashboard</h1>
<p class="sub">A plain-language guide to the numbers on each card, with worked examples. Analysis, not advice.</p></header>
{back}
<nav class="toc">{toc}</nav>
{"".join(sections)}
<p class="disc">This is educational analysis, not investment advice, and not a
recommendation to buy, sell, or hold any security. Every figure is a model estimate
built on free, possibly delayed data; the decision is always yours.</p>
<div class="foot">2026 SMI Investments. All rights reserved.</div>
</div>
<script>
function goBack(e){{ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){{ try{{window.opener.focus();}}catch(_){{}}; window.close(); }}
  else location.href='/'; return false; }}
</script>
</body></html>"""
