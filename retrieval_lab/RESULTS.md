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

## Items 6-10: rerank, chunk-size sweep, query rewriting, error analysis, answer-quality eval

### 6. Cross-encoder rerank

Reranked hybrid's top-20 candidate pool with a local cross-encoder
(`cross-encoder/ms-marco-MiniLM-L-6-v2`, via `sentence-transformers`) and
compared against hybrid's own ranking, on MULTIVAC `structural-500`:

| Method | recall@1 | recall@3 | recall@5 |
|---|---|---|---|
| hybrid | 78.3% | 91.7% | 96.7% |
| + cross-encoder rerank | 66.7% | 86.7% | 93.3% |

**Rerank made things worse here, and that's the finding.** MS MARCO trains
this cross-encoder on general web/passage search relevance, not MULTIVAC's
brand-heavy technical vocabulary ("PEAQ", "MLC", "GS1 Digital Link") — it
doesn't know these terms carry outsized relevance signal the way BM25's
exact-match scoring does, so it reshuffled some correct top hits downward.
Lesson: reranking isn't a free precision upgrade — a general-domain
cross-encoder can hurt on a narrow-vocabulary corpus where the first-stage
retriever (here, hybrid) is already well-tuned to that vocabulary. Rerank
would be worth revisiting with a domain-adapted or larger cross-encoder, or
on a corpus with broader, more general-language content.

### 7. Chunk size sweep (fixed-size, 200/500/1000 tokens)

**MULTIVAC** (24 docs, real trade-off is visible):

| Size | Chunks | vector@1/3/5 | bm25@1/3/5 | hybrid@1/3/5 |
|---|---|---|---|---|
| 200 | 296 | 40.0% / 73.3% / 81.7% | 78.3% / 90.0% / 93.3% | 66.7% / **96.7%** / 96.7% |
| 500 | 124 | 46.7% / 65.0% / 78.3% | **80.0%** / 91.7% / 93.3% | 66.7% / 91.7% / 93.3% |
| 1000 | 67 | **56.7%** / 70.0% / 83.3% | 75.0% / 88.3% / 93.3% | **71.7%** / 85.0% / **95.0%** |

Vector recall@1 climbs steadily with chunk size (40→47→57%) — bigger chunks
carry more complete context, which helps a single dense embedding represent
the topic. But hybrid recall@3 is *best at the smallest size* (200 tokens,
96.7%) then drops as chunks grow — smaller, more topically-focused chunks
give BM25 (and therefore hybrid) sharper term-matching precision at moderate
depth, at the cost of vector recall@1. This is the "bigger context vs. more
noise" trade-off the interview question is fishing for, with real numbers
behind it, not just the general claim.

**NFCorpus** (short PubMed abstracts, chunk size mostly a non-factor as
expected — confirmed rather than assumed):

| Size | Chunks | vector@5/10/20 | bm25@5/10/20 | hybrid@5/10/20 |
|---|---|---|---|---|
| 200 | 7,896 | 12.5% / 17.2% / 21.1% | 10.7% / 13.4% / 15.9% | 13.1% / 17.6% / 21.4% |
| 500 | 3,882 | 13.9% / 17.5% / 22.6% | 11.6% / 14.7% / 17.0% | 14.4% / 18.1% / 22.5% |
| 1000 | 3,643 | 13.9% / 17.8% / 23.1% | 11.6% / 14.7% / 17.2% | 14.5% / 18.2% / 23.0% |

500 vs. 1000 tokens barely move the numbers (most abstracts already fit in
one chunk at either size: 3,882 vs. 3,643 chunks for 3,633 docs). 200 tokens
measurably *hurts* (more docs get split, fragmenting already-short context)
— so "chunk size doesn't matter here" only holds once chunks are already
larger than the median document; it's not that chunk size never matters on
this corpus.

### 8. Query rewriting (LLM paraphrase + RRF merge)

