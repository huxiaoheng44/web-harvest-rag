"""Bucket imperfect-recall queries from a saved eval run into failure categories.

This only gets you the *symptom* automatically - which method(s) missed the
expected doc(s). The actual root-cause judgment (was it a chunking boundary
problem, an embedding/vocabulary mismatch, or a genuinely vague query) is a
human-in-the-loop step; this script's job is surfacing candidates for that
review efficiently, not replacing it.

Usage:
    python -m retrieval_lab.error_analysis --results structural-500 --k 5
    python -m retrieval_lab.error_analysis --results nfcorpus-fixed-500 --k 10
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "data" / "eval_results"


def categorize(query_result: dict, k: int) -> str | None:
    recall = query_result["recall"]
    vector_r = recall.get(f"vector@{k}", 0.0)
    bm25_r = recall.get(f"bm25@{k}", 0.0)
    hybrid_r = recall.get(f"hybrid@{k}", 0.0)

    if hybrid_r >= 1.0:
        return None  # hybrid found everything expected - nothing to analyze

    if vector_r == 0.0 and bm25_r > 0.0:
        return "vector_missed_bm25_hit"
    if bm25_r == 0.0 and vector_r > 0.0:
        return "bm25_missed_vector_hit"
    if vector_r == 0.0 and bm25_r == 0.0:
        return "both_missed"
    return "partial_miss"


CATEGORY_LABELS = {
    "vector_missed_bm25_hit": "Vector missed, BM25 hit (semantic/vocabulary gap)",
    "bm25_missed_vector_hit": "BM25 missed, vector hit (keyword gap - paraphrase, no shared terms)",
    "both_missed": "Both missed (query too vague, wrong chunk boundary, or corpus lacks the answer)",
    "partial_miss": "Partial miss (some but not all expected docs found)",
}


def analyze(results_name: str, k: int) -> dict:
    with open(RESULTS_DIR / f"{results_name}.json", encoding="utf-8") as handle:
        summary = json.load(handle)

    buckets: dict[str, list[dict]] = {key: [] for key in CATEGORY_LABELS}
    for query_result in summary["per_query"]:
        category = categorize(query_result, k)
        if category:
            buckets[category].append(query_result)

    return {"index_name": summary["index_name"], "k": k, "query_count": summary["query_count"], "buckets": buckets}


def write_report(analysis: dict, path: Path) -> None:
    lines = [f"# Error Analysis: {analysis['index_name']} (k={analysis['k']})", ""]
    total_failures = sum(len(v) for v in analysis["buckets"].values())
    lines.append(f"{total_failures} / {analysis['query_count']} queries have imperfect hybrid recall@{analysis['k']}.")
    lines.append("")

    for category, label in CATEGORY_LABELS.items():
        queries = analysis["buckets"][category]
        lines.append(f"## {label} ({len(queries)})")
        lines.append("")
        if not queries:
            lines.append("_None._")
            lines.append("")
            continue

        for q in queries:
            lines.append(f"- **{q['id']}** — \"{q['query']}\"")
            lines.append(f"  - expected: {q['expected_doc_ids']}")
            lines.append(f"  - vector top: {q.get('vector_top_doc_ids', [])[:5]}")
            lines.append(f"  - bm25 top: {q.get('bm25_top_doc_ids', [])[:5]}")
            lines.append(f"  - hybrid top: {q.get('hybrid_top_doc_ids', [])[:5]}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, help="Name of a saved eval_results/<name>.json (without extension)")
    parser.add_argument("--k", type=int, required=True, help="Which recall@k to analyze failures at")
    args = parser.parse_args()

    analysis = analyze(args.results, args.k)
    out_path = RESULTS_DIR / f"{args.results}_error_analysis.md"
    write_report(analysis, out_path)

    print(f"Analyzed {analysis['query_count']} queries at k={args.k}:")
    for category, label in CATEGORY_LABELS.items():
        print(f"  {label}: {len(analysis['buckets'][category])}")
    print(f"\nSaved report -> {out_path}")


if __name__ == "__main__":
    main()
