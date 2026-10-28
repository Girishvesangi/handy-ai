"""Hybrid guide search: BM25 keyword search plus embedding search, fused.

Why both? Keyword search nails exact model names ("A1466", "T480"), and
embedding search handles loose phrasing ("my laptop won't hold a charge"
should find battery guides). Reciprocal rank fusion (RRF) merges the two
rankings without having to tune score scales against each other.
"""

from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

from .guides import Guide

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "my", "i",
    "is", "it", "this", "that", "how", "do", "can", "with", "me", "need", "want",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(d)) for d in docs]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.docs else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for doc, length in zip(self.docs, self.lengths):
            s = 0.0
            for t in q:
                tf = doc.get(t, 0)
                if tf:
                    norm = tf + self.k1 * (1 - self.b + self.b * length / self.avg_len)
                    s += self.idf[t] * tf * (self.k1 + 1) / norm
            out.append(s)
        return out


def rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal rank fusion: each list votes 1/(k + rank) for its items."""
    score: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            score[idx] = score.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(score, key=lambda i: score[i], reverse=True)


class GuideIndex:
    def __init__(self, guides: list[Guide]) -> None:
        self.guides = guides
        self.bm25 = BM25([g.search_text() for g in guides])
        with_vectors = [g.embedding for g in guides if g.embedding]
        self.has_embeddings = bool(guides) and len(with_vectors) == len(guides)
        if self.has_embeddings:
            m = np.array([g.embedding for g in guides], dtype=np.float32)
            self.matrix = m / np.linalg.norm(m, axis=1, keepdims=True)

    def by_id(self, guide_id: int) -> Guide | None:
        return next((g for g in self.guides if g.id == guide_id), None)

    def keyword_ranking(self, query: str, depth: int = 50) -> list[int]:
        scores = self.bm25.scores(query)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [i for i in ranked[:depth] if scores[i] > 0]

    def vector_ranking(self, query_vec: list[float], depth: int = 50) -> list[int]:
        q = np.array(query_vec, dtype=np.float32)
        sims = self.matrix @ (q / np.linalg.norm(q))
        return list(np.argsort(-sims)[:depth])

    def search(self, query: str, query_vec: list[float] | None = None, k: int = 3) -> list[Guide]:
        rankings = [self.keyword_ranking(query)]
        if query_vec is not None and self.has_embeddings:
            rankings.append(self.vector_ranking(query_vec))
        return [self.guides[i] for i in rrf(rankings)[:k]]
