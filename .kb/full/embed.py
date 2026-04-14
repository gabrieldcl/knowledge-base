#!/usr/bin/env python3
"""
embed.py - Index KB notes into a LanceDB vector database (Full tier).

Scans all markdown files in the KB, embeds any that are new or updated,
and stores them in a local LanceDB table at .kb/full/index/.

Embedding provider is selected via the EMBED_PROVIDER env var:
  - "voyage" (default) — Voyage AI, Anthropic's recommended embedding partner.
                         Best for code. Free tier: 200M tokens/month.
                         Get a key at https://www.voyageai.com
  - "openai"           — OpenAI text-embedding-3-small. Pay-per-token.

Note: Anthropic's Claude API key cannot be used for embeddings — Claude is a
generative model only. Voyage AI is Anthropic's recommended embedding solution.

Requirements:
    pip install lancedb python-frontmatter voyageai   # Voyage (default)
    pip install lancedb python-frontmatter openai     # OpenAI

Environment:
    VOYAGE_API_KEY  - required when EMBED_PROVIDER=voyage (default)
    OPENAI_API_KEY  - required when EMBED_PROVIDER=openai
    EMBED_PROVIDER  - "voyage" (default) or "openai"
    KB_ROOT         - path to knowledge base root (default: ~/projects/knowledge-base)

Usage:
    python3 embed.py              # index all new/changed notes
    python3 embed.py --rebuild    # drop and rebuild the full index
"""

import os
import sys
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone

EMBED_PROVIDER = os.environ.get("EMBED_PROVIDER", "voyage")

try:
    import frontmatter
    import lancedb
    if EMBED_PROVIDER == "openai":
        import openai
    else:
        import voyageai
except ImportError as e:
    print(f"[kb] Missing dependency: {e}")
    if EMBED_PROVIDER == "openai":
        print("[kb] Run: pip install lancedb openai python-frontmatter")
    else:
        print("[kb] Run: pip install lancedb voyageai python-frontmatter")
    sys.exit(1)

KB_ROOT = Path(os.environ.get("KB_ROOT", Path.home() / "projects/knowledge-base"))
INDEX_DIR = KB_ROOT / ".kb" / "full" / "index"

if EMBED_PROVIDER == "openai":
    _client = openai.OpenAI()
    EMBED_MODEL = "text-embedding-3-small"
else:
    _client = voyageai.Client()
    EMBED_MODEL = "voyage-code-3"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts in a single API call."""
    if EMBED_PROVIDER == "openai":
        response = _client.embeddings.create(input=texts, model=EMBED_MODEL)
        return [r.embedding for r in response.data]
    else:
        result = _client.embed(texts, model=EMBED_MODEL)
        return result.embeddings


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def collect_notes() -> list[dict]:
    notes = []
    for md_file in KB_ROOT.rglob("*.md"):
        # Skip index files, CONTEXT.md, and session logs
        if md_file.name.startswith("_") or md_file.name == "CONTEXT.md":
            continue
        if ".kb" in md_file.parts:
            continue
        try:
            post = frontmatter.load(str(md_file))
            notes.append({
                "path": str(md_file.relative_to(KB_ROOT)),
                "title": post.get("title") or md_file.stem.replace("-", " ").title(),
                "type": post.get("type", "note"),
                "domain": post.get("domain", "general"),
                "tags": ",".join(post.get("tags", [])),
                "updated_at": str(post.get("updatedAt", "")),
                "content": post.content[:4000],  # cap to avoid token limits
                "hash": file_hash(md_file),
            })
        except Exception as e:
            print(f"[kb] Skipping {md_file}: {e}", file=sys.stderr)
    return notes


def run(rebuild: bool = False):
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(INDEX_DIR))

    existing_hashes: dict[str, str] = {}

    if rebuild and "notes" in db.list_tables():
        db.drop_table("notes")
        print("[kb] Dropped existing index for rebuild")

    if "notes" in db.list_tables():
        table = db.open_table("notes")
        for row in table.to_pandas().itertuples():
            existing_hashes[row.path] = row.hash

    notes = collect_notes()
    to_index = [n for n in notes if existing_hashes.get(n["path"]) != n["hash"]]

    if not to_index:
        print(f"[kb] Index up to date ({len(notes)} notes)")
        return

    print(f"[kb] Embedding {len(to_index)} new/updated notes...")

    texts = [f"{n['title']}\n\n{n['content']}" for n in to_index]
    vectors = embed_texts(texts)

    rows = []
    for note, vector in zip(to_index, vectors):
        rows.append({**note, "vector": vector})
        print(f"[kb]   ✓ {note['path']}")

    if rebuild or "notes" not in db.list_tables():
        db.create_table("notes", data=rows, mode="overwrite")
    else:
        table = db.open_table("notes")
        # Remove stale entries for re-indexed paths
        updated_paths = [r["path"] for r in rows]
        table.delete(f"path IN {updated_paths}")
        table.add(rows)

    print(f"[kb] Indexed {len(rows)} notes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index KB notes into LanceDB")
    parser.add_argument("--rebuild", action="store_true", help="Drop and rebuild full index")
    args = parser.parse_args()
    run(rebuild=args.rebuild)
