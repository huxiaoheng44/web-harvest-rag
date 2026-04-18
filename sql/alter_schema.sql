-- Run this in Supabase SQL Editor to remove the auth.users FK constraint
-- so that conversations can use anonymous client-generated user IDs.

-- Drop the foreign key so user_id no longer needs to exist in auth.users
ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_user_id_fkey;

-- Change user_id to text so it accepts any string ID (UUID from localStorage)
ALTER TABLE conversations ALTER COLUMN user_id TYPE text USING user_id::text;
