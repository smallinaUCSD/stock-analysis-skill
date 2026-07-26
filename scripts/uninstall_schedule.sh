#!/bin/bash
# Remove the stockskill dashboard cron entry (leaves all other crontab lines).
set -euo pipefail
MARK="# stockskill-dashboard"
if crontab -l 2>/dev/null | grep -q "$MARK"; then
    crontab -l 2>/dev/null | grep -v "$MARK" | crontab -
    echo "Removed the stockskill dashboard schedule."
else
    echo "No stockskill dashboard schedule found; nothing to do."
fi
