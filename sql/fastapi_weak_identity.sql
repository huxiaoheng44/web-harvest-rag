-- Run this when using the FastAPI backend with local weak identity.
-- The browser keeps a generated client UUID in localStorage and sends it to FastAPI.
-- FastAPI uses SUPABASE_SERVICE_ROLE_KEY, so browser-side Supabase Auth is no longer required.

alter table conversations drop constraint if exists conversations_user_id_fkey;
alter table conversations alter column user_id type text using user_id::text;

create table if not exists app_users (
    id text primary key,
    display_name text not null,
    created_at timestamptz not null default timezone('utc', now()),
    last_seen_at timestamptz not null default timezone('utc', now())
);
