"""Values placed inside an inline <script>.

``json.dumps`` alone isn't enough there: the browser ends the script at the
first "</script" even inside a JS string, so a value like
``</script><script>...`` (from a URL parameter or a user's name) would run as
code. ``script_json`` escapes <, >, & and the two JS line separators.
"""

from __future__ import annotations

import json


def script_json(value) -> str:
    return (json.dumps(value, default=str).replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
