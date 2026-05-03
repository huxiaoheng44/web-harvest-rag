-- Current schema for the FastAPI backend.
--
-- Run this file in Supabase SQL Editor for the current project setup.
-- It does not require Supabase Auth. The browser stores a local UUID and
-- sends it to FastAPI as user_id.

create extension if not exists pgcrypto;
create extension if not exists vector;

create table if not exists chunks (
    id            text primary key,
    doc_id        text not null,
    title         text,
    url           text,
    category      text,
    chunk_idx     int,
    total_chunks  int,
    content       text not null,
    embedding     vector(1536)
);

create index if not exists chunks_embedding_idx
on chunks
using hnsw (embedding vector_cosine_ops);

create index if not exists chunks_category_idx on chunks (category);

create or replace function public.match_chunks(
  query_embedding vector(1536),
  match_count int default 6
)
returns table (
  id text,
  doc_id text,
  title text,
  url text,
  category text,
  content text,
  chunk_idx int,
  total_chunks int,
  similarity float
)
language sql
stable
as $$
  select
    chunks.id,
    chunks.doc_id,
    chunks.title,
    chunks.url,
    chunks.category,
    chunks.content,
    chunks.chunk_idx,
    chunks.total_chunks,
    1 - (chunks.embedding <=> query_embedding) as similarity
  from chunks
  where chunks.embedding is not null
  order by chunks.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;

create table if not exists app_users (
    id text primary key,
    display_name text not null,
    created_at timestamptz not null default timezone('utc', now()),
    last_seen_at timestamptz not null default timezone('utc', now())
);

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    user_id text not null references app_users(id) on delete cascade,
    title text not null default 'New chat',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null check (role in ('system', 'user', 'assistant')),
    content text not null,
    sources jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

-- Compatibility with databases that previously used the legacy Supabase Auth schema.
alter table conversations drop constraint if exists conversations_user_id_fkey;
alter table conversations alter column user_id type text using user_id::text;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists conversations_set_updated_at on conversations;
create trigger conversations_set_updated_at
before update on conversations
for each row execute function public.set_updated_at();

create index if not exists conversations_user_updated_idx
on conversations (user_id, updated_at desc);

create index if not exists messages_conversation_created_idx
on messages (conversation_id, created_at asc);
