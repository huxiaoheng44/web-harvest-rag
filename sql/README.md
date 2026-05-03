# SQL Files

Use `schema.sql` for the current FastAPI backend.

## Current Schema

```text
schema.sql
```

Creates the schema used by the FastAPI migration:

- `chunks`
- `match_chunks()`
- `app_users`
- `conversations`
- `messages`
- vector/search indexes
- `updated_at` trigger for conversations

This version does not require Supabase Auth. The browser stores a generated local UUID and sends it to FastAPI as `user_id`.

## Legacy Supabase Auth Schema

These files are kept under `legacy/` only as historical reference for the old Next.js API route implementation:

```text
legacy/setup_schema.sql
legacy/web_schema.sql
legacy/alter_schema.sql
```

Do not run the legacy files for the current FastAPI flow unless you are intentionally restoring the older Supabase Auth architecture.
