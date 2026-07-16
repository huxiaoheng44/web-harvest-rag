# Retrieval Lab: Experiment Results

Quantitative findings from the retrieval experimentation harness in this
directory: chunking strategy comparison, BM25 vs. vector vs. hybrid
retrieval, and hyperparameter tuning, run on two corpora.

## Corpora

| Corpus | Docs | Chunks (fixed-500 / structural-500) | Eval queries | Avg relevant docs/query |
|---|---|---|---|---|
| MULTIVAC (scraped) | 24 | 124 / 159 | 30 (hand-labeled, LLM-drafted + human-reviewed) | ~1.1 |
| [NFCorpus](https://huggingface.co/datasets/BeIR/nfcorpus) (BEIR benchmark) | 3,633 | 3,882 / 3,879 | 323 test (+324 validation for tuning) | 38.2 |

MULTIVAC is a company knowledge base scraped from multivac.com (digital
solutions pages, news, case studies, a PDF brochure). NFCorpus is a public
benchmark of PubMed-style medical/nutrition abstracts with official relevance
judgments (qrels), added specifically because MULTIVAC's hand-labeled query
set is too small and too "one right answer per query" to produce
discriminating numbers between retrieval methods (see below).

## Headline numbers

alpha tuned on NFCorpus's validation split (not the test split reported
here); MULTIVAC has no separate validation split, so its alpha=0.5 is
untuned — see caveats.

| Corpus / Index | Method | recall@5 | recall@k (larger k) |
|---|---|---|---|
| MULTIVAC structural-500 | vector | 93.3% | recall@3: 71.7%, recall@1: 60.0% |
| | bm25 | 95.0% | recall@3: 85.0%, recall@1: 75.0% |
| | **hybrid (α=0.5)** | **96.7%** | recall@3: **91.7%**, recall@1: **78.3%** |
| MULTIVAC fixed-500 | vector | 78.3% | recall@3: 65.0%, recall@1: 46.7% |
| | bm25 | 93.3% | recall@3: 91.7%, recall@1: 80.0% |
| | hybrid (α=0.5) | 93.3% | recall@3: 91.7%, recall@1: 66.7% |
| NFCorpus fixed-500 | vector | 13.9% | recall@100: 35.4% |
| | bm25 | 11.6% | recall@100: 23.0% |
| | **hybrid (α=0.8, tuned)** | **14.4%** | recall@100: **36.0%** |
| NFCorpus structural-500 | vector | 13.8% | recall@100: 35.3% |
| | bm25 | 11.6% | recall@100: 23.0% |
| | **hybrid (α=0.8, tuned)** | **14.5%** | recall@100: **36.0%** |

Full per-query breakdowns are in `data/eval_results/*.json` (git-ignored,
regenerate with the commands below).

## Findings

**1. Retrieval method effectiveness is domain-dependent, not universal.**
BM25 dominates on MULTIVAC (brand names, product codes like "MLC", "PEAQ",
"GS1 Digital Link" — high proper-noun density rewards exact keyword match).
Vector search dominates on NFCorpus (technical medical abstracts vs.
colloquial queries — vocabulary mismatch rewards semantic match). Neither
method is a safe default; which one wins is a property of the corpus.

**2. Hybrid fusion only helps when implemented and tuned correctly** — this
took two rounds to get right:

- *Bug found and fixed*: an early version of hybrid fusion took each
  method's own top-20 and defaulted a chunk's score to 0 on whichever side
  didn't surface it in that top-20, even when its true score there was
  nonzero. This unfairly penalized chunks one method liked but the other
  didn't rank as highly. Fixed by scoring the full union of both methods'
  candidates against their *true* scores (`VectorStore.score` /
  `BM25Store.score`, exact re-scoring via FAISS `reconstruct()` and BM25's
  full `get_scores()`) instead of zero-filling.
- *Reproducibility bug found and fixed*: the fusion code briefly collected
  candidate ids into a Python `set()` before sorting. `set` iteration order
  depends on `PYTHONHASHSEED`, which is randomized per process — the exact
  same query, index, and alpha produced different recall@1 numbers
  (70.0% / 73.3% / 73.3%) across three separate runs, purely from
  score-tie-breaking order. Fixed by sorting candidate ids explicitly before
  fusion. Numbers in this file are from the fixed, deterministic version.

