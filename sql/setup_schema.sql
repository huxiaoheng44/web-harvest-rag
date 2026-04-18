-- Run this once in Supabase: Dashboard → SQL Editor → New query → Run
-- Step 1: Enable pgvector
create extension if not exists vector;

-- Step 2: Create chunks table
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

-- Step 3: HNSW index for cosine similarity search
create index if not exists chunks_embedding_idx
on chunks
using hnsw (embedding vector_cosine_ops);

-- Step 4: Index on category for filtered searches
create index if not exists chunks_category_idx on chunks (category);
