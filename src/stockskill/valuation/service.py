"""Turn a fundamentals snapshot + assumptions into a fair-value report.

This is what powers "what is this stock actually worth?". Given a
:class:`~stockskill.data.fundamentals.FundamentalSnapshot` and a set of
explicit :class:`Assumptions`, it runs every method the data supports (DCF,
reverse DCF, relative multiples, dividend discount) and returns a
:class:`~stockskill.valuation.engine.ValuationReport` with a low/base/high
range and margin of safety.

Deterministic: identical (snapshot, assumptions) -> identical report. The
assumptions are the *only* subjective inputs, and they are explicit and
logged -- never guessed silently by a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..data.fundamentals import FundamentalSnapshot
from .dcf import DCFInputs, two_stage_dcf
from .reverse_dcf import implied_stage1_growth
from .multiples import MultiplesInputs, value_from_multiples, blended_multiples_value
from .ddm import gordon_growth_value
from .engine import ValuationReport, capm_cost_of_equity


@dataclass
class Assumptions:
    """Explicit, logged valuation assumptions (the only subjective inputs)."""

    risk_free: float = 0.043
    equity_premium: float = 0.05
    default_beta: float = 1.1              # used only if snapshot has no beta
    min_discount_rate: float = 0.08        # floor: a low beta can't imply a sub-8% equity rate
    stage1_growth: float = 0.08            # base-case FCF growth (year 1 if fading)
    stage1_years: int = 10
    terminal_growth: float = 0.025
    # Fade is available but OFF by default: with the discount-rate floor and the
    # data-driven growth, a plain two-stage DCF tracks analyst targets well;
    # fading on top pushes fair values systematically ~50% too low. Opt in per
    # name when you want an explicitly conservative, decelerating-growth view.
    fade_growth: bool = False              # taper growth toward a mature rate over the window
    fade_floor: float = 0.045              # "mature" growth the fade lands on at year N
    # method weights in the blended base case
    weight_dcf: float = 0.45
    weight_multiples: float = 0.35
    weight_ddm: float = 0.20
    # peer multiples for relative valuation (supply from data layer / peers)
    peer_pe: float | None = None
    peer_ev_ebitda: float | None = None
    peer_ps: float | None = None
    # dividend growth for the Gordon model
    dividend_growth: float = 0.05
    # minimum current yield for DDM to be included in the blend
    min_ddm_yield: float = 0.01


@dataclass
class ValuationOutput:
    report: ValuationReport
    discount_rate: float
    implied_market_growth: float | None = None
    assumptions_used: Assumptions = field(default_factory=Assumptions)
    warnings: list[str] = field(default_factory=list)
    dcf_inputs: DCFInputs | None = None      # for sensitivity analysis in the CLI
    terminal_value_pct: float | None = None  # share of EV from the terminal value


def value_snapshot(snap: FundamentalSnapshot, a: Assumptions | None = None) -> ValuationOutput:
    a = a or Assumptions()
    warnings: list[str] = []

    if snap.price is None:
        warnings.append("no price in snapshot; margin of safety unavailable")
    report = ValuationReport(ticker=snap.ticker, price=snap.price or float("nan"))

    beta = snap.beta if snap.beta is not None else a.default_beta
    if snap.beta is None:
        warnings.append(f"no beta in snapshot; used default {a.default_beta}")
    capm = capm_cost_of_equity(a.risk_free, beta, a.equity_premium)
    discount_rate = max(capm, a.min_discount_rate)
    if capm < a.min_discount_rate:
        warnings.append(f"CAPM rate {capm:.1%} (beta {beta:.2f}) floored to {a.min_discount_rate:.1%}")

    implied_growth = None
    dcf_inputs_used: DCFInputs | None = None
    terminal_pct: float | None = None

    # --- DCF + reverse DCF ---
    # Prefer free cash flow. If FCF is missing/negative (e.g. a profitable
    # company in a heavy-capex phase), fall back to net income as a cash-flow
    # PROXY so we can still value it -- labeled distinctly and flagged as rougher.
    flow0 = None
    flow_label = None
    if snap.fcf and snap.fcf > 0:
        flow0, flow_label = snap.fcf, "DCF"
    elif snap.eps and snap.shares and snap.eps > 0:
        flow0, flow_label = snap.eps * snap.shares, "DCF (earnings)"

    if flow0 and snap.shares:
        dcf_inp = DCFInputs(
            fcf0=flow0,
            shares=snap.shares,
            net_debt=snap.net_debt or 0.0,
            discount_rate=discount_rate,
            stage1_growth=a.stage1_growth,
            stage1_years=a.stage1_years,
            terminal_growth=a.terminal_growth,
            fade=a.fade_growth,
            fade_to=a.fade_floor,
        )
        try:
            dcf = two_stage_dcf(dcf_inp)
            dcf_inputs_used = dcf_inp
            terminal_pct = dcf.terminal_value_pct
            fade_txt = "faded" if a.fade_growth else "flat"
            note = (f"g1={a.stage1_growth:.0%} ({fade_txt}), r={discount_rate:.1%}, "
                    f"terminal={dcf.terminal_value_pct:.0%} of EV")
            if flow_label == "DCF (earnings)":
                note += "; net income used (FCF negative/NA)"
                warnings.append("FCF negative/unavailable; DCF run on net income as a proxy")
            report.add(flow_label, dcf.fair_value_per_share, a.weight_dcf, note=note)
            if snap.price:
                implied_growth = implied_stage1_growth(snap.price, dcf_inp)
        except ValueError as e:
            warnings.append(f"DCF skipped: {e}")
    else:
        warnings.append("DCF skipped: no positive FCF or EPS")

    # --- Relative multiples (needs peer multiples + matching metrics) ---
    if snap.shares and any([a.peer_pe, a.peer_ev_ebitda, a.peer_ps]):
        m_inp = MultiplesInputs(
            shares=snap.shares, net_debt=snap.net_debt or 0.0,
            eps=snap.eps, ebitda=snap.ebitda, revenue=snap.revenue,
        )
        m_vals = value_from_multiples(
            m_inp, pe=a.peer_pe, ev_ebitda=a.peer_ev_ebitda, ps=a.peer_ps,
        )
        blended = blended_multiples_value(m_vals)
        if blended is not None:
            report.add("Multiples", blended, a.weight_multiples,
                       note=", ".join(f"{k}:{v:.0f}" for k, v in m_vals.items()))
    else:
        warnings.append("Multiples skipped: no peer multiples supplied")

    # --- Dividend discount (only for real payers) ---
    # A token dividend (buyback-heavy names) makes a DDM value that badly
    # understates the business; giving it weight drags the blend down. Only
    # include DDM when the current yield is material (>= min_ddm_yield).
    div_yield = (snap.dividend_annual / snap.price) if (snap.dividend_annual and snap.price) else 0.0
    if snap.dividend_annual and snap.dividend_annual > 0 and div_yield >= a.min_ddm_yield:
        d1 = snap.dividend_annual * (1.0 + a.dividend_growth)
        if discount_rate > a.dividend_growth:
            ddm_val = gordon_growth_value(d1, discount_rate, a.dividend_growth)
            report.add("DDM", ddm_val, a.weight_ddm,
                       note=f"yield={div_yield:.1%}, D1={d1:.2f}, g={a.dividend_growth:.0%}")
        else:
            warnings.append("DDM skipped: discount_rate <= dividend_growth")
    elif snap.dividend_annual and div_yield < a.min_ddm_yield:
        warnings.append(
            f"DDM excluded: yield {div_yield:.1%} < {a.min_ddm_yield:.0%} "
            "(buyback-heavy name; DDM would understate value)")

    return ValuationOutput(
        report=report,
        discount_rate=discount_rate,
        implied_market_growth=implied_growth,
        assumptions_used=a,
        warnings=warnings,
        dcf_inputs=dcf_inputs_used,
        terminal_value_pct=terminal_pct,
    )
