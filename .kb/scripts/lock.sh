#!/usr/bin/env bash
# lock.sh - POSIX-compatible filesystem mutex for KB write operations
# Source this file: source "$(dirname "${BASH_SOURCE[0]}")/lock.sh"

KB_ROOT="${KB_ROOT:-$HOME/projects/knowledge-base}"
LOCK_DIR="$KB_ROOT/.kb/write.lock"
LOCK_TIMEOUT=30

acquire_lock() {
    local i=0
    while ! mkdir "$LOCK_DIR" 2>/dev/null; do
        if [ "$i" -ge "$LOCK_TIMEOUT" ]; then
            echo "[kb] Warning: stale lock detected after ${LOCK_TIMEOUT}s, removing" >&2
            rmdir "$LOCK_DIR" 2>/dev/null || true
            break
        fi
        sleep 0.5
        i=$((i + 1))
    done
}

release_lock() {
    rmdir "$LOCK_DIR" 2>/dev/null || true
}

# Write to a temp file then atomically swap — safe on all POSIX systems
atomic_write() {
    local target="$1"
    local tmp="${target}.tmp.$$"
    cat > "$tmp"
    mv "$tmp" "$target"
}
