"""Evaluate vector-only, BM25-only, and hybrid retrieval against a labeled query set.

Works against either the hand-labeled MULTIVAC queries (eval/queries.json,
usually 1-2 expected docs per query) or a public benchmark's qrels converted
to the same {id, query, query_type, expected_doc_ids} shape (e.g. NFCorpus,
which averages ~38 relevant docs per query) via --queries.

recall@k is macro-averaged proportional recall per query:
    |relevant docs retrieved in top-k| / |relevant docs for that query|
which collapses to a plain hit/miss rate when a query has exactly one
expected doc (the MULTIVAC case) and behaves correctly for queries with many
expected docs (the NFCorpus case).

Usage:
    python -m retrieval_lab.eval.run_eval --index fixed-500 --k 3 5 --alpha 0.5
    python -m retrieval_lab.eval.run_eval --index nfcorpus-fixed-500 \
        --queries retrieval_lab/data/nfcorpus_source/eval_queries.json --k 5 10 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from retrieval_lab.bm25_index import BM25Store
from retrieval_lab.embeddings import embed_texts
from retrieval_lab.hybrid import linear_fusion, rrf_fusion
from retrieval_lab.vector_store import VectorStore

BASE_DIR = Path(__file__).parent
LAB_DIR = BASE_DIR.parent
INDEXES_DIR = LAB_DIR / "data" / "indexes"
RESULTS_DIR = LAB_DIR / "data" / "eval_results"
DEFAULT_QUERIES_PATH = BASE_DIR / "queries.json"

CANDIDATE_POOL_SIZE = 20


def load_queries(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def recall_fraction(hits: list[tuple[dict, float]], k: int, expected_doc_ids: list[str]) -> float:
    expected = set(expected_doc_ids)
    if not expected:
        return 0.0
    retrieved = {chunk["doc_id"] for chunk, _ in hits[:k]}
    return len(retrieved & expected) / len(expected)


def run(
    index_name: str,
    k_values: list[int],
    alpha: float,
    queries_path: Path,
    fusion: str = "linear",
    rrf_k: int = 60,
) -> dict:
    index_dir = INDEXES_DIR / index_name
    if not index_dir.exists():
        raise FileNotFoundError(f"No index found at {index_dir}. Build it first with build_experiment_index.py")

    store = VectorStore.load(index_dir)
    bm25 = BM25Store.load(index_dir)
    queries = load_queries(queries_path)

    max_k = max(k_values)
    pool_size = max(CANDIDATE_POOL_SIZE, max_k)

    print(f"Embedding {len(queries)} queries...")
    query_embeddings = embed_texts([q["query"] for q in queries])

    per_query_results = []
    method_totals = {"vector": {k: 0.0 for k in k_values}, "bm25": {k: 0.0 for k in k_values}, "hybrid": {k: 0.0 for k in k_values}}

    for query_record, query_embedding in zip(queries, query_embeddings):
        query = query_record["query"]
        expected = query_record["expected_doc_ids"]

        vector_hits = store.search(query_embedding, k=pool_size)
        bm25_hits = bm25.search(query, k=pool_size)

        if fusion == "rrf":
            fused_hits = rrf_fusion(vector_hits, bm25_hits, k=pool_size, rrf_k=rrf_k)
        else:
            fused_hits = linear_fusion(vector_hits, bm25_hits, store, bm25, query, query_embedding, k=pool_size, alpha=alpha)

        query_result = {
            "id": query_record["id"],
            "query": query,
            "query_type": query_record.get("query_type", ""),
            "expected_doc_ids": expected,
            "vector_top_doc_ids": [chunk["doc_id"] for chunk, _ in vector_hits[:max_k]],
            "bm25_top_doc_ids": [chunk["doc_id"] for chunk, _ in bm25_hits[:max_k]],
            "hybrid_top_doc_ids": [chunk["doc_id"] for chunk, _ in fused_hits[:max_k]],
            "recall": {},
        }

        for k in k_values:
            for method, hits in (("vector", vector_hits), ("bm25", bm25_hits), ("hybrid", fused_hits)):
                fraction = recall_fraction(hits, k, expected)
                query_result["recall"][f"{method}@{k}"] = fraction
                method_totals[method][k] += fraction

        per_query_results.append(query_result)

    total = len(queries)
    recall = {method: {k: method_totals[method][k] / total for k in k_values} for method in method_totals}

    return {
        "index_name": index_name,
        "queries_path": str(queries_path),
        "fusion": fusion,
        "alpha": alpha,
        "rrf_k": rrf_k,
        "query_count": total,
        "recall": recall,
        "per_query": per_query_results,
    }


def print_table(summary: dict, k_values: list[int]) -> None:
    fusion_desc = f"alpha={summary['alpha']}" if summary["fusion"] == "linear" else f"rrf_k={summary['rrf_k']}"
    print(f"\nIndex: {summary['index_name']}  (fusion={summary['fusion']}, {fusion_desc}, n={summary['query_count']} queries)")
    print(f"Queries file: {summary['queries_path']}")
    header = "Method".ljust(10) + "".join(f"recall@{k}".rjust(12) for k in k_values)
    print(header)
    for method in ("vector", "bm25", "hybrid"):
        row = method.ljust(10) + "".join(f"{summary['recall'][method][k]:.1%}".rjust(12) for k in k_values)
        print(row)


def write_results_md(summary: dict, k_values: list[int], path: Path) -> None:
    fusion_desc = f"alpha={summary['alpha']}" if summary["fusion"] == "linear" else f"rrf_k={summary['rrf_k']}"
    lines = [f"# Retrieval Eval Results: {summary['index_name']}", ""]
    lines.append(f"Queries: {summary['query_count']} (from `{summary['queries_path']}`)  |  Fusion: {summary['fusion']} ({fusion_desc})")
    lines.append("")
    lines.append("| Method | " + " | ".join(f"recall@{k}" for k in k_values) + " |")
    lines.append("|---" * (len(k_values) + 1) + "|")
    for method in ("vector", "bm25", "hybrid"):
        row = [f"{summary['recall'][method][k]:.1%}" for k in k_values]
        lines.append(f"| {method} | " + " | ".join(row) + " |")

    lines.append("")
    best_k = max(k_values)
    vector_r = summary["recall"]["vector"][best_k]
    hybrid_r = summary["recall"]["hybrid"][best_k]
    delta = (hybrid_r - vector_r) * 100
    direction = "improved" if delta >= 0 else "reduced"
    lines.append(
        f"Hybrid retrieval {direction} recall@{best_k} from {vector_r:.1%} (vector-only) "
        f"to {hybrid_r:.1%} on a {summary['query_count']}-query evaluation set."
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, help="Experiment name under retrieval_lab/data/indexes/")
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5])
    parser.add_argument("--fusion", choices=["linear", "rrf"], default="linear")
    parser.add_argument("--alpha", type=float, default=0.5, help="Linear fusion weight on the vector channel")
    parser.add_argument("--rrf-k", type=int, default=60, help="RRF rank-damping constant")
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES_PATH), help="Path to a {id, query, expected_doc_ids} JSON file")
    parser.add_argument("--tag", default="", help="Suffix appended to the saved results filename (e.g. to separate fusion runs)")
    args = parser.parse_args()

    k_values = sorted(args.k)
    summary = run(args.index, k_values, args.alpha, Path(args.queries), fusion=args.fusion, rrf_k=args.rrf_k)
    print_table(summary, k_values)

    result_name = f"{args.index}{('_' + args.tag) if args.tag else ''}"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RESULTS_DIR / f"{result_name}.json"
    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    md_path = RESULTS_DIR / f"{result_name}_RESULTS.md"
    write_results_md(summary, k_values, md_path)

    print(f"\nSaved raw results -> {raw_path}")
    print(f"Saved summary -> {md_path}")


if __name__ == "__main__":
    main()
