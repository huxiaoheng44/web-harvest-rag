"""Cross-encoder reranking over an already-retrieved candidate pool.

A cross-encoder scores a (query, passage) pair jointly (unlike the bi-encoder
used for vector search, which embeds query and passage independently), so it
captures interactions a dot product can't - at the cost of being too slow to
run over an entire corpus. The standard pattern is "retrieve wide, rerank
narrow": use a cheap first-stage retriever (here, hybrid fusion) to get a
candidate pool, then rerank just that pool with the more expensive model.
"""

from __future__ import annotations

_model = None

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(MODEL_NAME)
    return _model


def rerank(query: str, candidates: list[tuple[dict, float]], k: int) -> list[tuple[dict, float]]:
    """Re-score candidates with the cross-encoder and return the new top-k."""
    if not candidates:
        return []

    model = _get_model()
    pairs = [(query, chunk["text"]) for chunk, _ in candidates]
    scores = model.predict(pairs)

    reranked = sorted(
        ((chunk, float(score)) for (chunk, _), score in zip(candidates, scores)),
        key=lambda item: item[1],
        reverse=True,
    )
    return reranked[:k]
