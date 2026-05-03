-- Legacy Supabase Auth schema fragment.
-- For the current FastAPI backend, use sql/schema.sql instead.
--
-- Run this once in Supabase: Dashboard -> SQL Editor -> New query -> Run

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
