-- Run this in Supabase SQL Editor after sql/setup_schema.sql.

create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text,
    full_name text,
    avatar_url text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
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

create index if not exists conversations_user_updated_idx
on conversations (user_id, updated_at desc);

create index if not exists messages_conversation_created_idx
on messages (conversation_id, created_at asc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on profiles;
create trigger profiles_set_updated_at
before update on profiles
for each row execute function public.set_updated_at();

drop trigger if exists conversations_set_updated_at on conversations;
create trigger conversations_set_updated_at
before update on conversations
for each row execute function public.set_updated_at();

alter table profiles enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;

drop policy if exists "profiles_select_own" on profiles;
create policy "profiles_select_own"
on profiles for select
using (auth.uid() = id);

drop policy if exists "profiles_update_own" on profiles;
create policy "profiles_update_own"
on profiles for update
using (auth.uid() = id)
with check (auth.uid() = id);

drop policy if exists "conversations_select_own" on conversations;
create policy "conversations_select_own"
on conversations for select
using (auth.uid() = user_id);

drop policy if exists "conversations_insert_own" on conversations;
create policy "conversations_insert_own"
on conversations for insert
with check (auth.uid() = user_id);

drop policy if exists "conversations_update_own" on conversations;
create policy "conversations_update_own"
on conversations for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "conversations_delete_own" on conversations;
create policy "conversations_delete_own"
on conversations for delete
using (auth.uid() = user_id);

drop policy if exists "messages_select_own" on messages;
create policy "messages_select_own"
on messages for select
using (
  exists (
    select 1 from conversations
    where conversations.id = messages.conversation_id
      and conversations.user_id = auth.uid()
  )
);

drop policy if exists "messages_insert_own" on messages;
create policy "messages_insert_own"
on messages for insert
with check (
  exists (
    select 1 from conversations
    where conversations.id = messages.conversation_id
      and conversations.user_id = auth.uid()
  )
);

drop policy if exists "messages_delete_own" on messages;
create policy "messages_delete_own"
on messages for delete
using (
  exists (
    select 1 from conversations
    where conversations.id = messages.conversation_id
      and conversations.user_id = auth.uid()
  )
);

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
