# FastAPI Backend

This is the initial FastAPI migration for the RAG backend.

## Environment

Use the project root `.env`:

```env
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:3000
```

The frontend no longer needs `NEXT_PUBLIC_SUPABASE_URL` or `NEXT_PUBLIC_SUPABASE_ANON_KEY` for this flow.

## Database Migration

Run this SQL in Supabase before using the FastAPI weak identity flow:

```text
sql/fastapi_weak_identity.sql
```

It removes the dependency on `auth.users` for conversations and adds a small `app_users` table for browser-local identities.

## Run Locally

From the repository root:

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then run the frontend separately:

```bash
npm run dev
```

Useful URLs:

```text
FastAPI docs: http://localhost:8000/docs
Frontend:     http://localhost:3000
```
