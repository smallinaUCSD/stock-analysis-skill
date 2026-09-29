"""The LLM-written email brief: the number guard, the fallback to the plain
template, and the wiring into deliver(). The Claude client is faked."""

from types import SimpleNamespace

import pytest

from stockskill.accounts import brief as B

LINES = ["Good morning, Ana. All changes are for the last session.",
         "<b>Markets yesterday:</b> S&amp;P 500 <b>+0.4%</b> · Nasdaq <b>-1.2%</b>",
         "<b>Your biggest gainers:</b> NVDA +3.1%, AMD +2.0%"]


class Fake:
    def __init__(self, text, stop="end_turn"):
        self.text, self.stop, self.calls = text, stop, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason=self.stop, content=[SimpleNamespace(type="text", text=self.text)])


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    for k in ("STOCKSKILL_BRIEF", "HF_TOKEN", "STOCKSKILL_LLM_URL"):
        monkeypatch.delenv(k, raising=False)
    B._cache.clear()

    def use(text, stop="end_turn"):
        f = Fake(text, stop)
        monkeypatch.setattr(B, "_client", f)
        return f
    return use


def test_guard():
    facts = "S&P 500 +0.4% · Nasdaq -1.2% · NVDA +3.1% at 8:30am"
    assert B.check(facts, "The S&P 500 rose 0.4% while the Nasdaq fell 1.2%; data at 8:30 a.m.")
    assert not B.check(facts, "The two indexes averaged -0.4%, and NVDA gained 3.2%.")   # 3.2 isn't a fact
    assert not B.check(facts, "Two of your 5 stocks rose.")                               # a count it made up


def test_polish_writes_a_brief(fake):
    f = fake("Good morning, Ana.\n\n**Markets.** The S&P 500 gained 0.4% while the Nasdaq slipped 1.2%.\n\n"
             "**Your stocks.** NVDA led with +3.1%, followed by AMD at +2.0%.")
    out = B.polish("summary", "Before the bell · Tue Sep 29", LINES)
    assert out[1].startswith("<b>Markets.</b> The S&amp;P 500") and len(out) == 3
    kw = f.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "S&P 500 +0.4%" in kw["messages"][0]["content"]                 # tags stripped, entities decoded
    B.polish("summary", "Before the bell · Tue Sep 29", LINES)
    assert len(f.calls) == 1                                                # same facts: cached


def test_polish_falls_back(fake, monkeypatch):
    fake("The S&P 500 gained 0.5%.")                                        # a changed number
    assert B.polish("summary", "t", LINES) is None
    fake("", stop="refusal")
    assert B.polish("summary", "t2", LINES) is None
    assert B.polish("trade", "t3", LINES) is None                           # short alerts stay as they are
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert B.polish("summary", "t4", LINES) is None

    def boom(**kw):
        raise RuntimeError("down")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(B, "_client", SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=boom))))
    assert B.polish("summary", "t5", LINES) is None


def test_deliver_emails_the_brief(fake, monkeypatch, tmp_path):
    monkeypatch.setenv("STOCKSKILL_DB", str(tmp_path / "users.db"))
    from stockskill.accounts import db, notify
    db.init()
    uid = db.create_user("ana@example.com", "a-long-password-1")
    u = {**db.get_user(uid), "notify_email": 1, "email_verified": 1}
    sent = {}
    monkeypatch.setattr(notify, "send_email", lambda to, subj, text, htm, **k: sent.update(text=text, html=htm) or True)
    fake("**Markets.** The S&P 500 gained 0.4% and the Nasdaq fell 1.2%.")
    notify.deliver(u, "summary", "Before the bell · Tue Sep 29", LINES, "/", "sum:x")
    assert "<b>Markets.</b>" in sent["html"] and "gained 0.4%" in sent["text"]
    assert "Your biggest gainers" in db.notifications(uid)[0]["body"]       # the in-app copy keeps the facts


def test_hugging_face_and_local(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "STOCKSKILL_BRIEF", "STOCKSKILL_LLM_URL", "STOCKSKILL_HF_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    B._cache.clear()
    seen = []

    def post(url, json=None, headers=None, timeout=None):
        seen.append((url, json, headers))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"choices": [{"finish_reason": "stop", "message": {
            "content": "<think>add them up</think>**Markets.** The S&P 500 rose 0.4%; the Nasdaq fell 1.2%."}}]})
    import requests
    monkeypatch.setattr(requests, "post", post)
    out = B.polish("event", "Big moves", LINES)
    assert out == ["<b>Markets.</b> The S&amp;P 500 rose 0.4%; the Nasdaq fell 1.2%."]      # reasoning notes dropped
    url, body, headers = seen[0]
    assert url == "https://router.huggingface.co/v1/chat/completions" and body["model"] == B.HF_MODEL
    assert headers == {"Authorization": "Bearer hf_test"} and body["messages"][0]["content"] == B.SYSTEM
    monkeypatch.delenv("HF_TOKEN")
    monkeypatch.setenv("STOCKSKILL_LLM_URL", "http://localhost:11434/v1/")
    assert B.backend() == ("openai", "http://localhost:11434/v1", "qwen3:8b")
    B.polish("event", "Other", LINES)
    assert seen[1][0] == "http://localhost:11434/v1/chat/completions" and seen[1][2] == {}    # no key sent to a local server


def test_name_never_leaves_the_server(fake):
    lines = ["Good morning, Ana. All changes are for the last session.", "<b>Markets:</b> S&amp;P 500 <b>+0.4%</b>"]
    f = fake("Good morning, [NAME].\n\n**Markets.** The S&P 500 rose 0.4%.")
    assert B.polish("summary", "t", lines, "Ana")[0] == "Good morning, Ana."
    assert "Ana" not in f.calls[0]["messages"][0]["content"]
    assert B.polish("summary", "t", ["Good morning, Raj. All changes are for the last session.", lines[1]],
                    "Raj")[0] == "Good morning, Raj."                     # same facts: cached, own name
    assert len(f.calls) == 1
