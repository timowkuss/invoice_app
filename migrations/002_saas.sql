ALTER TABLE document_items DROP CONSTRAINT IF EXISTS document_items_match_status_check;
ALTER TABLE document_items ADD CONSTRAINT document_items_match_status_check
CHECK (match_status IN ('pending','matched','manual','not_found','needs_review'));
CREATE INDEX IF NOT EXISTS idx_document_store_hash ON documents(store_id, original_file_hash);
CREATE INDEX IF NOT EXISTS idx_document_queue ON documents(status, created_at);
CREATE TABLE IF NOT EXISTS login_attempts (
    key TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, window_start DOUBLE PRECISION NOT NULL
);
