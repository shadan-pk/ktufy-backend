-- =============================================================================
-- KTUfy V2 Pipeline — DB Migration
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- =============================================================================

-- ─── 1. Patch uploaded_files with missing columns ────────────────────────────
-- The table already exists; these statements are safe to run multiple times.

ALTER TABLE uploaded_files
    ADD COLUMN IF NOT EXISTS original_filename  TEXT,
    ADD COLUMN IF NOT EXISTS file_type          TEXT DEFAULT 'pdf',
    ADD COLUMN IF NOT EXISTS file_size          BIGINT,
    ADD COLUMN IF NOT EXISTS regulation         TEXT DEFAULT '2019',
    ADD COLUMN IF NOT EXISTS error_message      TEXT,
    ADD COLUMN IF NOT EXISTS subjects_count     INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS modules_count      INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS topics_count       INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS processed_at       TIMESTAMPTZ;


-- ─── 2. Create processing_jobs table ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS processing_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id             UUID REFERENCES uploaded_files(id) ON DELETE SET NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    progress            INTEGER NOT NULL DEFAULT 0,
    message             TEXT,
    subjects_processed  INTEGER DEFAULT 0,
    total_subjects      INTEGER DEFAULT 0,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    error               TEXT,
    result              JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast lookups by file_id and status
CREATE INDEX IF NOT EXISTS idx_processing_jobs_file_id ON processing_jobs(file_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status  ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_created ON processing_jobs(created_at DESC);

-- ─── 3. Row-Level Security ────────────────────────────────────────────────────
-- Allow service_role full access (used by supabase_admin_client).
-- Deny all anon access.

ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_all" ON processing_jobs;
CREATE POLICY "service_role_all"
    ON processing_jobs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- =============================================================================
-- Done. Verify with:
--   SELECT * FROM processing_jobs LIMIT 5;
--   SELECT column_name FROM information_schema.columns
--     WHERE table_name = 'uploaded_files' ORDER BY ordinal_position;
-- =============================================================================
