"""
Build the vector index from data/knowledge_base.json and store embeddings in Supabase.

Prerequisites:
    1. Run sql/setup_schema.sql once in Supabase SQL Editor
    2. .env must contain OPENAI_API or OPENAI_API_KEY, plus SUPABASE_URL and SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY

Usage:
    python build_index.py
    python build_index.py --reset
    python build_index.py --input data/knowledge_base.json
"""

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

BASE_DIR = Path(__file__).parent
DEFAULT_KB_PATH = BASE_DIR / "data" / "knowledge_base.json"
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "1200"))
OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS", "150"))

openai_client = OpenAI(api_key=os.getenv("OPENAI_API") or os.getenv("OPENAI_API_KEY"))
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
)


def split_into_chunks(text: str) -> list[str]:
    text = text.strip()
    if len(text) <= CHUNK_CHARS:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_CHARS
        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        search_from = start + OVERLAP_CHARS
        cut = text.rfind("\n\n", search_from, end)
        if cut == -1:
            cut = text.rfind(". ", search_from, end)
        if cut == -1:
            cut = end

        chunk = text[start:cut].strip()
        if chunk:
            chunks.append(chunk)
        start = max(cut - OVERLAP_CHARS, start + 1)

    return [chunk for chunk in chunks if len(chunk) > 50]


def embed_batch(texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def build_index(kb_path: Path, reset: bool = False):
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base file not found: {kb_path}")

    with open(kb_path, encoding="utf-8") as handle:
        docs = json.load(handle)
    print(f"Loaded {len(docs)} documents from {kb_path}")

    if reset:
        supabase.table("chunks").delete().neq("id", "").execute()
        print("Deleted all existing chunks")

    existing = supabase.table("chunks").select("id").execute()
    existing_ids = {row["id"] for row in existing.data}
    print(f"Already indexed: {len(existing_ids)} chunks")

    inserted = 0
    skipped = 0

    for doc_num, doc in enumerate(docs, start=1):
        text = doc.get("content_plain", "").strip()
        if not text:
            continue

        chunks = split_into_chunks(text)
        new_chunks = []
        new_meta = []

        for index, chunk in enumerate(chunks):
            chunk_id = f"{doc['id']}__chunk_{index}"
            if chunk_id in existing_ids:
                skipped += 1
                continue

            new_chunks.append(chunk)
            new_meta.append(
                {
                    "id": chunk_id,
                    "doc_id": doc["id"],
                    "title": doc.get("detected_title") or doc.get("title", ""),
                    "url": doc.get("url", ""),
                    "category": doc.get("category", ""),
                    "chunk_idx": index,
                    "total_chunks": len(chunks),
                    "content": chunk,
                }
            )

        if not new_chunks:
            continue

        print(f"  [{doc_num}/{len(docs)}] {doc['id']} ({len(new_chunks)} chunks)")
        embeddings = embed_batch(new_chunks)
        rows = [{**meta, "embedding": embedding} for meta, embedding in zip(new_meta, embeddings)]
        supabase.table("chunks").insert(rows).execute()
        inserted += len(rows)
        time.sleep(0.3)

    print(f"\nDone. {inserted} new chunks indexed ({skipped} already existed).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete all chunks and rebuild from scratch")
    parser.add_argument("--input", default=str(DEFAULT_KB_PATH), help="Path to the knowledge base JSON file")
    args = parser.parse_args()
    build_index(Path(args.input), reset=args.reset)
