# Retrieval Lab

A standalone retrieval experimentation and evaluation harness. It doesn't
touch the production frontend, backend, or database schema (`app/`,
`components/`, `lib/`, `backend/`, `sql/`) — it's a parallel, local research
module for comparing chunking strategies and retrieval methods with real
recall@k numbers, either on the scraped MULTIVAC corpus or on a public
benchmark (NFCorpus).

See [`RESULTS.md`](RESULTS.md) for the actual experiment findings and
numbers. This file covers what's here and how to run it.

## What it does

1. **Chunking** (`chunking.py`) — two strategies over the same source text:
   - `fixed_size_chunks`: token-based sliding window with overlap
   - `structural_chunks`: splits on markdown heading/paragraph boundaries,
     merging small sections up to a token budget
2. **Embedding** (`embeddings.py`) — OpenAI `text-embedding-3-small` (same
   model as the production pipeline), with a disk cache keyed by content
   hash so re-running experiments over overlapping chunks doesn't re-pay
   the API cost.
3. **Vector search** (`vector_store.py`) — a local FAISS `IndexFlatIP`
   (cosine similarity via L2-normalized vectors), no server required.
4. **Keyword search** (`bm25_index.py`) — `rank_bm25` over the same chunks.
5. **Hybrid fusion** (`hybrid.py`) — two strategies:
   - `linear_fusion`: per-query min-max normalized weighted sum
     (`alpha * vector + (1-alpha) * bm25`), scored against the *true* score
     for every candidate (not zero-filled — see `RESULTS.md` for why that
     distinction mattered)
   - `rrf_fusion`: Reciprocal Rank Fusion, scale-invariant, no alpha needed
6. **Evaluation** (`eval/run_eval.py`) — computes macro-averaged recall@k
   for vector-only / bm25-only / hybrid against a labeled query set, prints
   a comparison table, and saves raw + markdown results. Two optional extra
   columns:
   - `--rerank` (`rerank.py`) — cross-encoder (`sentence-transformers`)
     reranks the hybrid candidate pool
   - `--query-rewrite N` (`query_rewrite.py`) — LLM-paraphrases each query
     into N variants, retrieves hybrid for each, merges via
     `hybrid.rrf_merge_many`
7. **Chunk size sweep** (`chunk_size_sweep.py`) — orchestrates
   `build_experiment_index.py` + `eval/run_eval.py` across several fixed
   chunk sizes and tabulates the recall@k trend.
8. **Error analysis** (`error_analysis.py`) — post-processes a saved
   `eval/run_eval.py` result into failure buckets (vector-missed/BM25-hit,
   BM25-missed/vector-hit, both-missed, partial-miss).
9. **Answer-quality eval** (`answer_eval.py`) — generates an answer from the
   retrieved chunks and has a second LLM call judge its faithfulness to
   that context (1-5) — covers generation quality, not just retrieval.

## Directory layout

```
retrieval_lab/
  chunking.py, embeddings.py, vector_store.py, bm25_index.py, hybrid.py
  build_experiment_index.py    # CLI: chunk -> embed -> build FAISS + BM25 index
  build_nfcorpus_source.py     # CLI: download NFCorpus from Hugging Face, convert to our schema
  rerank.py                    # cross-encoder reranking over a candidate pool
  query_rewrite.py             # LLM query paraphrasing
  chunk_size_sweep.py          # CLI: sweep fixed chunk sizes, tabulate recall@k trend
  error_analysis.py            # CLI: bucket failures from a saved eval result
  answer_eval.py               # CLI: generate + LLM-judge answer faithfulness
  eval/
    queries.json                # hand-labeled MULTIVAC eval queries (LLM-drafted, human-reviewed)
    run_eval.py                  # CLI: run the eval, print + save recall@k
  data/       (git-ignored)     # built indexes, embedding cache, eval results, downloaded corpora
  backups/    (git-ignored)     # point-in-time snapshots of corpus + indexes + results
```

## Running it

Install the core scraping deps plus this module's own extra dependencies
(`faiss-cpu`, `rank_bm25`, `tiktoken`, `numpy`, `datasets`,
`sentence-transformers` — kept in a separate `retrieval_lab/requirements.txt`
so the production backend image doesn't have to install them too):

```bash
pip install -r requirements.txt -r retrieval_lab/requirements.txt
```

### On the MULTIVAC corpus (uses the already-scraped `data/knowledge_base.json`)

```bash
python -m retrieval_lab.build_experiment_index --strategy fixed --chunk-size 500 --overlap 50 --name fixed-500
python -m retrieval_lab.build_experiment_index --strategy structural --max-tokens 500 --name structural-500

python -m retrieval_lab.eval.run_eval --index fixed-500 --k 1 3 5 --alpha 0.5
python -m retrieval_lab.eval.run_eval --index structural-500 --k 1 3 5 --alpha 0.5
```

### On NFCorpus (a public BEIR benchmark, downloaded from Hugging Face)

```bash
python -m retrieval_lab.build_nfcorpus_source

python -m retrieval_lab.build_experiment_index --strategy fixed --chunk-size 500 --overlap 50 \
  --name nfcorpus-fixed-500 --input retrieval_lab/data/nfcorpus_source/knowledge_base.json

python -m retrieval_lab.eval.run_eval --index nfcorpus-fixed-500 \
  --queries retrieval_lab/data/nfcorpus_source/eval_queries.json --k 5 10 20 100 --alpha 0.8
```

### Comparing fusion strategies or alpha values

```bash
python -m retrieval_lab.eval.run_eval --index fixed-500 --k 1 3 5 --fusion rrf --tag rrf
python -m retrieval_lab.eval.run_eval --index fixed-500 --k 1 3 5 --alpha 0.3 --tag alpha0.3
```

`--tag` appends a suffix to the saved results filename so runs with
different settings don't overwrite each other.

### Rerank, query rewriting, chunk size sweep, error analysis, answer quality

```bash
# Cross-encoder rerank on top of hybrid
python -m retrieval_lab.eval.run_eval --index structural-500 --k 1 3 5 --rerank --tag rerank

# Query rewriting (2 LLM-generated variants + original, RRF-merged)
python -m retrieval_lab.eval.run_eval --index structural-500 --k 1 3 5 --query-rewrite 2 --tag qrewrite

# Chunk size sweep
python -m retrieval_lab.chunk_size_sweep --sizes 200 500 1000 --prefix multivac --k 1 3 5

# Error analysis on an already-saved eval_results/<name>.json
python -m retrieval_lab.error_analysis --results structural-500 --k 5

# LLM-as-judge answer-quality eval
python -m retrieval_lab.answer_eval --index structural-500 --k 5 --alpha 0.5
```

See `RESULTS.md` for what each of these actually found, including a judge-
prompt calibration bug that turned up (and was fixed) while running the
answer-quality eval.

## Adding your own corpus

`build_experiment_index.py --input <path>` accepts any JSON file shaped like
a list of `{"id", "title", "url", "category", "status": "ok",
"content_plain", "content_markdown"}` records — the same shape
`scraper.py` produces. `run_eval.py --queries <path>` accepts any JSON file
shaped like `[{"id", "query", "expected_doc_ids": [...]}, ...]` — doc-level
labels, so it works whether a query has one right answer (MULTIVAC) or
dozens (NFCorpus-style qrels).
