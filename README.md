# Web Harvest Chatbot

`Web Harvest Chatbot` is a config-driven starter for building a retrieval-augmented chatbot from websites and PDFs.

Paste a list of URLs into the web UI, click **Save and build**, and the app automatically scrapes, chunks, embeds, and indexes the content into Supabase pgvector — no command line required.

The full workflow:

1. Paste URLs in the web UI (or edit `config/sources.json` directly)
2. The app extracts and deduplicates all links from the pasted text
3. Scrapes HTML pages and extracts text from PDFs
4. Builds a merged knowledge base
5. Chunks and embeds content into Supabase pgvector
6. Chat with the indexed corpus from the same UI

## What it includes

- **Web UI source management**: paste raw text containing URLs, the app extracts and deduplicates links automatically
- **One-click ingestion**: "Save and build" triggers the full pipeline in the background; build status is shown live in the sidebar
- **Automatic database sync**: removing a source from the UI also deletes its chunks from the vector database
- Config-driven source list in `config/sources.json` (synced automatically with the UI)
- HTML scraping and PDF text extraction in `scraper.py`
- Vector indexing in `build_index.py`
- One-command ingestion runner in `pipeline.py`
- Supabase SQL for vector search and chat persistence
- Next.js frontend with anonymous Supabase auth
- Shared branding config in `config/project.json`

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
OPENAI_CHAT_MODEL=
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

### 3. Initialize Supabase

Run these scripts in Supabase SQL Editor:

```text
sql/setup_schema.sql
sql/web_schema.sql
```

Also enable anonymous auth in Supabase.

### 4. Start the web app

```bash
npm run dev
```

Open `http://localhost:3000` and start an anonymous session.

### 5. Add sources and build

1. Click **Add sources** in the sidebar
2. Paste any text containing URLs (plain list, email, notes — the app extracts all links)
3. Click **Save and build**

The app scrapes the URLs, chunks the content, generates embeddings, and indexes everything into Supabase. Build progress is shown live in the sidebar. When the build finishes, the knowledge base is ready to query.

To remove a source, click the **x** next to it in the sidebar. Its chunks are deleted from the database immediately.

#### Advanced: manual ingestion from the command line

```bash
python pipeline.py
python scraper.py --test
python scraper.py --limit 10
python build_index.py --reset
python pipeline.py --test --reset-index
```

#### Advanced: edit sources directly

You can also edit `config/sources.json` by hand. Each entry can be a plain URL string or an object:

```json
{ "url": "https://example.com", "title": "Example", "type": "html", "category": "website" }
```

See `config/sources.example.json` for reference.

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