**3. Reciprocal Rank Fusion (RRF) is not a free win here.** RRF
(`score = Σ 1/(rrf_k + rank)`, scale-invariant, no alpha to tune) is the
default hybrid strategy in systems like Elasticsearch and Weaviate, so it
was implemented as a second fusion strategy for comparison. On both corpora
it under-performed a properly-tuned linear weighted sum (e.g. MULTIVAC
fixed-500: RRF hybrid recall@5 88.3% vs. linear 93.3%). RRF's advantage is
when two methods are comparably strong and their raw scores can't be
calibrated against each other; here one method is clearly stronger than the
other on each corpus, so linear fusion's ability to reflect *how much*
stronger (via actual score magnitude, not just rank) wins out.

**4. alpha is corpus-specific and worth tuning properly.** Swept alpha
0.1–0.9 on NFCorpus's official validation split (324 queries, separate from
the 323 test queries reported above) and picked the best (α=0.8, favoring
vector — consistent with finding #1). Evaluated that tuned value on the
held-out test split and it generalized: hybrid beat vector-only at every k
(5/10/20/100), not just the one it was tuned on.

**5. Chunking strategy matters more on longer documents.** MULTIVAC pages
(hundreds to thousands of words) show a real gap between fixed-size and
structural chunking (structural's hybrid: 96.7% vs. fixed's hybrid: 93.3% at
recall@5). NFCorpus abstracts are short enough that both strategies produce
~1 chunk/doc almost always (3,882 vs. 3,879 chunks for 3,633 docs) — chunking
strategy is a non-factor there by construction, not because one strategy is
secretly equivalent to the other in general.

## Caveats (read before quoting these numbers)

- **MULTIVAC's alpha=0.5 is untuned.** There's no held-out validation split
  for the 30-query hand-labeled set (it's too small to split further without
  making the eval noisier than the signal). The NFCorpus alpha=0.8 result is
  the methodologically sound one (tuned on validation, evaluated on held-out
  test).
- **NFCorpus recall@k looks low in absolute terms (13–36%) — this is
  expected, not a bug.** Queries average 38 relevant docs each (up to 475),
  so even a perfect oracle retriever caps out around 46% recall@5 / 62%
  recall@10 / 77% recall@20 given this dataset's relevance-judgment density.
  Our BM25 recall@100 (23.0%) lands within 2 points of BEIR's published
  official BM25 baseline (25.0%), which is the actual signal that the
  harness's implementation is sound — not the absolute recall number itself.
- **MULTIVAC's 30-query set is hand-labeled at the page level**, drafted by
  an LLM and reviewed by a human, not independently audited — treat it as a
  learning/demo eval set, not a rigorous benchmark, unlike NFCorpus.
- Both corpora use OpenAI `text-embedding-3-small` and the same simple
  regex tokenizer for BM25 (no stemming/lemmatization), so absolute numbers
  are not directly comparable to papers using different embedding models or
  Anserini's tokenizer/BM25 parameters (k1=0.9, b=0.4 vs. rank_bm25's
  defaults k1=1.5, b=0.75 used here).

## Reproducing these numbers

```bash
# MULTIVAC (uses the already-scraped data/knowledge_base.json)
python -m retrieval_lab.build_experiment_index --strategy fixed --chunk-size 500 --overlap 50 --name fixed-500
python -m retrieval_lab.build_experiment_index --strategy structural --max-tokens 500 --name structural-500
python -m retrieval_lab.eval.run_eval --index fixed-500 --k 1 3 5 --alpha 0.5
python -m retrieval_lab.eval.run_eval --index structural-500 --k 1 3 5 --alpha 0.5

# NFCorpus (downloads from Hugging Face on first run)
python -m retrieval_lab.build_nfcorpus_source
python -m retrieval_lab.build_experiment_index --strategy fixed --chunk-size 500 --overlap 50 \
  --name nfcorpus-fixed-500 --input retrieval_lab/data/nfcorpus_source/knowledge_base.json
python -m retrieval_lab.eval.run_eval --index nfcorpus-fixed-500 \
  --queries retrieval_lab/data/nfcorpus_source/eval_queries.json --k 5 10 20 100 --alpha 0.8

# RRF comparison (either corpus)
python -m retrieval_lab.eval.run_eval --index fixed-500 --k 1 3 5 --fusion rrf --tag rrf
```
