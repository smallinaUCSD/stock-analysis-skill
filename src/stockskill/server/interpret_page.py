"""Interpret: a plain-language guide to reading the dashboard's numbers.

A static help page (opened from the board's "Interpret" button) that explains,
for a non-finance reader, what each metric is, how to read it, and the "so what".
No math here, just prose; the tested engines produce the numbers elsewhere.
"""

from __future__ import annotations

from ..dashboard.render import _CSS

_INTERPRET_CSS = """
.wrap{max-width:min(880px,100%);padding:22px clamp(16px,3vw,40px)}
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
.guide li{margin:4px 0}
.guide b{color:var(--ink)}
.h-back{display:inline-block;margin:12px 0;color:var(--muted);text-decoration:none;font-size:14px}
.h-back:hover{color:var(--ink);text-decoration:underline}
.foot{color:var(--muted);font-size:12px;text-align:center;margin:26px 0 6px;
  padding-top:14px;border-top:1px solid var(--border)}
.disc{color:var(--muted);font-size:12.5px;line-height:1.5;margin-top:14px}
"""


def _section(sid, title, lede, blocks):
    body = f'<div class="lede">{lede}</div>'
    for head, html in blocks:
        body += f'<h3>{head}</h3>{html}'
    return f'<section id="{sid}" class="guide"><h2>{title}</h2>{body}</section>'


