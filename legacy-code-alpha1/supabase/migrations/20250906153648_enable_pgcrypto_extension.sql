-- Enable pgcrypto extension for gen_random_bytes() function
-- Required for secure session ID generation in auth service

-- Check if extension already exists before creating
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Verify the extension is enabled
SELECT * FROM pg_extension WHERE extname = 'pgcrypto';

-- Test that gen_random_bytes works
SELECT encode(gen_random_bytes(16), 'hex') as test_random_bytes;