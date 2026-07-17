"""LLM-as-judge answer-quality eval: not just "was the right chunk retrieved"
but "given that chunk, is the generated answer actually correct/grounded".

Since none of our query sets have gold reference answers, the judge scores
**faithfulness** - is the answer supported by the retrieved context - rather
than similarity to a reference answer. That's the standard metric choice
when there's no reference to compare against, and worth stating explicitly
rather than pretending we're doing reference-based QA scoring.

Usage:
    python -m retrieval_lab.answer_eval --index structural-500 --k 5 --alpha 0.5
    python -m retrieval_lab.answer_eval --index nfcorpus-fixed-500 --k 5 --alpha 0.8 \
        --queries retrieval_lab/data/nfcorpus_source/eval_queries.json --limit 25
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from retrieval_lab.bm25_index import BM25Store
from retrieval_lab.embeddings import embed_query
from retrieval_lab.hybrid import linear_fusion
from retrieval_lab.vector_store import VectorStore

load_dotenv()

BASE_DIR = Path(__file__).parent
INDEXES_DIR = BASE_DIR / "data" / "indexes"
RESULTS_DIR = BASE_DIR / "data" / "eval_results"
DEFAULT_QUERIES_PATH = BASE_DIR / "eval" / "queries.json"

CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API") or os.getenv("OPENAI_API_KEY"))
    return _client


def build_context(chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant sources were retrieved from the knowledge base."

    parts = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"Title: {chunk.get('title') or 'Untitled'}",
                    f"URL: {chunk.get('url') or ''}",
                    f"Content: {chunk.get('text', '')}",
                ]
            )
        )
    return "\n\n".join(parts)


def generate_answer(query: str, chunks: list[dict]) -> str:
    client = _get_client()
    context = build_context(chunks)
    completion = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a knowledge-base assistant. Answer using only the retrieved context "
                    "below. If the context is insufficient, say clearly that you cannot confirm it "
                    "from the current knowledge base. Do not invent facts."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}",
            },
        ],
    )
    return (completion.choices[0].message.content or "").strip()


JUDGE_SYSTEM_PROMPT = (
    "You are grading whether an answer is faithfully supported by the retrieved context "
    "it was generated from - not whether it matches some other reference answer (none exists), "
    "and not whether the context itself was the right thing to retrieve. "
    "This means two distinct failure modes must NOT be scored the same way: "
    "(a) the retrieved context is irrelevant to the query (a retrieval failure) and "
    "(b) the answer contradicts or invents claims beyond context that IS relevant (a generation failure). "
    "If the context is irrelevant or insufficient and the answer correctly says it cannot confirm the answer "
    "from the knowledge base, that is the CORRECT, faithful behavior and should score 5 - the model is not at "
    "fault for retrieval bringing back the wrong passages. "
    "Score 1-5: "
    "5 = fully supported by the context with no unsupported claims, OR a correct refusal when the context is "
    "irrelevant/insufficient; "
    "3 = partially supported, missing nuance, or an unnecessary refusal when the context actually did contain "
    "a usable partial answer; "
    "1 = confidently states claims that contradict the context, or invents claims not present in context that "
    "IS relevant, or answers from outside knowledge while ignoring relevant context. "
    "Respond with JSON: {\"score\": <int 1-5>, \"reasoning\": \"<one sentence>\"}."
)


def judge_answer(query: str, answer: str, chunks: list[dict]) -> dict:
    client = _get_client()
    context = build_context(chunks)
    completion = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer to grade:\n{answer}",
            },
        ],
    )
    content = completion.choices[0].message.content or "{}"
    try:
        payload = json.loads(content)
        return {"score": int(payload.get("score", 0)), "reasoning": str(payload.get("reasoning", ""))}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"score": 0, "reasoning": "judge response could not be parsed"}


def run(index_name: str, k: int, alpha: float, queries_path: Path, limit: int | None) -> dict:
    index_dir = INDEXES_DIR / index_name
    store = VectorStore.load(index_dir)
    bm25 = BM25Store.load(index_dir)

    with open(queries_path, encoding="utf-8") as handle:
        queries = json.load(handle)
    if limit:
        queries = queries[:limit]

    pool_size = max(20, k)
    records = []

    for query_record in queries:
        query = query_record["query"]
        embedding = embed_query(query)

        vector_hits = store.search(embedding, k=pool_size)
        bm25_hits = bm25.search(query, k=pool_size)
        fused_hits = linear_fusion(vector_hits, bm25_hits, store, bm25, query, embedding, k=k, alpha=alpha)
        chunks = [chunk for chunk, _ in fused_hits]

        answer = generate_answer(query, chunks)
        verdict = judge_answer(query, answer, chunks)

        records.append(
            {
                "id": query_record["id"],
                "query": query,
                "retrieved_doc_ids": [chunk["doc_id"] for chunk in chunks],
                "answer": answer,
                "score": verdict["score"],
                "reasoning": verdict["reasoning"],
            }
        )
        print(f"[{query_record['id']}] score={verdict['score']} - {query[:60]}")

    average_score = sum(r["score"] for r in records) / len(records) if records else 0.0
    return {"index_name": index_name, "k": k, "alpha": alpha, "query_count": len(records), "average_score": average_score, "records": records}


def write_report(summary: dict, path: Path) -> None:
    lines = [
        f"# Answer Quality Eval (LLM-as-judge): {summary['index_name']}",
        "",
        f"{summary['query_count']} queries, k={summary['k']}, alpha={summary['alpha']}. "
        f"Judge scores faithfulness 1-5 (is the answer supported by the retrieved context), not similarity to a reference answer.",
        "",
        f"**Average score: {summary['average_score']:.2f} / 5**",
        "",
        "| id | score | query | reasoning |",
        "|---|---|---|---|",
    ]
    for record in summary["records"]:
        query_short = record["query"].replace("|", "\\|")[:70]
        reasoning_short = record["reasoning"].replace("|", "\\|")
        lines.append(f"| {record['id']} | {record['score']} | {query_short} | {reasoning_short} |")

    low_scoring = [r for r in summary["records"] if r["score"] <= 2]
    if low_scoring:
        lines.append("")
        lines.append(f"## Low-scoring cases ({len(low_scoring)})")
        lines.append("")
        for record in low_scoring:
            lines.append(f"- **{record['id']}** (score {record['score']}) — \"{record['query']}\"")
            lines.append(f"  - answer: {record['answer'][:300]}")
            lines.append(f"  - judge: {record['reasoning']}")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES_PATH))
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N queries")
    args = parser.parse_args()

    summary = run(args.index, args.k, args.alpha, Path(args.queries), args.limit)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RESULTS_DIR / f"{args.index}_answer_eval.json"
    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    md_path = RESULTS_DIR / f"{args.index}_answer_eval.md"
    write_report(summary, md_path)

    print(f"\nAverage score: {summary['average_score']:.2f} / 5")
    print(f"Saved raw results -> {raw_path}")
    print(f"Saved report -> {md_path}")


if __name__ == "__main__":
    main()
