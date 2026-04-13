#!/usr/bin/env python3
"""
embed.py - Index KB notes into a LanceDB vector database (Full tier).

Scans all markdown files in the KB, embeds any that are new or updated,
and stores them in a local LanceDB table at .kb/full/index/.

Requirements:
    pip install lancedb openai python-frontmatter

Environment:
    OPENAI_API_KEY  - required for OpenAI embeddings
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

try:
    import frontmatter
    import lancedb
    import openai
except ImportError as e:
    print(f"[kb] Missing dependency: {e}")
    print("[kb] Run: pip install lancedb openai python-frontmatter")
    sys.exit(1)

KB_ROOT = Path(os.environ.get("KB_ROOT", Path.home() / "projects/knowledge-base"))
INDEX_DIR = KB_ROOT / ".kb" / "full" / "index"
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

client = openai.OpenAI()


def embed_text(text: str) -> list[float]:
    response = client.embeddings.create(input=text, model=EMBED_MODEL)
    return response.data[0].embedding


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

    if rebuild and "notes" in db.table_names():
        db.drop_table("notes")
        print("[kb] Dropped existing index for rebuild")

    if "notes" in db.table_names():
        table = db.open_table("notes")
        for row in table.to_pandas().itertuples():
            existing_hashes[row.path] = row.hash

    notes = collect_notes()
    to_index = [n for n in notes if existing_hashes.get(n["path"]) != n["hash"]]

    if not to_index:
        print(f"[kb] Index up to date ({len(notes)} notes)")
        return

    print(f"[kb] Embedding {len(to_index)} new/updated notes...")

    rows = []
    for note in to_index:
        text = f"{note['title']}\n\n{note['content']}"
        vector = embed_text(text)
        rows.append({**note, "vector": vector})
        print(f"[kb]   ✓ {note['path']}")

    if "notes" not in db.table_names():
        db.create_table("notes", data=rows)
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
