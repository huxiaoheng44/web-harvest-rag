"""Fusion strategies for combining vector and BM25 retrieval.

Two strategies:

- linear_fusion: min-max normalizes each method's *true* score (not just
  whatever it put in its own top-N) over the union of both methods'
  candidate pools, then combines with a weighted sum
  (score = alpha*vector + (1-alpha)*bm25). Using true scores instead of
  zero-filling absent candidates matters: a chunk one method ranks highly
  but doesn't surface in the other's top-N pool still gets its real,
  non-zero score from that method instead of being unfairly dragged toward 0.
- rrf_fusion: Reciprocal Rank Fusion, score = sum(1 / (rrf_k + rank)) across
  methods that surface the candidate. Scale-invariant - no normalization or
  alpha tuning needed, which is why it's the default hybrid strategy in
  systems like Elasticsearch and Weaviate.
"""

from __future__ import annotations


def _normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    span = hi - lo
    if span == 0:
        return {cid: 1.0 for cid in values}
    return {cid: (v - lo) / span for cid, v in values.items()}


def linear_fusion(
    vector_hits: list[tuple[dict, float]],
    bm25_hits: list[tuple[dict, float]],
    vector_store,
    bm25_store,
    query: str,
    query_embedding: list[float],
    k: int,
    alpha: float = 0.5,
) -> list[tuple[dict, float]]:
    chunk_by_id = {chunk["id"]: chunk for chunk, _ in vector_hits}
    chunk_by_id.update({chunk["id"]: chunk for chunk, _ in bm25_hits})
    # Sorted, not a bare set(): set iteration order depends on PYTHONHASHSEED,
    # which is randomized per process - that was silently reshuffling tie
    # breaks in the sort below and made recall@k non-reproducible across runs.
    candidate_ids = sorted(chunk_by_id)

    vector_scores = vector_store.score(query_embedding, candidate_ids)
    bm25_scores = bm25_store.score(query, candidate_ids)

    vector_norm = _normalize(vector_scores)
    bm25_norm = _normalize(bm25_scores)

    combined = {
        cid: alpha * vector_norm.get(cid, 0.0) + (1 - alpha) * bm25_norm.get(cid, 0.0) for cid in candidate_ids
    }
    ranked = sorted(combined, key=lambda cid: combined[cid], reverse=True)[:k]
    return [(chunk_by_id[cid], combined[cid]) for cid in ranked]


def rrf_fusion(
    vector_hits: list[tuple[dict, float]],
    bm25_hits: list[tuple[dict, float]],
    k: int,
    rrf_k: int = 60,
) -> list[tuple[dict, float]]:
    chunk_by_id = {chunk["id"]: chunk for chunk, _ in vector_hits}
    chunk_by_id.update({chunk["id"]: chunk for chunk, _ in bm25_hits})

    vector_rank = {chunk["id"]: rank for rank, (chunk, _) in enumerate(vector_hits, start=1)}
    bm25_rank = {chunk["id"]: rank for rank, (chunk, _) in enumerate(bm25_hits, start=1)}

    combined = {
        cid: (1 / (rrf_k + vector_rank[cid]) if cid in vector_rank else 0.0)
        + (1 / (rrf_k + bm25_rank[cid]) if cid in bm25_rank else 0.0)
        for cid in chunk_by_id
    }
    ranked = sorted(combined, key=lambda cid: combined[cid], reverse=True)[:k]
    return [(chunk_by_id[cid], combined[cid]) for cid in ranked]


def rrf_merge_many(
    ranked_lists: list[list[tuple[dict, float]]],
    k: int,
    rrf_k: int = 60,
) -> list[tuple[dict, float]]:
    """Reciprocal Rank Fusion across an arbitrary number of ranked lists.

    Generalizes rrf_fusion's fixed two-list case - used to merge per-query-
    variant hybrid retrieval results in the query-rewriting eval, where the
    number of variants is a runtime parameter, not always two.
    """
    chunk_by_id: dict[str, dict] = {}
    scores: dict[str, float] = {}

    for ranked_list in ranked_lists:
        for rank, (chunk, _) in enumerate(ranked_list, start=1):
            chunk_by_id.setdefault(chunk["id"], chunk)
            scores[chunk["id"]] = scores.get(chunk["id"], 0.0) + 1 / (rrf_k + rank)

    ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:k]
    return [(chunk_by_id[cid], scores[cid]) for cid in ranked_ids]
