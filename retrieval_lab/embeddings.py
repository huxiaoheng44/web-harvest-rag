"""OpenAI embedding wrapper with a disk cache.

Reuses the same embedding model as the production Supabase pipeline
(text-embedding-3-small) so vector-only results are comparable, and caches
by content hash so re-running experiments over overlapping chunks doesn't
re-pay the API cost.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_DIR = Path(__file__).parent
CACHE_PATH = BASE_DIR / "data" / "embedding_cache.json"
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API") or os.getenv("OPENAI_API_KEY"))
    return _client


def _hash(text: str) -> str:
    return hashlib.sha1(f"{EMBED_MODEL}:{text}".encode("utf-8")).hexdigest()


def _load_cache() -> dict[str, list[float]]:
    if not CACHE_PATH.exists():
        return {}
    with open(CACHE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _save_cache(cache: dict[str, list[float]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as handle:
        json.dump(cache, handle)


def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Return one embedding vector per input text, using the disk cache where possible."""
    cache = _load_cache()
    results: list[list[float] | None] = [None] * len(texts)
    to_fetch: list[tuple[int, str]] = []

    for i, text in enumerate(texts):
        key = _hash(text)
        if key in cache:
            results[i] = cache[key]
        else:
            to_fetch.append((i, text))

    client = _get_client()
    for start in range(0, len(to_fetch), batch_size):
        batch = to_fetch[start : start + batch_size]
        response = client.embeddings.create(model=EMBED_MODEL, input=[text for _, text in batch])
        for (i, text), item in zip(batch, response.data):
            results[i] = item.embedding
            cache[_hash(text)] = item.embedding

    if to_fetch:
        _save_cache(cache)

    return results  # type: ignore[return-value]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
