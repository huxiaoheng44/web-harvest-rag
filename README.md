# Web Harvest Chatbot

`Web Harvest Chatbot` is a config-driven starter for building a retrieval-augmented chatbot from websites and PDFs.

It is designed for the workflow you were building manually before:

1. Define source URLs
2. Crawl HTML pages
3. Extract text from PDFs
4. Build a merged knowledge base JSON
5. Chunk and embed into Supabase pgvector
6. Chat with the indexed corpus from a Next.js UI

## What it includes

- Config-driven source ingestion through `config/sources.json`
- HTML scraping and PDF text extraction in `scraper.py`
- Vector indexing in `build_index.py`
- One-command ingestion runner in `pipeline.py`
- Supabase SQL for vector search and chat persistence
- Next.js frontend with anonymous Supabase auth
- Shared branding config in `config/project.json`
- In-app source management with background build status

## UI example

### Add sources

![Add sources modal](readme-source/add-source.png)

### Chat interface

![Chat interface](readme-source/chat-example.png)

## Project structure

- `config/project.json`: app name, assistant name, and UI copy
- `config/sources.json`: active crawl targets for this project
- `config/sources.example.json`: reusable sample source configuration
- `scraper.py`: crawls pages and PDFs into `data/`
- `build_index.py`: chunks content and writes embeddings to Supabase
- `pipeline.py`: runs scrape + index in sequence
- `scripts/run-pipeline-background.mjs`: runs rebuilds in the background
- `sql/`: database schema and RPC definitions
- `app/`, `components/`, `lib/`: web app and API routes
- `docs/setup/SETUP.md`: detailed setup instructions
- `docs/architecture.md`: high-level system design

## How the pipeline works

```text
config/sources.json
  -> scraper.py
  -> data/pages/*.json
  -> data/knowledge_base.json
  -> build_index.py
  -> Supabase pgvector
  -> Next.js chat UI
```

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
npm install
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and set:

```env
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Optional chunk tuning:

```env
CHUNK_CHARS=1200
CHUNK_OVERLAP_CHARS=150
```

### 3. Configure your sources

You can either edit `config/sources.json` directly or add sources from the web UI.

The app accepts plain URL lists or mixed pasted text containing URLs.

Each source supports:

- `id`
- `title`
- `url`
- `category`
- `type` as `html` or `pdf`

You can start from `config/sources.example.json`.

### 4. Initialize Supabase

Run these scripts in Supabase SQL Editor:

```text
sql/setup_schema.sql
sql/web_schema.sql
```

Also enable anonymous auth in Supabase.

### 5. Run ingestion

```bash
python pipeline.py
```

Or trigger a rebuild directly from the web UI after adding sources.

Useful variants:

```bash
python scraper.py --test
python scraper.py --limit 10
python build_index.py --reset
python pipeline.py --test --reset-index
```

### 6. Start the web app

```bash
npm run dev
```

Open `http://localhost:3000` and start an anonymous session.

## Example prompts

```text
What is MULTIVAC Smart Services?
What is MULTIVAC Line Control used for?
Summarize the Production 4.0 page in 3 bullet points.
Compare Smart Services and Line Control.
Which sources mention productivity or efficiency?
Summarize the PEAQ brochure in 5 bullet points.
```

## Example use cases

- Company knowledge chatbot from marketing pages and brochures
- Customer support assistant from docs + downloadable PDFs
- Research assistant for niche websites with mixed HTML/PDF content
- Lightweight vertical RAG prototype before building a larger ingestion stack

## Notes

- `data/pages/` and `data/knowledge_base.json` are generated artifacts and ignored by git.
- `data/build-status.json` and `data/build.log` are local runtime artifacts and ignored by git.
- The vector search uses `match_chunks()` from `sql/web_schema.sql`.
- The app stores chat history in Supabase conversations and messages tables.
- The current scraper is intentionally simple and easy to adapt, not a full distributed crawler.

## License

This repository is licensed under the MIT License.
