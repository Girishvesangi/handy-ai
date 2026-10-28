"""Retrieval eval: does guide search put the right guide in the top results?

Each line of data/retrieval_queries.jsonl is a spoken-style query and the
words the correct guide's title must contain, e.g.
  {"query": "my macbook air won't hold a charge", "must": ["macbook air", "battery"]}

A result counts as relevant when its title (plus device) contains every
"must" phrase ("ram|memory" accepts either word). We report hit@1, hit@3 and MRR for keyword-only search and,
when embeddings exist, for hybrid search.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from handy.guides import Guide, load_guides
from handy.search import GuideIndex

from .metrics import hit_at_k, mrr

DATA = Path(__file__).parent / "data" / "retrieval_queries.jsonl"


def load_queries(path: Path = DATA) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def relevant(guide: Guide, must: list[str]) -> bool:
    """Every "must" item has to appear; "ram|memory" means either word is fine."""
    text = f"{guide.title} {guide.device}".lower()
    return all(any(alt.strip().lower() in text for alt in m.split("|")) for m in must)


def first_relevant_rank(results: list[Guide], must: list[str]) -> int | None:
    return next((i + 1 for i, g in enumerate(results) if relevant(g, must)), None)


def answerable(queries: list[dict], guides: list[Guide]) -> list[dict]:
    """Only score queries that have at least one relevant guide in the dataset."""
    return [q for q in queries if any(relevant(g, q["must"]) for g in guides)]


def evaluate(index: GuideIndex, queries: list[dict], vectors: list[list[float]] | None = None, k: int = 10) -> dict:
    ranks, rows = [], []
    for i, q in enumerate(queries):
        vec = vectors[i] if vectors else None
        results = index.search(q["query"], query_vec=vec, k=k)
        rank = first_relevant_rank(results, q["must"])
        ranks.append(rank)
        rows.append({"query": q["query"], "rank": rank, "top": results[0].title if results else None})
    return {
        "n": len(queries),
        "hit@1": hit_at_k(ranks, 1),
        "hit@3": hit_at_k(ranks, 3),
        "mrr": mrr(ranks),
        "misses": [r for r in rows if r["rank"] is None or r["rank"] > 3],
    }


def run() -> dict:
    guides = load_guides()
    if not guides:
        raise SystemExit("No guides found. Run `python -m handy.ingest` first.")
    index = GuideIndex(guides)
    all_queries = load_queries()
    queries = answerable(all_queries, guides)
    out = {
        "guides": len(guides),
        "queries_total": len(all_queries),
        "queries_answerable": len(queries),
        "keyword": evaluate(index, queries),
    }
    if index.has_embeddings:
        from handy.embeddings import Embedder

        embedder = Embedder()

        async def embed_all() -> list[list[float]]:
            return [await embedder.embed_query(q["query"]) for q in queries]

        out["hybrid"] = evaluate(index, queries, asyncio.run(embed_all()))
    return out
