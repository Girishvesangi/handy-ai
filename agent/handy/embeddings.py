"""Text embeddings with the Gemini API, used for the semantic half of search."""

from __future__ import annotations

import os

from google import genai
from google.genai import types

EMBED_MODEL = os.getenv("EMBED_MODEL") or "gemini-embedding-001"
EMBED_DIMS = 768  # smaller vectors are plenty for a few thousand guides


class Embedder:
    def __init__(self, client: genai.Client | None = None) -> None:
        self._client = client or genai.Client()  # reads GOOGLE_API_KEY

    def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        resp = self._client.models.embed_content(
            model=EMBED_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=EMBED_DIMS),
        )
        return [e.values for e in resp.embeddings]

    def embed_documents(self, texts: list[str], batch_size: int = 50) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            out.extend(self._embed(texts[i : i + batch_size], "RETRIEVAL_DOCUMENT"))
        return out

    async def embed_query(self, text: str) -> list[float]:
        resp = await self._client.aio.models.embed_content(
            model=EMBED_MODEL,
            contents=[text],
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=EMBED_DIMS),
        )
        return resp.embeddings[0].values
