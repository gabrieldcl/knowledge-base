#!/usr/bin/env python3
"""
query.py - Semantic search over KB notes (Full tier).

Runs a hybrid search combining vector similarity and grep-based keyword
matching, then returns ranked results for Claude to synthesise.

Embedding provider is selected via the EMBED_PROVIDER env var (must match
what was used in embed.py):
  - "voyage" (default) — Voyage AI voyage-code-3
  - "openai"           — OpenAI text-embedding-3-small

Requirements:
    pip install lancedb python-frontmatter voyageai   # Voyage (default)
    pip install lancedb python-frontmatter openai     # OpenAI

Environment:
    VOYAGE_API_KEY  - required when EMBED_PROVIDER=voyage (default)
    OPENAI_API_KEY  - required when EMBED_PROVIDER=openai
    EMBED_PROVIDER  - "voyage" (default) or "openai"
    KB_ROOT         - path to knowledge base root (default: ~/projects/knowledge-base)

Usage:
    python3 query.py "how does the auth middleware work"
    python3 query.py "deployment pipeline" --domain backend --top 5
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

EMBED_PROVIDER = os.environ.get("EMBED_PROVIDER", "voyage")

try:
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


def embed_text(text: str) -> list[float]:
    if EMBED_PROVIDER == "openai":
        response = _client.embeddings.create(input=text, model=EMBED_MODEL)
        return response.data[0].embedding
    else:
        result = _client.embed([text], model=EMBED_MODEL)
        return result.embeddings[0]


def vector_search(query: str, domain: str | None, top: int) -> list[dict]:
    if not (INDEX_DIR).exists() or "notes" not in lancedb.connect(str(INDEX_DIR)).table_names():
        print("[kb] No vector index found. Run embed.py first.", file=sys.stderr)
        return []

    db = lancedb.connect(str(INDEX_DIR))
    table = db.open_table("notes")
    vector = embed_text(query)

    results = table.search(vector).limit(top * 2).to_pandas()

    if domain:
        results = results[results["domain"] == domain]

    return results.head(top).to_dict("records")


def keyword_search(query: str, domain: str | None, top: int) -> list[str]:
    """Fallback grep search across KB files."""
    search_root = str(KB_ROOT / ("areas/" + domain if domain else ""))
    try:
        result = subprocess.run(
            ["grep", "-rl", "--include=*.md", query, search_root],
            capture_output=True, text=True, timeout=10
        )
        paths = result.stdout.strip().splitlines()
        return [p for p in paths if "_index.md" not in p and "CONTEXT.md" not in p][:top]
    except Exception:
        return []


def reciprocal_rank_fusion(vector_results: list[dict], keyword_paths: list[str]) -> list[str]:
    """Merge vector and keyword results by reciprocal rank fusion."""
    scores: dict[str, float] = {}
    k = 60  # RRF constant

    for rank, r in enumerate(vector_results):
        path = r["path"]
        scores[path] = scores.get(path, 0) + 1 / (k + rank + 1)

    for rank, path in enumerate(keyword_paths):
        rel = str(Path(path).relative_to(KB_ROOT))
        scores[rel] = scores.get(rel, 0) + 1 / (k + rank + 1)

    return sorted(scores, key=lambda p: scores[p], reverse=True)


def run(query: str, domain: str | None, top: int):
    print(f"[kb] Query: \"{query}\"\n")

    vector_results = vector_search(query, domain, top)
    keyword_paths = keyword_search(query, domain, top)
    ranked = reciprocal_rank_fusion(vector_results, keyword_paths)

    if not ranked:
        # Log miss for upgrade threshold detection
        import datetime
        log_dir = KB_ROOT / ".kb" / "sessions"
        log_dir.mkdir(parents=True, exist_ok=True)
        miss_log = log_dir / "query-misses.log"
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(miss_log, "a") as f:
            f.write(f"kb-query-miss {ts} query=\"{query}\"\n")
        print("[kb] No results found.")
        return

    print(f"[kb] Top {min(top, len(ranked))} results:\n")
    for i, path in enumerate(ranked[:top], 1):
        full_path = KB_ROOT / path
        if full_path.exists():
            print(f"{i}. {path}")
            # Print first non-frontmatter line as preview
            lines = full_path.read_text().splitlines()
            for line in lines:
                if line.startswith("#"):
                    print(f"   {line}")
                    break
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Semantic search over KB notes")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--domain", help="Filter by domain", default=None)
    parser.add_argument("--top", type=int, default=5, help="Number of results (default: 5)")
    args = parser.parse_args()
    run(args.query, args.domain, args.top)
