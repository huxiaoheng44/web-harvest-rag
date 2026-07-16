"""BM25 keyword index over the same chunk set used by the vector store."""

from __future__ import annotations

import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Store:
    def __init__(self, chunk_meta: list[dict]):
        self.chunks = chunk_meta
        corpus = [tokenize(chunk["text"]) for chunk in chunk_meta]
        self.bm25 = BM25Okapi(corpus) if corpus else None
        self._row_by_id = {chunk["id"]: row for row, chunk in enumerate(chunk_meta)}

    def search(self, query: str, k: int) -> list[tuple[dict, float]]:
        if not self.chunks or self.bm25 is None:
            return []

        tokens = tokenize(query)
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.chunks[i], float(scores[i])) for i in ranked]

    def score(self, query: str, chunk_ids: set[str]) -> dict[str, float]:
        """Exact BM25 score for a specific set of chunk ids.

        get_scores() already computes a score for every doc in the corpus
        (it just isn't truncated to top-k), so this reuses that full array
        instead of defaulting ids absent from search()'s top-k to 0.
        """
        if not chunk_ids or self.bm25 is None:
            return {}

        tokens = tokenize(query)
        all_scores = self.bm25.get_scores(tokens)
        result = {}
        for chunk_id in chunk_ids:
            row = self._row_by_id.get(chunk_id)
            if row is None:
                continue
            result[chunk_id] = float(all_scores[row])
        return result

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        with open(directory / "bm25.pkl", "wb") as handle:
            pickle.dump({"chunks": self.chunks, "bm25": self.bm25}, handle)

    @classmethod
    def load(cls, directory: Path) -> "BM25Store":
        with open(directory / "bm25.pkl", "rb") as handle:
            payload = pickle.load(handle)

        store = cls.__new__(cls)
        store.chunks = payload["chunks"]
        store.bm25 = payload["bm25"]
        store._row_by_id = {chunk["id"]: row for row, chunk in enumerate(store.chunks)}
        return store
