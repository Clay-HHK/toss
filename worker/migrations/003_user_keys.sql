-- T2-3: user public-key columns for Tier 2 end-to-end encryption.
--
-- All columns are nullable. Users who have not enrolled yet simply carry
-- NULLs, which the Phase A client treats as "fall back to plaintext".
-- Phase B will flip the default and start warning on missing keys.
ALTER TABLE users ADD COLUMN public_key TEXT;            -- toss1<base64url> X25519 pubkey
ALTER TABLE users ADD COLUMN signing_public_key TEXT;    -- tossk1<base64url> Ed25519 pubkey
ALTER TABLE users ADD COLUMN public_key_proof TEXT;      -- base64url Ed25519 signature
ALTER TABLE users ADD COLUMN public_key_issued_at INTEGER; -- unix seconds (matches proof)
ALTER TABLE users ADD COLUMN public_key_updated_at TEXT;   -- ISO 8601 server-side timestamp
