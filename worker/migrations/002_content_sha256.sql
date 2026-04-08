-- T1-3: add content SHA-256 column to documents for end-to-end integrity check.
-- Nullable: legacy rows and old clients will leave it NULL; readers must tolerate that.
ALTER TABLE documents ADD COLUMN content_sha256 TEXT;
