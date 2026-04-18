# Setup

## 1. Configure your sources

Edit `config/sources.json` and list the HTML pages and PDF URLs you want to ingest.

Each entry supports:

- `id`
- `title`
- `url`
- `category`
- `type` as `html` or `pdf`

## 2. Configure environment variables

Copy `.env.example` to `.env` and set:

```env
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Optional tuning:

```env
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
CHUNK_CHARS=1200
CHUNK_OVERLAP_CHARS=150
```

## 3. Initialize Supabase

Run these scripts in Supabase SQL Editor:

- `sql/setup_schema.sql`
- `sql/web_schema.sql`

Enable anonymous auth in Supabase so the chat UI can create browser-scoped sessions.

## 4. Ingest content

Install Python packages:

```bash
pip install -r requirements.txt
```

Run the full pipeline:

```bash
python pipeline.py
```

Useful variants:

```bash
python scraper.py --test
python build_index.py --reset
python pipeline.py --test --reset-index
```

## 5. Run the web app

Install Node packages and start the app:

```bash
npm install
npm run dev
```

Open `http://localhost:3000` and start an anonymous session.
