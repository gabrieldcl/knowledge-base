#!/usr/bin/env bash
# session-start.sh - UserPromptSubmit hook
#
# Fires before every user message. On the FIRST message of a session:
#   1. Consolidates any pending session logs from previous sessions
#   2. Runs upgrade threshold checks
#   3. Injects CONTEXT.md into the conversation
#
# On all subsequent messages in the same session: exits immediately (no-op).

set -euo pipefail

INPUT=$(cat)

# Extract session ID from hook JSON input
SESSION_ID=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', '').strip())
except:
    print('')
" 2>/dev/null || true)

[ -z "$SESSION_ID" ] && SESSION_ID="session-$$-$(date +%s)"

KB_ROOT="${KB_ROOT:-$HOME/projects/knowledge-base}"
FLAG_DIR="$HOME/.claude"
FLAG_FILE="$FLAG_DIR/.kb_session_${SESSION_ID}"

# Skip if not the first message of this session
[ -f "$FLAG_FILE" ] && exit 0

# Mark session as started
mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"

mkdir -p "$KB_ROOT/.kb/sessions"

SCRIPTS_DIR="$KB_ROOT/.kb/scripts"
source "$SCRIPTS_DIR/lock.sh"

# --- Consolidate pending session logs from previous sessions ---
acquire_lock

LOGS=$(ls "$KB_ROOT/.kb/sessions"/session-log-*.md 2>/dev/null || true)

if [ -n "$LOGS" ]; then
    echo ""
    echo "=== PENDING SESSION LOGS ==="
    echo "These notes were captured in previous sessions. Consolidate any new"
    echo "knowledge into the KB using kb-save.sh, then they will be cleared."
    echo ""
    for LOG in $LOGS; do
        echo "--- $(basename "$LOG") ---"
        cat "$LOG"
        echo ""
        rm -f "$LOG"
    done
    echo "=== END PENDING SESSION LOGS ==="
    echo ""
fi

release_lock

# --- Run upgrade checks ---
bash "$SCRIPTS_DIR/consolidate.sh" 2>/dev/null || true

# --- Inject CONTEXT.md ---
if [ -f "$KB_ROOT/CONTEXT.md" ]; then
    echo ""
    echo "=== KNOWLEDGE BASE CONTEXT ==="
    cat "$KB_ROOT/CONTEXT.md"
    echo "=== END KNOWLEDGE BASE CONTEXT ==="
    echo ""
fi
