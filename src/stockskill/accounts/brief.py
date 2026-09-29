"""Turn an alert's facts into a short, formal written brief before it's emailed.

The facts (every number, ticker and date) are computed by the app; Claude only
rewrites them as readable prose. A guard checks that every number in the draft
appears in the facts, so a miscounted or invented figure never reaches anyone:
if the check fails, or the API is unavailable, the email goes out as before.

On only when ANTHROPIC_API_KEY is set. STOCKSKILL_BRIEF=0 turns it off;
STOCKSKILL_BRIEF_MODEL picks another model.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import threading

MODEL = "claude-opus-5-5"
KINDS = ("summary", "event", "fund")

SYSTEM = """You write the email briefs for a stock-watchlist app. You receive the facts of one \
message (a daily market summary, a big-move alert, or a fund's new holdings filing) and rewrite \
them as a short, formal brief that reads like a note from a research desk: calm, clear, plain English.

Rules - these matter more than style:
- Use only the facts given. Do not add news, reasons, causes, forecasts, or opinions.
- Copy every number exactly as written in the facts (percentages, prices, counts, times). \
Never calculate, round, average, total, count, or compare numbers yourself, and never write a \
number (or year) that is not in the facts. Write counts only if they are given.
- Keep every ticker and name exactly as given.
- No advice: never say to buy, sell, hold, or watch something.
- Keep the greeting if there is one. Then 2 to 4 short paragraphs. A paragraph may start with a \
short bold heading followed by a period, written as **Heading.** Group related facts; lead with \
the broad market, then the reader's own stocks, then what's coming up.
- At most about 180 words. No sign-off, no subject line, no bullet lists, no emojis.

Reply with the brief only."""

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_cache: dict[str, list[str]] = {}
_lock = threading.Lock()
_client = None


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and os.environ.get("STOCKSKILL_BRIEF", "1") != "0"


def _numbers(text: str) -> set[str]:
    """Every number, without sign or thousands commas ('-1.2%' and '1.2' -> '1.2')."""
    return {m.replace(",", "") for m in _NUM.findall(text)}


def check(facts: str, draft: str) -> bool:
    """True when every number in the draft is one the facts contain."""
    return _numbers(draft) <= _numbers(facts)


def to_lines(draft: str) -> list[str]:
    """The model's plain text -> the email's paragraphs as simple HTML."""
    out = []
    for para in re.split(r"\n\s*\n", draft.strip()):
        p = html.escape(" ".join(para.split()))
        p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p)
        if p:
            out.append(p.replace("*", ""))
    return out


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(timeout=60.0, max_retries=2)
    return _client


def _write(kind: str, title: str, facts: str) -> str | None:
    client = _get_client()
    msg = client.beta.messages.create(
        model=os.environ.get("STOCKSKILL_BRIEF_MODEL") or MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Kind: {kind}\nSubject: {title}\n\nFacts:\n{facts}"}],
        output_config={"effort": "low"},
        # if the model declines, the API retries on Anthropic's recommended fallback model
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if msg.stop_reason in ("refusal", "max_tokens"):
        return None
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    return text or None


def polish(kind: str, title: str, lines: list[str]) -> list[str] | None:
    """A brief to email in place of ``lines``, or None to send ``lines`` as they are."""
    if kind not in KINDS or not lines or not enabled():
        return None
    facts = "\n".join(html.unescape(re.sub(r"<[^>]+>", "", ln)) for ln in lines)
    key = hashlib.sha256(f"{kind}\n{title}\n{facts}".encode()).hexdigest()
    with _lock:
        if key in _cache:
            return _cache[key]
    try:
        draft = _write(kind, title, facts)
    except Exception as e:  # noqa: BLE001 - never let the brief stop the email
        _log(f"brief failed ({kind}): {e!r}")
        return None
    if not draft:
        return None
    if not check(title + "\n" + facts, draft):
        _log(f"brief rejected ({kind}): numbers not in the facts {sorted(_numbers(draft) - _numbers(title + facts))}")
        return None
    out = to_lines(draft)
    with _lock:
        if len(_cache) > 500:
            _cache.clear()
        _cache[key] = out
    return out


def _log(msg: str) -> None:
    import sys
    print(f"brief: {msg}", file=sys.stderr, flush=True)
