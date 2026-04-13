#!/usr/bin/env bash
# session-stop.sh - Stop hook
#
# Fires after every Claude response.
# Writes a lightweight heartbeat to the session log so the next session
# knows this session occurred and can check for anything to consolidate.

set -euo pipefail

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', '').strip())
except:
    print('')
" 2>/dev/null || true)

[ -z "$SESSION_ID" ] && SESSION_ID="session-$$"

KB_ROOT="${KB_ROOT:-$HOME/projects/knowledge-base}"
LOG_FILE="$KB_ROOT/.kb/sessions/session-log-${SESSION_ID}.md"

mkdir -p "$KB_ROOT/.kb/sessions"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")

# Initialise log with header if it doesn't exist yet
if [ ! -f "$LOG_FILE" ]; then
    cat <<EOF > "$LOG_FILE"
---
session_id: $SESSION_ID
started: $TIMESTAMP
---

EOF
fi

# Append heartbeat timestamp
echo "<!-- active:${TIMESTAMP} -->" >> "$LOG_FILE"
