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
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:3000
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

- `sql/schema.sql`

Supabase Auth is not required for the current FastAPI flow. The browser stores a local UUID and display name.

## 4. Ingest content

Install Python packages:

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
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

## 5. Run the FastAPI backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 6. Run the web app

Install Node packages and start the app:

```bash
npm install
npm run dev
```

Open `http://localhost:3000` and enter a display name to start a local weak-identity session.
