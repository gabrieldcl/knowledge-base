#!/usr/bin/env bash
# consolidate.sh - Check upgrade thresholds and surface warnings into CONTEXT.md
# Called at session start by session-start.sh.

set -euo pipefail

KB_ROOT="${KB_ROOT:-$HOME/projects/knowledge-base}"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPTS_DIR/lock.sh"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")
CONTEXT="$KB_ROOT/CONTEXT.md"
WARN=0

check_upgrade_warnings() {
    local warnings=""

    # Check note count per domain index (threshold: 150 notes)
    while IFS= read -r index; do
        local count
        count=$(grep -c "^-" "$index" 2>/dev/null || echo 0)
        if [ "$count" -gt 150 ]; then
            warnings+="⚠️  Upgrade signal: $(dirname "$index" | sed "s|$KB_ROOT/||") has $count notes — consider enabling Full tier for semantic search.\n"
            WARN=1
        fi
    done < <(find "$KB_ROOT/areas" "$KB_ROOT/resources" -name "_index.md" 2>/dev/null)

    # Write warnings into CONTEXT.md Signals section if any
    if [ -n "$warnings" ]; then
        acquire_lock
        # Replace Signals section content
        local tmp="${CONTEXT}.tmp.$$"
        awk -v w="$warnings" '
            /^## Signals/ { print; print w; found=1; next }
            found && /^## / { found=0 }
            !found { print }
        ' "$CONTEXT" > "$tmp"
        mv "$tmp" "$CONTEXT"
        release_lock
    fi
}

check_upgrade_warnings