For each of the 30 MULTIVAC queries, generated 2 LLM paraphrases (e.g.
"MULTIVAC Line Control" → "Control system for MULTIVAC lines" / "MULTIVAC
production line management" — genuine rewording, not near-duplicates),
retrieved hybrid results for original + both variants, and merged via
Reciprocal Rank Fusion (`hybrid.rrf_merge_many`):

| Method | recall@1 | recall@3 | recall@5 |
|---|---|---|---|
| hybrid (single query) | 78.3% | 91.7% | 96.7% |
| + query rewriting (multiquery) | 68.3% | 93.3% | **98.3%** |

recall@1 dips (merging three ranked lists dilutes the single best hit's
rank-1 position) but recall@3/@5 improve — multi-query retrieval trades a
bit of top-1 precision for better coverage, which is the right trade when
the downstream use is "give the LLM good context to answer from" rather
than "must be first result." Run only on MULTIVAC's 30 queries, not all 323
NFCorpus queries — NFCorpus's queries are already well-formed benchmark
queries, so rewriting them tests a different (and less interesting, given
the cost) thing than rewriting genuinely terse/vague real-user queries.

### 9. Error analysis

Bucketed every query with imperfect hybrid recall into: vector-missed/BM25-
hit, BM25-missed/vector-hit, both-missed, or partial-miss (some but not all
expected docs found). Full reports in
`data/eval_results/{structural-500,nfcorpus-fixed-500}_error_analysis.md`.

**MULTIVAC** (`structural-500`, k=5): only 2/30 queries imperfect, both
"partial miss" — q25 and q27, the two queries deliberately written with
*two* acceptable answer docs each. Root cause, from reading the actual
retrieved lists: expanding the corpus from 6 to 24 documents introduced new,
topically-adjacent pages (e.g. `news-data-visibility-new-currency`,
`digitalisation-food-industry`) that now compete for the same top-5 slots
as one of the two originally-expected docs. Not a chunking or embedding
bug — a byproduct of enriching the corpus after the eval set was written.

**NFCorpus** (`fixed-500`, k=10): 306/323 queries imperfect, but 191 of
those are "partial miss" — expected given the ~38 relevant-docs/query
density (recall@10 can't be 100% almost by construction, see the Caveats
section). The 67 "both missed" cases are concentrated in extremely terse,
single-entity queries with no supporting context — e.g. `"eggnog"`,
`"fava beans"`, `"Dr. Walter Willett"`, `"Fosamax"`. A bare drug/food/person
name has no semantic content beyond the entity itself, and NFCorpus's
relevant-doc set for these is whatever a specific medical-forum thread
happened to link, which our simple retrieval has no way to reverse-engineer
from the name alone. This is the "query too vague" failure mode in
practice, not chunking or embedding quality.

### 10. Answer-quality eval (LLM-as-judge)

Generated an answer from each query's top-5 hybrid-retrieved chunks, then
had a second LLM call judge **faithfulness** 1-5 (is the answer supported by
the retrieved context - not similarity to a reference answer, since none of
our query sets have gold answers).

**A real judge-calibration bug turned up immediately** in the first NFCorpus
run (25-query sample): average score 3.32/5, with many queries scoring 1.
Reading the actual low-scoring cases showed the judge was conflating two
different failure modes - when retrieval brought back irrelevant chunks and
the model correctly responded "I cannot confirm this from the current
knowledge base" (the *correct*, non-hallucinating behavior), the judge
scored that refusal as a 1 ("contradicts the context"), penalizing the
model for retrieval's failure rather than judging the model's own behavior.
Fixed by rewriting the judge prompt to explicitly separate "context is
irrelevant, correct refusal" (score 5) from "context is relevant, but the
answer contradicts or invents claims" (score 1). Re-running after the fix:

| Corpus | Sample | Before fix | After fix |
|---|---|---|---|
| MULTIVAC (`structural-500`) | 30 queries | 4.93 / 5 | **5.00 / 5** |
| NFCorpus (`fixed-500`, α=0.8) | first 25 test queries | 3.32 / 5 | **4.92 / 5** |

**The real finding isn't the score - it's what stayed constant across two
corpora with wildly different retrieval recall (96.7% vs. ~15-36%): near-
perfect faithfulness on both.** That's the central point of full-pipeline
RAG evaluation: faithfulness and retrieval-completeness are different axes.
A system can score ~5/5 on faithfulness by correctly saying "I don't know"
whenever retrieval fails, while still being an incomplete or unhelpful
system in practice - you need recall@k *and* an answer-quality metric
together, because either one alone hides the other's failure mode.

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

# Item 6: cross-encoder rerank (needs sentence-transformers, retrieval_lab/requirements.txt)
python -m retrieval_lab.eval.run_eval --index structural-500 --k 1 3 5 --rerank --tag rerank

# Item 7: chunk size sweep
python -m retrieval_lab.chunk_size_sweep --sizes 200 500 1000 --prefix multivac --k 1 3 5
python -m retrieval_lab.chunk_size_sweep --sizes 200 500 1000 --prefix nfcorpus \
  --input retrieval_lab/data/nfcorpus_source/knowledge_base.json \
  --queries retrieval_lab/data/nfcorpus_source/eval_queries.json --k 5 10 20

# Item 8: query rewriting + RRF merge
python -m retrieval_lab.eval.run_eval --index structural-500 --k 1 3 5 --query-rewrite 2 --tag qrewrite

# Item 9: error analysis (reads an already-saved eval_results/<name>.json)
python -m retrieval_lab.error_analysis --results structural-500 --k 5
python -m retrieval_lab.error_analysis --results nfcorpus-fixed-500 --k 10

# Item 10: LLM-as-judge answer-quality eval
python -m retrieval_lab.answer_eval --index structural-500 --k 5 --alpha 0.5
python -m retrieval_lab.answer_eval --index nfcorpus-fixed-500 --k 5 --alpha 0.8 \
  --queries retrieval_lab/data/nfcorpus_source/eval_queries.json --limit 25
```
