"""Build a FAISS + BM25 index for one chunking-strategy experiment.

Usage:
    python -m retrieval_lab.build_experiment_index --strategy fixed --chunk-size 500 --overlap 50 --name fixed-500
    python -m retrieval_lab.build_experiment_index --strategy structural --max-tokens 500 --name structural-500
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from retrieval_lab import chunking
from retrieval_lab.bm25_index import BM25Store
from retrieval_lab.embeddings import embed_texts
from retrieval_lab.vector_store import VectorStore

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent
KB_PATH = PROJECT_DIR / "data" / "knowledge_base.json"
INDEXES_DIR = BASE_DIR / "data" / "indexes"


def build_chunks(docs: list[dict], strategy: str, chunk_size: int, overlap: int, max_tokens: int) -> list[dict]:
    chunk_records = []

    for doc in docs:
        doc_id = doc["id"]
        title = doc.get("detected_title") or doc.get("title", "")
        url = doc.get("url", "")
        category = doc.get("category", "")

        if strategy == "fixed":
            text = doc.get("content_plain", "").strip()
            pieces = chunking.fixed_size_chunks(text, chunk_tokens=chunk_size, overlap_tokens=overlap)
        elif strategy == "structural":
            text = (doc.get("content_markdown") or doc.get("content_plain", "")).strip()
            pieces = chunking.structural_chunks(text, max_tokens=max_tokens)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        for piece in pieces:
            chunk_records.append(
                {
                    "id": f"{doc_id}__{strategy}__chunk{piece.chunk_idx}",
                    "doc_id": doc_id,
                    "title": title,
                    "url": url,
                    "category": category,
                    "chunk_idx": piece.chunk_idx,
                    "text": piece.text,
                }
            )

    return chunk_records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=["fixed", "structural"], required=True)
    parser.add_argument("--chunk-size", type=int, default=500, help="Fixed-size chunk length in tokens")
    parser.add_argument("--overlap", type=int, default=50, help="Fixed-size chunk overlap in tokens")
    parser.add_argument("--max-tokens", type=int, default=500, help="Structural chunk max length in tokens")
    parser.add_argument("--name", required=True, help="Experiment name, used as the output directory")
    parser.add_argument("--input", default=str(KB_PATH))
    args = parser.parse_args()

    kb_path = Path(args.input)
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base not found: {kb_path}")

    with open(kb_path, encoding="utf-8") as handle:
        docs = json.load(handle)

    docs = [doc for doc in docs if doc.get("status") == "ok"]
    print(f"Loaded {len(docs)} documents from {kb_path}")

    chunk_records = build_chunks(docs, args.strategy, args.chunk_size, args.overlap, args.max_tokens)
    if not chunk_records:
        raise SystemExit("No chunks produced - check the knowledge base file has usable content.")

    print(f"Produced {len(chunk_records)} chunks using strategy={args.strategy}")
    per_doc: dict[str, int] = {}
    for record in chunk_records:
        per_doc[record["doc_id"]] = per_doc.get(record["doc_id"], 0) + 1
    for doc_id, count in per_doc.items():
        print(f"  {doc_id}: {count} chunks")

    print("Embedding chunks (cached where possible)...")
    embeddings = embed_texts([record["text"] for record in chunk_records])

    store = VectorStore(dim=len(embeddings[0]))
    store.add(embeddings, chunk_records)

    bm25 = BM25Store(chunk_records)

    output_dir = INDEXES_DIR / args.name
    store.save(output_dir)
    bm25.save(output_dir)

    with open(output_dir / "meta.json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "strategy": args.strategy,
                "chunk_size": args.chunk_size,
                "overlap": args.overlap,
                "max_tokens": args.max_tokens,
                "chunk_count": len(chunk_records),
            },
            handle,
            indent=2,
        )

    print(f"\nSaved index -> {output_dir}")


if __name__ == "__main__":
    main()
