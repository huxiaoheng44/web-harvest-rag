# Web Harvest RAG

Web Harvest RAG is a configurable starter for building a retrieval-augmented chatbot from websites and PDFs.

It gives you one end-to-end flow:

1. Configure source URLs in `config/sources.json`
2. Crawl HTML pages and extract PDF text with `scraper.py`
3. Merge everything into `data/knowledge_base.json`
4. Chunk and embed the corpus into Supabase pgvector with `build_index.py`
5. Chat with the indexed corpus from the Next.js web UI

## Project structure

- `config/project.json`: app branding and shared UI copy
- `config/sources.json`: the websites and PDFs to ingest
- `scraper.py`: HTML and PDF ingestion
- `build_index.py`: vector indexing into Supabase
- `pipeline.py`: optional one-command ingestion runner
- `sql/`: database schema and chat tables
- `app/`, `components/`, `lib/`: Next.js frontend and API routes

## Quick start

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Install web dependencies:

```bash
npm install
```

3. Copy `.env.example` to `.env` and fill in your OpenAI and Supabase values.

4. Update `config/sources.json` with your own URLs.

5. Run the database SQL:

```text
sql/setup_schema.sql
sql/web_schema.sql
```

6. Build the knowledge base and index:

```bash
python pipeline.py
```

7. Start the web app:

```bash
npm run dev
```

## Notes

- `data/pages/` and `data/knowledge_base.json` are generated files and are ignored by git.
- The web app expects Supabase anonymous auth to be enabled.
- The vector search uses `match_chunks()` from `sql/web_schema.sql`.
