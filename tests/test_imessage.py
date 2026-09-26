"""Texts as iMessages from the Mac mini: the site queues a file, the helper
(scripts/macmini/imessage_relay.sh) sends it through Messages. Messages is
replaced by a fake osascript that records what it was asked to send."""

import os
import shutil
import stat
import subprocess
import time

import pytest

from stockskill.accounts import sms as S

RELAY = os.path.join(os.path.dirname(__file__), "..", "scripts", "macmini", "imessage_relay.sh")


@pytest.fixture
def spool(tmp_path, monkeypatch):
    d = tmp_path / "spool"
    (d / "outbox").mkdir(parents=True)
    monkeypatch.setenv("STOCKSKILL_IMESSAGE_DIR", str(d))
    for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM", "TWILIO_MESSAGING_SERVICE_SID"):
        monkeypatch.delenv(k, raising=False)
    return d


def test_provider_follows_the_helpers_heartbeat(spool, monkeypatch):
    assert S.provider() is None and not S.sms_ready()
    (spool / "heartbeat").touch()
    assert S.provider() == "imessage"
    old = time.time() - 600
    os.utime(spool / "heartbeat", (old, old))                       # helper stopped
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "t")
    monkeypatch.setenv("TWILIO_FROM", "+18885550100")
    assert S.provider() == "twilio"


def test_send_queues_one_file_per_message(spool):
    (spool / "heartbeat").touch()
    assert S.send_sms("+14155550134", "SM Investments: NVDA is up 6%.\nReply STOP to opt out.") == (True, None)
    assert S.send_sms("12345", "x")[0] is False
    files = list((spool / "outbox").glob("*.msg"))
    assert len(files) == 1
    assert files[0].read_text() == "+14155550134\nSM Investments: NVDA is up 6%.\nReply STOP to opt out."
    assert stat.S_IMODE(files[0].stat().st_mode) == 0o660          # the helper's user can read it (group)


@pytest.mark.skipif(not shutil.which("zsh"), reason="zsh not installed")
def test_relay_sends_and_keeps_failures(spool, tmp_path):
    log = tmp_path / "sent.txt"
    fake = tmp_path / "osascript"
    fake.write_text('#!/bin/sh\n[ "$2" = "+15550000000" ] && { echo "not an iMessage user" >&2; exit 1; }\n'
                    f'printf "%s|%s\\n" "$2" "$3" >> "{log}"\n')
    fake.chmod(0o755)
    (spool / "outbox" / "a.msg").write_text("+14155550134\nline one\nline two")
    (spool / "outbox" / "b.msg").write_text("+15550000000\nwon't go")
    (spool / "outbox" / "c.msg").write_text("not-a-number\nx")
    env = dict(os.environ, OSASCRIPT=str(fake), STOCKSKILL_IMESSAGE_DIR=str(spool))
    subprocess.run(["zsh", RELAY, "--once"], env=env, check=True, timeout=30)
    assert log.read_text() == "+14155550134|line one\nline two\n"
    assert list((spool / "outbox").glob("*.msg")) == []              # sent ones are deleted
    assert "not an iMessage user" in (spool / "failed" / "b.msg.err").read_text()
    assert (spool / "failed" / "c.msg.err").read_text().strip() == "bad number"
    assert (spool / "heartbeat").exists()
