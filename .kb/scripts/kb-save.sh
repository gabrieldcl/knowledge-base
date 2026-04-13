#!/usr/bin/env bash
# kb-save.sh - Write a note to the knowledge base
#
# Usage:
#   echo "content" | kb-save.sh --type <type> --domain <domain> --tags <tag1,tag2> --title <title>
#
# Arguments:
#   --type    resource | note | session | project  (default: note)
#   --domain  domain name matching an areas/ or resources/ subfolder  (default: general)
#   --tags    comma-separated list of tags  (default: none)
#   --title   note title (required)

set -euo pipefail

KB_ROOT="${KB_ROOT:-$HOME/projects/knowledge-base}"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPTS_DIR/lock.sh"

TYPE="note"
DOMAIN="general"
TAGS=""
TITLE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)   TYPE="$2";   shift 2 ;;
        --domain) DOMAIN="$2"; shift 2 ;;
        --tags)   TAGS="$2";   shift 2 ;;
        --title)  TITLE="$2";  shift 2 ;;
        *) shift ;;
    esac
done

if [ -z "$TITLE" ]; then
    echo "[kb] Error: --title is required" >&2
    exit 1
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE_PREFIX=$(date -u +"%Y-%m-%d")
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr -s ' ' '-' | tr -cd '[:alnum:]-')

# Determine target directory based on type
case "$TYPE" in
    project)  TARGET_DIR="$KB_ROOT/projects/$DOMAIN" ;;
    resource) TARGET_DIR="$KB_ROOT/resources/$DOMAIN" ;;
    *)        TARGET_DIR="$KB_ROOT/areas/$DOMAIN" ;;
esac

mkdir -p "$TARGET_DIR"
NOTE_PATH="$TARGET_DIR/${DATE_PREFIX}-${SLUG}.md"

# Read content from stdin
CONTENT=$(cat)

# Format tags as YAML sequence
if [ -n "$TAGS" ]; then
    TAGS_YAML="[$(echo "$TAGS" | sed 's/,/, /g')]"
else
    TAGS_YAML="[]"
fi

# Write note under lock
acquire_lock

cat <<EOF | atomic_write "$NOTE_PATH"
---
type: $TYPE
domain: $DOMAIN
tags: $TAGS_YAML
created: $TIMESTAMP
updatedAt: $TIMESTAMP
last_referenced: $TIMESTAMP
sessions: 1
---

# $TITLE

$CONTENT
EOF

# Update domain _index.md
INDEX_FILE="$TARGET_DIR/_index.md"
if [ ! -f "$INDEX_FILE" ]; then
    cat <<EOF | atomic_write "$INDEX_FILE"
# Index: $DOMAIN

## Notes
EOF
fi

ENTRY="- [${TITLE}](./${DATE_PREFIX}-${SLUG}.md) — ${TIMESTAMP}"
if ! grep -qF "$SLUG" "$INDEX_FILE" 2>/dev/null; then
    echo "$ENTRY" >> "$INDEX_FILE"
fi

# Update parent _index.md with domain entry if missing
PARENT_INDEX="$(dirname "$TARGET_DIR")/_index.md"
if [ -f "$PARENT_INDEX" ] && ! grep -qF "$DOMAIN" "$PARENT_INDEX" 2>/dev/null; then
    echo "- $DOMAIN" >> "$PARENT_INDEX"
fi

# Update CONTEXT.md last updated timestamp
if [ -f "$KB_ROOT/CONTEXT.md" ]; then
    sed -i.bak "s|^Last updated:.*|Last updated: $TIMESTAMP|" "$KB_ROOT/CONTEXT.md" \
        && rm -f "$KB_ROOT/CONTEXT.md.bak"
fi

release_lock

echo "[kb] Saved: $NOTE_PATH" >&2
