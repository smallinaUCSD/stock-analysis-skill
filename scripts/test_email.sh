#!/usr/bin/env bash
# Send one test email with the SMTP settings in .env and show the result.
#   ./scripts/test_email.sh you@example.com
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
[ -f .env ] && { . scripts/load_env.sh; load_env; }
TO="${1:-${SMTP_USER:-}}"
[ -n "$TO" ] || { echo "usage: $0 you@example.com"; exit 1; }
echo "SMTP_HOST=${SMTP_HOST:-<missing>}  SMTP_PORT=${SMTP_PORT:-587}  SMTP_USER=${SMTP_USER:-<missing>}"
pw="${SMTP_PASSWORD:-}"; pw="${pw// /}"
echo "SMTP_PASSWORD: ${#pw} characters (a Gmail app password is 16)"
uv run python - "$TO" <<'PY'
import sys
from stockskill.accounts import notify as N
if not N.email_ready():
    sys.exit("Not configured: SMTP_HOST, SMTP_USER and SMTP_PASSWORD must all be set in .env")
ok = N.send_email(sys.argv[1], "StockSkill test email", "If you can read this, email sending works.")
print("Sent. Check the inbox (and spam) of " + sys.argv[1] if ok else "FAILED: " + (N.LAST_ERROR["msg"] or "unknown error"))
PY
