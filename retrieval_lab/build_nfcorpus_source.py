"""Download NFCorpus (a BEIR benchmark dataset) and convert it into the shapes
retrieval_lab already knows how to consume: a knowledge_base.json (same schema
as scraper.py's output) and an eval_queries.json (same schema as
eval/queries.json).

NFCorpus: ~3.6K PubMed-style abstracts, 323 test queries with relevance
judgments (qrels), averaging ~38 relevant docs per query.
See https://huggingface.co/datasets/BeIR/nfcorpus

Usage:
    python -m retrieval_lab.build_nfcorpus_source
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "data" / "nfcorpus_source"


def _convert_split(qrels_split, query_text_by_id: dict[str, str]) -> list[dict]:
    relevant_by_query: dict[str, set[str]] = defaultdict(set)
    for row in qrels_split:
        relevant_by_query[row["query-id"]].add(row["corpus-id"])

    eval_queries = [
        {
            "id": query_id,
            "query": query_text_by_id[query_id],
            "query_type": "public_benchmark",
            "expected_doc_ids": sorted(doc_ids),
        }
        for query_id, doc_ids in relevant_by_query.items()
        if query_id in query_text_by_id
    ]
    eval_queries.sort(key=lambda q: q["id"])
    return eval_queries


def build():
    print("Downloading NFCorpus corpus/queries/qrels from Hugging Face (BeIR/nfcorpus)...")
    corpus = load_dataset("BeIR/nfcorpus", "corpus")["corpus"]
    queries = load_dataset("BeIR/nfcorpus", "queries")["queries"]
    qrels = load_dataset("BeIR/nfcorpus-qrels")

    docs = [
        {
            "id": row["_id"],
            "title": row["title"],
            "detected_title": row["title"],
            "url": "",
            "category": "nfcorpus",
            "status": "ok",
            "content_plain": row["text"],
            "content_markdown": row["text"],
            "char_count": len(row["text"]),
        }
        for row in corpus
    ]

    query_text_by_id = {row["_id"]: row["text"] for row in queries}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "knowledge_base.json", "w", encoding="utf-8") as handle:
        json.dump(docs, handle, ensure_ascii=False)
    print(f"Wrote {len(docs)} documents -> {OUTPUT_DIR / 'knowledge_base.json'}")

    # test = final reported numbers. validation = for tuning alpha/rrf_k so we
    # don't tune hyperparameters on the same split we report results on.
    for split_name, output_name in (("test", "eval_queries.json"), ("validation", "eval_queries_validation.json")):
        eval_queries = _convert_split(qrels[split_name], query_text_by_id)
        with open(OUTPUT_DIR / output_name, "w", encoding="utf-8") as handle:
            json.dump(eval_queries, handle, ensure_ascii=False, indent=2)

        avg_relevant = sum(len(q["expected_doc_ids"]) for q in eval_queries) / len(eval_queries)
        print(f"Wrote {len(eval_queries)} {split_name} queries -> {OUTPUT_DIR / output_name} (avg {avg_relevant:.1f} relevant docs/query)")


if __name__ == "__main__":
    build()
