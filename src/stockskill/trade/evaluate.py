"""Evaluate a proposed trade against the tool's analysis -- an alignment
scorecard, NOT a yes/no recommendation.

You describe a trade (buy/sell/short a ticker, optional stop/target); this scores
it factor-by-factor (valuation, technical signal, trend, RSI, analyst consensus,
risk/reward) as supporting, against, or neutral, and summarizes how well the
trade lines up with the evidence. The decision stays yours.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Factor:
    name: str
    stance: str      # support | against | neutral
    detail: str


@dataclass
class TradeEval:
    ticker: str
    action: str      # BUY | SELL | SHORT
    price: float | None
    factors: list = field(default_factory=list)
    rr: float | None = None
    alignment: str = ""

    @property
    def n_support(self):
        return sum(1 for f in self.factors if f.stance == "support")

    @property
    def n_against(self):
        return sum(1 for f in self.factors if f.stance == "against")


def _bullish(action: str) -> bool:
    return action == "BUY"


def evaluate_trade(ticker: str, action: str, price: float | None,
                   *, valuation_mos: float | None = None, valuation_signal: str | None = None,
                   tech_signal: str | None = None, trend_score: float | None = None,
                   rsi: float | None = None, consensus_reco: str | None = None,
                   consensus_target_vs_price: float | None = None,
                   stop: float | None = None, target: float | None = None) -> TradeEval:
    action = action.upper()
    bull = _bullish(action)
    ev = TradeEval(ticker.upper(), action, price)
    f = ev.factors.append

    # 1) valuation: undervalued supports a buy, overvalued supports a short
    if valuation_mos is not None:
        under = valuation_mos > 0.05
        over = valuation_mos < -0.05
        if (bull and under) or (not bull and over):
            f(Factor("Valuation", "support",
                     f"{'below' if under else 'above'} fair value ({valuation_mos:+.0%})"))
        elif (bull and over) or (not bull and under):
            f(Factor("Valuation", "against",
                     f"{'above' if over else 'below'} fair value ({valuation_mos:+.0%})"))
        else:
            f(Factor("Valuation", "neutral", f"roughly fair ({valuation_mos:+.0%})"))
    elif valuation_signal:
        f(Factor("Valuation", "neutral", valuation_signal))

    # 2) technical signal alignment
    if tech_signal:
        if tech_signal == action:
            f(Factor("Technical signal", "support", f"strategy also says {tech_signal}"))
        elif tech_signal in ("BUY", "SHORT", "SELL") and tech_signal != action:
            f(Factor("Technical signal", "against", f"strategy says {tech_signal}"))
        else:
            f(Factor("Technical signal", "neutral", "strategy is HOLD"))

    # 3) trend direction
    if trend_score is not None:
        up = trend_score >= 1.5
        down = trend_score <= -1.5
        if (bull and up) or (not bull and down):
            f(Factor("Trend", "support", f"trend {trend_score:+.0f} agrees"))
        elif (bull and down) or (not bull and up):
            f(Factor("Trend", "against", f"trend {trend_score:+.0f} opposes (fighting the tape)"))
        else:
            f(Factor("Trend", "neutral", f"trend {trend_score:+.0f} (flat)"))

    # 4) RSI (momentum extreme)
    if rsi is not None:
        if bull and rsi <= 35:
            f(Factor("RSI", "support", f"oversold ({rsi:.0f}) — mean-reversion for a long"))
        elif bull and rsi >= 70:
            f(Factor("RSI", "against", f"overbought ({rsi:.0f}) — chasing"))
        elif not bull and rsi >= 65:
            f(Factor("RSI", "support", f"overbought ({rsi:.0f}) — mean-reversion for a short"))
        elif not bull and rsi <= 30:
            f(Factor("RSI", "against", f"oversold ({rsi:.0f})"))
        else:
            f(Factor("RSI", "neutral", f"{rsi:.0f}"))

    # 5) analyst consensus
    if consensus_reco and consensus_reco != "n/a":
        rl = consensus_reco.lower()
        bullish_reco = "buy" in rl
        bearish_reco = "sell" in rl
        if (bull and bullish_reco) or (not bull and bearish_reco):
            f(Factor("Analyst consensus", "support", consensus_reco))
        elif (bull and bearish_reco) or (not bull and bullish_reco):
            f(Factor("Analyst consensus", "against", consensus_reco))
        else:
            f(Factor("Analyst consensus", "neutral", consensus_reco))

    # 6) risk / reward if a stop & target were given
    if price and stop and target:
        risk = abs(price - stop)
        reward = abs(target - price)
        ev.rr = (reward / risk) if risk else None
        if ev.rr is not None:
            if ev.rr >= 2:
                f(Factor("Risk/reward", "support", f"{ev.rr:.1f}:1"))
            elif ev.rr < 1:
                f(Factor("Risk/reward", "against", f"{ev.rr:.1f}:1 (risking more than the reward)"))
            else:
                f(Factor("Risk/reward", "neutral", f"{ev.rr:.1f}:1"))

    net = ev.n_support - ev.n_against
    if net >= 2:
        ev.alignment = "well aligned — the evidence mostly supports this trade"
    elif net <= -2:
        ev.alignment = "poorly aligned — the evidence mostly points the other way"
    else:
        ev.alignment = "mixed — the evidence is split; size accordingly"
    return ev
