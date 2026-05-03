-- Legacy migration helper.
-- Prefer sql/schema.sql for the current FastAPI backend.
--
-- Run this in Supabase SQL Editor to remove the auth.users FK constraint
-- so that conversations can use browser-local generated user IDs.

alter table conversations drop constraint if exists conversations_user_id_fkey;
alter table conversations alter column user_id type text using user_id::text;
