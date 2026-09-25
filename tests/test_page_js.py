"""Every inline script on the account pages parses (catches broken escaping,
which the Python tests can't see). Skipped when Node.js isn't installed."""

import re
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node not installed")


def _pages():
    from stockskill.accounts import pages as P
    from stockskill.server import politician_page as PP
    return {"landing": P.landing_html(), "login": P.login_html("login", "cid"), "signup": P.login_html("signup"),
            "welcome": P.welcome_html(), "account": P.account_html(), "terms": P.legal_html("terms"),
            "board": P.personalize_board("<html><head></head><body><div class='bar'></div><div class='top-r'></div>"
                                         "</body></html>", {"first_name": "Ada"}, ["AAPL"]),
            "politician": PP.politician_html("x"), "sw": "<script>" + P.SERVICE_WORKER + "</script>"}


@pytest.mark.parametrize("name", list(_pages()))
def test_inline_scripts_parse(name, tmp_path):
    for i, js in enumerate(re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", _pages()[name], re.S)):
        if not js.strip():
            continue
        f = tmp_path / f"{name}_{i}.js"
        f.write_text(js)
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{name} script {i}: {r.stderr[:400]}"
