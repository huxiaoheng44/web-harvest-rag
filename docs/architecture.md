# Architecture

`Web Harvest RAG` is built as a simple five-stage pipeline:

1. `config/sources.json` defines which pages and PDFs belong to the corpus.
2. `scraper.py` fetches sources, extracts readable text, and writes one JSON file per source into `data/pages/`.
3. `scraper.py` also merges the crawl into `data/knowledge_base.json`.
4. `build_index.py` chunks the merged corpus, generates embeddings, and stores them in Supabase `chunks`.
5. The Next.js app retrieves relevant chunks, calls the chat model, and stores conversations in Supabase.

## Why this version is more general

- No site-specific URL list is hardcoded in Python.
- Branding and UI copy live in `config/project.json`.
- Crawled artifacts are treated as generated output, not source code.
- The web app now uses Supabase anonymous auth instead of a local fake user id.
