# Knowledge Base

A persistent, queryable knowledge base for AI-assisted sessions. Built on the [PARA method](https://fortelabs.com/blog/para/) for structure and [LLM Wiki V2](https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2) principles for session lifecycle.

Zero manual maintenance — sessions start with relevant context automatically loaded, and knowledge is saved during sessions without any explicit "end session" command.

---

## How it works

### Structure (PARA)

```
projects/    Active, time-bound work with a clear goal
areas/       Ongoing responsibilities with no fixed end date
resources/   Reference material, documentation, saved content
archive/     Completed projects, inactive areas, old notes
```

Each folder contains domain subfolders (e.g. `areas/backend/`, `resources/devops/`). Every note is a plain markdown file with YAML frontmatter. No proprietary syntax — files render in any editor or on GitHub.

### Session lifecycle

```
You send your first message
  → hook runs session-start.sh
  → any logs from previous sessions are output for Claude to consolidate
  → CONTEXT.md is injected into the conversation
  → Claude has context before responding

During the session
  → Claude saves notes using kb-save.sh when it encounters something worth keeping
  → session-stop.sh writes a heartbeat after each response (lightweight, ~0 tokens)

You run /clear or close Claude Code
  → session log persists on disk
  → next session start picks it up automatically
```

### Tiers

The KB supports two search modes, controlled by `.kb-config.yml` on each machine:

| Tier | Search | Dependencies |
|---|---|---|
| **Lite** | grep + YAML tag filtering | git, bash — nothing extra |
| **Full** | Lite + semantic vector search | Python, LanceDB, embeddings API |

The files are identical on all machines. Only the search layer changes.
Start with Lite. Upgrade to Full when the KB grows large enough that grep starts missing things (the system will warn you).

---

## Setup

### 1. Clone the repo

```bash
git clone git@github.com:<your-username>/knowledge-base.git ~/projects/knowledge-base
```

### 2. Create your per-machine config

```bash
cp ~/projects/knowledge-base/.kb-config.yml.example \
   ~/projects/knowledge-base/.kb-config.yml
# Edit .kb-config.yml — set tier: lite (or full) and kb_root
```

### 3. Make hook scripts executable

```bash
chmod +x ~/projects/knowledge-base/.kb/hooks/session-start.sh
chmod +x ~/projects/knowledge-base/.kb/hooks/session-stop.sh
chmod +x ~/projects/knowledge-base/.kb/scripts/*.sh
```

### 4. Register hooks in Claude Code

Add the following to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/projects/knowledge-base/.kb/hooks/session-start.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/projects/knowledge-base/.kb/hooks/session-stop.sh"
          }
        ]
      }
    ]
  }
}
```

### 5. Add the KB snippet to your CLAUDE.md

Copy the contents of `claude-snippet.md` and paste it into your `~/.claude/CLAUDE.md`
(or any project-level `CLAUDE.md`).

---

## Session workflow examples

### Starting a session

You don't need to do anything special. Just send your first message. The hook fires
automatically and injects context before Claude responds.

Example first messages:
- "Let's work on the authentication service today"
- "I need to review the deployment pipeline"
- "Can you explain how our caching layer works?"

Claude will have loaded the relevant domain context before answering.

### Saving knowledge during a session

Claude calls `/kb-save` automatically when it encounters something worth keeping.
You can also ask explicitly:

- "Save this architecture decision to the KB"
- "Add a note about this API pattern"
- "Keep this for future reference"

### Ending a session

There is no required end command. You have two natural options:

| Action | What happens |
|---|---|
| `/clear` | Conversation cleared, session log persists, next session consolidates |
| Close Claude Code | Same — log persists, picked up next time |

Both are equivalent. The KB is always up to date at the start of the next session.

### Querying the KB on demand

Ask Claude directly:
- "What do I know about X?"
- "Have we covered Y before?"
- "Show me everything related to Z"

Or run a direct search:

```bash
# Lite tier — keyword search
grep -r "keyword" ~/projects/knowledge-base/areas/

# Full tier — semantic search
python3 ~/projects/knowledge-base/.kb/full/query.py "natural language query"
python3 ~/projects/knowledge-base/.kb/full/query.py "auth middleware" --domain backend
```

---

## Adding a new domain

1. Create the folder: `areas/<domain>/` or `resources/<domain>/`
2. Claude will create `_index.md` automatically when the first note is saved
3. Add the domain to `.kb-config.yml` under `domains:` as a hint for context loading

No other configuration needed.

---

## Upgrading to Full tier

The system will warn you when the Lite tier is approaching its limits:

```
⚠️  Upgrade signal: areas/backend has 152 notes — consider enabling Full tier
```

When you see this (or when grep starts missing things you know are in the KB):

### Full tier setup

```bash
# Install Python dependencies
pip install lancedb openai python-frontmatter

# Set your embeddings API key
export OPENAI_API_KEY=sk-...
# Add to ~/.zshrc or ~/.bashrc to persist

# Build the initial vector index
python3 ~/projects/knowledge-base/.kb/full/embed.py

# Update .kb-config.yml
# tier: full
```

After that, `embed.py` keeps the index up to date (run it after bulk note additions,
or add it to the session-stop hook if you prefer automatic indexing).

### Using local embeddings (no API key)

If you prefer not to use an external API, install [Ollama](https://ollama.com) and
swap the embedding model in `embed.py` and `query.py`:

```python
# Replace the OpenAI client with:
import ollama
def embed_text(text: str) -> list[float]:
    return ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"]
```

No server needs to run permanently — Ollama starts on demand.

---

## Integrating with other workflows

Domain-specific skills (any workflow built on top of this KB) integrate by writing
session notes into `areas/<domain>/`. The KB umbrella reads them at next session
start automatically.

**No coupling required** — other skills just write to the agreed path. The KB
discovers new domains automatically.

Example: a skill that saves notes to `areas/devops/` will have those notes available
in the next general KB session without any extra configuration.

---

## File format reference

Every note follows this structure:

```markdown
---
type: resource | note | session | project
domain: <domain-name>
tags: [tag-a, tag-b]
created: 2026-04-14T10:23:45.123Z
updatedAt: 2026-04-14T10:23:45.123Z
last_referenced: 2026-04-14T10:23:45.123Z
sessions: 1
---

# Note Title

Content here.
```

All dates are ISO 8601 with milliseconds in UTC. Files are plain markdown —
no special syntax required.

---

## Concurrency

Multiple Claude instances running in parallel are safe. Each instance writes to
its own session log file (named by session ID). All writes to shared KB files go
through a POSIX filesystem lock (works on Linux and macOS). Files are written
atomically via temp file + `mv`.

---

## What this repo does NOT contain

- `.kb-config.yml` — gitignored, per-machine
- `.kb/sessions/` — gitignored, temporary session logs
- Any personal or organisation-specific content — that lives in your notes, not here