def interpret_html() -> str:
    sections = [
        _section(
            "factors", "Factors", "Ranking a stock against its peers on five proven traits.",
            [("What it is",
              "<p>Decades of academic research find that a few measurable traits tend to line up "
              "with how stocks do over time. We score every name on the board on five of them: "
              "<b>Value</b> (is it cheap for what you get?), <b>Quality</b> (is the business strong "
              "and profitable?), <b>Momentum</b> (has it been trending up?), <b>Growth</b> (is it "
              "expanding quickly?), and <b>Low-volatility</b> (is it calm rather than wild?).</p>"),
             ("How to read it",
              "<p>Each score is a <b>0 to 100 percentile versus the other stocks on the board</b>. "
              "A Value of 90 means it is cheaper than 90% of the list; 50 is middle of the pack. The "
              "<b>Composite</b> blends the five into one score. <b>Sector-neutral</b> means \"cheap\" "
              "is judged inside a stock's own industry (a bank against banks, a chipmaker against "
              "chipmakers), so a high score is not just a bet on whichever sector happens to be "
              "cheap right now.</p>"),
             ("So what",
              "<p>A name that is cheap <b>and</b> high-quality <b>and</b> trending up (all high) has the "
              "traits that have historically paid off. One that is cheap but low-quality and falling is "
              "the classic \"value trap\". Use the scores to decide which names deserve a closer look, "
              "not as a buy button.</p>")]),
        _section(
            "dcf", "DCF (Discounted Cash Flow)", "What the business itself is worth, ignoring the hype.",
            [("What it is",
              "<p>A company is worth all the cash it will hand its owners in the future. Because a dollar "
              "ten years from now is worth less than a dollar today, DCF \"discounts\" those future cash "
              "flows back to today's money and adds them up. The result is a <b>fair value per share</b>: "
              "an estimate of what the stock is worth based on the business, not the mood of the market.</p>"),
             ("How to read it",
              "<p>If fair value sits well <b>above</b> the price, the stock looks undervalued; well "
              "<b>below</b>, overvalued. It leans on assumptions (how fast cash flow grows, the discount "
              "rate), so treat it as a reasoned estimate, not a precise truth. We also show a "
              "<b>Reverse DCF</b>, which flips the question: <i>what growth does today's price already "
              "assume?</i> If the price implies 40% growth every year for a decade, you are paying for "
              "perfection and little can go wrong.</p>"),
             ("So what",
              "<p>DCF anchors you to what the business is worth, separate from a rising or falling stock "
              "price. The interesting moments are when price and DCF disagree: that gap is the debate "
              "worth having before you act.</p>")]),
        _section(
            "montecarlo", "Monte Carlo valuation", "The DCF, but as a range of outcomes with odds.",
            [("What it is",
              "<p>A single DCF number hides how uncertain it is. Monte Carlo runs the DCF thousands of "
              "times, each time nudging the assumptions (growth, margins, discount rate) up or down at "
              "random within sensible bounds. That produces a whole <b>range of fair values</b> instead "
              "of one.</p>"),
             ("How to read it",
              "<p>We show two things. <b>P5 to P95</b> is the middle 90% of those outcomes: the low-to-high "
              "band the fair value plausibly falls in. <b>P(undervalued)</b> is the share of runs where the "
              "fair value landed above today's price. 80% means \"in about 8 of 10 plausible futures, this "
              "is worth more than you pay today\".</p>"),
             ("So what",
              "<p>It is more honest than a single number. A high P(undervalued) with a tight band is a "
              "confident \"cheap\" read. A coin-flip near 50%, or a very wide band, is the tool telling you "
              "the answer depends heavily on assumptions, so lean on the range and your own judgement.</p>")]),
        _section(
            "consensus", "Analyst consensus", "What professional analysts collectively expect.",
            [("What it is",
              "<p>Wall Street analysts publish ratings (buy / hold / sell) and price targets for the stocks "
              "they cover. The consensus is the average of those views.</p>"),
             ("How to read it",
              "<p>The <b>target vs price</b> shows the upside or downside the Street sees on average. We "
              "show it <b>separately</b> from our own valuation on purpose, because the two often disagree.</p>"),
             ("So what",
              "<p>It is a useful second opinion and a read on expectations, not truth. When our DCF says "
              "\"expensive\" but analysts say \"buy\", that gap tells you the market is pricing in a lot of "
              "optimism, which is a risk if that optimism fades.</p>")]),
        _section(
            "ptarget", "P(target before stop)", "The odds a trade reaches its target before its stop.",
            [("What it is",
              "<p>A trade setup has three prices: where you get in (entry), a <b>stop</b> below it (where you "
              "cut a loss), and a <b>target</b> above it (where you take a profit). This number estimates the "
              "probability the price touches the <b>target first</b>, before it touches the stop. It comes "
              "from the stock's recent drift and how much it bounces around (its volatility), using a classic "
              "\"first-passage\" calculation: the odds of which of two lines a wandering price hits first.</p>"),
             ("How to read it",
              "<p>60% means that, given how this stock has been moving, reaching the target first is more "
              "likely than getting stopped out. Below 50% and the odds favor the stop. It assumes the "
              "recent trend and volatility continue, so it is an estimate of the edge, not a promise.</p>"),
             ("So what",
              "<p>It turns a stop and target into an honest edge estimate, and it feeds the position sizing: "
              "a bigger edge justifies a bigger position (the \"half-Kelly\" figure), and if the edge is not "
              "positive, the tool says to pass on the trade rather than force it.</p>")]),
        _section(
            "regime", "Regime and stop study", "Is the stock trending, and would a stop have helped it?",
            [("Regime (P bull)",
              "<p>A model reads whether a stock is in an up-trending (\"bull\") or down-trending (\"bear\") "
              "phase and reports it as a probability. A high <b>P(bull)</b> means the evidence says the "
              "up-trend is probably still intact; a low one warns the trend may have turned. The regime is "
              "inferred from prices, so read it as a considered opinion, not a certainty.</p>"),
             ("Stop study",
              "<p>This backtests whether a trailing stop-loss would actually have <b>helped or hurt</b> this "
              "specific stock in the past. Research shows stops tend to help names that trend cleanly but "
              "hurt choppy ones (you get whipsawed out and miss the rebound). \"Helped +3%/yr\" or "
              "\"hurt -6%/yr\" tells you which kind this stock has been.</p>")]),
    ]
    toc = "".join(
        f'<a href="#{sid}">{label}</a>' for sid, label in
        [("factors", "Factors"), ("dcf", "DCF"), ("montecarlo", "Monte Carlo"),
         ("consensus", "Analyst consensus"), ("ptarget", "P(target before stop)"),
         ("regime", "Regime &amp; stops")])
    back = '<a class="h-back" href="/" onclick="return goBack(event)">← back to board</a>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>How to read the dashboard</title><style>{_CSS}{_INTERPRET_CSS}</style></head>
<body><div class="wrap">
<header><h1>How to read the dashboard</h1>
<p class="sub">A plain-language guide to the numbers on each card. Analysis, not advice.</p></header>
{back}
<nav class="toc">{toc}</nav>
{"".join(sections)}
<p class="disc">This is educational analysis, not investment advice, and not a
recommendation to buy, sell, or hold any security. Every figure is a model estimate
built on free, possibly delayed data; the decision is always yours.</p>
{back}
<div class="foot">2026 SMI Investments. All rights reserved.</div>
</div>
<script>
function goBack(e){{ if(e) e.preventDefault();
  if(window.opener && !window.opener.closed){{ try{{window.opener.focus();}}catch(_){{}}; window.close(); }}
  else location.href='/'; return false; }}
</script>
</body></html>"""
