# Knowledge Base Integration

A persistent knowledge base lives at `~/projects/knowledge-base/`.

## At session start
The `session-start.sh` hook automatically injects `CONTEXT.md` before your first
response. If previous session logs are present, consolidate them into the KB first:
read each log, extract knowledge worth persisting, call `kb-save.sh` for each item,
then proceed with the session context.

## During a session
- Load domain indexes (`areas/<domain>/_index.md`, `resources/<domain>/_index.md`)
  lazily as topics emerge — do not load all indexes upfront.
- Call `/kb-save` whenever you encounter something worth persisting: documentation,
  architecture decisions, key findings, useful patterns.
- Use `rtk grep` to search the KB when the user asks about something you don't have
  in current context.
- Log a `kb-query-miss` comment in the session log if a grep search returns no results
  for a reasonable query — this feeds the upgrade threshold check.

## Writing notes
Always use `.kb/scripts/kb-save.sh` — never write KB files directly. It handles
frontmatter, locking, index updates, and atomic writes.

```bash
echo "Note content here" | bash ~/projects/knowledge-base/.kb/scripts/kb-save.sh \
  --type note \
  --domain <domain> \
  --tags <tag1,tag2> \
  --title "Note Title"
```

## Ending a session
No explicit command needed. Run `/clear` or close Claude Code — the session log
persists and will be consolidated at the start of the next session.

## On-demand queries
The user can ask: "what do I know about X?" — search with:
```bash
# Lite tier
rtk grep "keyword" ~/projects/knowledge-base

# Full tier
python3 ~/projects/knowledge-base/.kb/full/query.py "natural language query"
```
