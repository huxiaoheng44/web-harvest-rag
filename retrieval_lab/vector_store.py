"""FAISS-backed vector store with a JSON metadata sidecar.

FAISS only stores vectors and returns row indices, so we keep a parallel
list of chunk metadata (id, doc_id, title, url, category, text) indexed by
the same row order.
"""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np


class VectorStore:
    def __init__(self, dim: int):
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)
        self.chunks: list[dict] = []
        self._row_by_id: dict[str, int] = {}

    def add(self, embeddings: list[list[float]], chunk_meta: list[dict]) -> None:
        if len(embeddings) != len(chunk_meta):
            raise ValueError("embeddings and chunk_meta must be the same length")
        if not embeddings:
            return

        start_row = self.index.ntotal
        vectors = np.array(embeddings, dtype="float32")
        faiss.normalize_L2(vectors)
        self.index.add(vectors)
        self.chunks.extend(chunk_meta)
        for offset, meta in enumerate(chunk_meta):
            self._row_by_id[meta["id"]] = start_row + offset

    def search(self, query_embedding: list[float], k: int) -> list[tuple[dict, float]]:
        if self.index.ntotal == 0:
            return []

        vector = np.array([query_embedding], dtype="float32")
        faiss.normalize_L2(vector)
        scores, row_ids = self.index.search(vector, min(k, self.index.ntotal))

        hits = []
        for row_id, score in zip(row_ids[0], scores[0]):
            if row_id == -1:
                continue
            hits.append((self.chunks[row_id], float(score)))
        return hits

    def score(self, query_embedding: list[float], chunk_ids: set[str]) -> dict[str, float]:
        """Exact cosine similarity for a specific set of chunk ids.

        Unlike search(), this isn't limited to the top-k FAISS returns -
        used by hybrid fusion so a chunk that one method's top-N candidate
        list surfaces but the other method's doesn't still gets its real
        score instead of being defaulted to 0.
        """
        if not chunk_ids:
            return {}

        vector = np.array(query_embedding, dtype="float32")
        faiss.normalize_L2(vector.reshape(1, -1))

        scores = {}
        for chunk_id in chunk_ids:
            row = self._row_by_id.get(chunk_id)
            if row is None:
                continue
            stored_vector = self.index.reconstruct(row)
            scores[chunk_id] = float(np.dot(stored_vector, vector))
        return scores

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directory / "index.faiss"))
        with open(directory / "chunks.json", "w", encoding="utf-8") as handle:
            json.dump({"dim": self.dim, "chunks": self.chunks}, handle, ensure_ascii=False)

    @classmethod
    def load(cls, directory: Path) -> "VectorStore":
        with open(directory / "chunks.json", encoding="utf-8") as handle:
            payload = json.load(handle)

        store = cls(dim=payload["dim"])
        store.index = faiss.read_index(str(directory / "index.faiss"))
        store.chunks = payload["chunks"]
        store._row_by_id = {chunk["id"]: row for row, chunk in enumerate(store.chunks)}
        return store
