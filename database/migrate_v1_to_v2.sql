-- ═══════════════════════════════════════════════════════════════════════════════
-- KTUfy Migration: V1 → V2
-- Run this in Supabase SQL Editor to migrate from V1 to V2 schema
-- ═══════════════════════════════════════════════════════════════════════════════

-- ⚠️ WARNING: This will DELETE all existing syllabus embeddings data!
-- Make sure you're okay with losing current data before running this.

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Drop V1 Functions
-- ═══════════════════════════════════════════════════════════════════════════════

DROP FUNCTION IF EXISTS search_syllabus(vector(384), INT, INT, TEXT, TEXT);
DROP FUNCTION IF EXISTS search_syllabus(vector(768), INT, INT, TEXT, TEXT);
DROP FUNCTION IF EXISTS get_syllabus_stats();

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 2: Drop V1 Triggers
-- ═══════════════════════════════════════════════════════════════════════════════

DROP TRIGGER IF EXISTS syllabus_embeddings_updated_at ON syllabus_embeddings;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 3: Drop V1 Tables (CASCADE drops dependent objects)
-- ═══════════════════════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS processing_jobs CASCADE;
DROP TABLE IF EXISTS syllabus_embeddings CASCADE;
-- Keep uploaded_files table as it's compatible

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 4: Create V2 Schema
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable pgvector extension (should already be enabled)
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Syllabus Embeddings Table V2
-- Stores proper content chunks with rich metadata
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE syllabus_embeddings (
    id BIGSERIAL PRIMARY KEY,
    
    -- Chunk identification (NEW in V2)
    chunk_id TEXT UNIQUE,                    -- e.g., "cs201_m1_overview"
    chunk_type TEXT NOT NULL DEFAULT 'unknown', -- syllabus_content, topic_list, topic_detail, course_outcomes, references
    
    -- Content (what we embed and retrieve)
    content TEXT NOT NULL,
    
    -- Vector embedding (768 dimensions for BAAI/bge-base-en-v1.5)
    embedding vector(768),
    
    -- Subject metadata
    subject_code TEXT,
    subject_name TEXT,
    
    -- Module metadata (NEW in V2: module_id)
    module_id TEXT,                          -- Canonical ID: "cs201_m1"
    module_number INTEGER,
    module_name TEXT,
    
    -- Topic/Concept metadata (NEW in V2: topic_id)
    topic_id TEXT,                           -- Canonical ID: "cs201_m1_arrays"
    topic_name TEXT,
    
    -- Filtering metadata
    semester INTEGER,
    branch TEXT,
    regulation TEXT DEFAULT '2019',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- V2 Indexes
-- ═══════════════════════════════════════════════════════════════════════════════

-- Vector similarity search (HNSW is faster than IVFFlat)
CREATE INDEX syllabus_embeddings_embedding_hnsw_idx 
ON syllabus_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Chunk type for filtering by content type
CREATE INDEX idx_chunk_type ON syllabus_embeddings(chunk_type);

-- Filtering indexes
CREATE INDEX idx_semester ON syllabus_embeddings(semester);
CREATE INDEX idx_branch ON syllabus_embeddings(branch);
CREATE INDEX idx_subject ON syllabus_embeddings(subject_code);
CREATE INDEX idx_regulation ON syllabus_embeddings(regulation);
CREATE INDEX idx_module ON syllabus_embeddings(module_id);
CREATE INDEX idx_topic ON syllabus_embeddings(topic_id);

-- Composite indexes for common queries
CREATE INDEX idx_subject_module ON syllabus_embeddings(subject_code, module_number);
CREATE INDEX idx_sem_branch_reg ON syllabus_embeddings(semester, branch, regulation);

-- Full text search
CREATE INDEX idx_content_fts 
ON syllabus_embeddings 
USING GIN (to_tsvector('english', content));

-- ═══════════════════════════════════════════════════════════════════════════════
-- V2 Functions
-- ═══════════════════════════════════════════════════════════════════════════════

-- Main similarity search with chunk_type filtering
CREATE OR REPLACE FUNCTION search_syllabus_v2(
    query_embedding vector(768),
    match_count INT DEFAULT 5,
    filter_semester INT DEFAULT NULL,
    filter_branch TEXT DEFAULT NULL,
    filter_subject TEXT DEFAULT NULL,
    filter_regulation TEXT DEFAULT NULL,
    filter_chunk_types TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    chunk_id TEXT,
    chunk_type TEXT,
    content TEXT,
    subject_code TEXT,
    subject_name TEXT,
    module_id TEXT,
    module_number INTEGER,
    module_name TEXT,
    topic_id TEXT,
    topic_name TEXT,
    semester INTEGER,
    branch TEXT,
    regulation TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        se.id,
        se.chunk_id,
        se.chunk_type,
        se.content,
        se.subject_code,
        se.subject_name,
        se.module_id,
        se.module_number,
        se.module_name,
        se.topic_id,
        se.topic_name,
        se.semester,
        se.branch,
        se.regulation,
        1 - (se.embedding <=> query_embedding) AS similarity
    FROM syllabus_embeddings se
    WHERE 
        (filter_semester IS NULL OR se.semester = filter_semester)
        AND (filter_branch IS NULL OR se.branch = filter_branch)
        AND (filter_subject IS NULL OR se.subject_code = filter_subject)
        AND (filter_regulation IS NULL OR se.regulation = filter_regulation)
        AND (filter_chunk_types IS NULL OR se.chunk_type = ANY(filter_chunk_types))
    ORDER BY se.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Get chunks by concept ID
CREATE OR REPLACE FUNCTION get_concept_chunks(
    concept_id TEXT,
    chunk_types TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    chunk_id TEXT,
    chunk_type TEXT,
    content TEXT,
    module_name TEXT,
    topic_name TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        se.id,
        se.chunk_id,
        se.chunk_type,
        se.content,
        se.module_name,
        se.topic_name
    FROM syllabus_embeddings se
    WHERE 
        se.topic_id = concept_id
        AND (chunk_types IS NULL OR se.chunk_type = ANY(chunk_types))
    ORDER BY se.chunk_type;
END;
$$;

-- Get chunks by module ID
CREATE OR REPLACE FUNCTION get_module_chunks(
    target_module_id TEXT,
    chunk_types TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    chunk_id TEXT,
    chunk_type TEXT,
    content TEXT,
    topic_id TEXT,
    topic_name TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        se.id,
        se.chunk_id,
        se.chunk_type,
        se.content,
        se.topic_id,
        se.topic_name
    FROM syllabus_embeddings se
    WHERE 
        se.module_id = target_module_id
        AND (chunk_types IS NULL OR se.chunk_type = ANY(chunk_types))
    ORDER BY se.chunk_type, se.topic_name;
END;
$$;

-- V2 Statistics
CREATE OR REPLACE FUNCTION get_syllabus_stats_v2()
RETURNS TABLE (
    total_chunks BIGINT,
    chunks_by_type JSONB,
    total_subjects BIGINT,
    total_modules BIGINT,
    total_topics BIGINT,
    branches TEXT[],
    semesters INTEGER[],
    regulations TEXT[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH type_counts AS (
        SELECT 
            se.chunk_type,
            COUNT(*) as cnt
        FROM syllabus_embeddings se
        GROUP BY se.chunk_type
    )
    SELECT 
        COUNT(*)::BIGINT as total_chunks,
        (SELECT jsonb_object_agg(tc.chunk_type, tc.cnt) FROM type_counts tc) as chunks_by_type,
        COUNT(DISTINCT se.subject_code)::BIGINT as total_subjects,
        COUNT(DISTINCT se.module_id)::BIGINT as total_modules,
        COUNT(DISTINCT se.topic_id)::BIGINT as total_topics,
        ARRAY_AGG(DISTINCT se.branch) FILTER (WHERE se.branch IS NOT NULL) as branches,
        ARRAY_AGG(DISTINCT se.semester) FILTER (WHERE se.semester IS NOT NULL) as semesters,
        ARRAY_AGG(DISTINCT se.regulation) FILTER (WHERE se.regulation IS NOT NULL) as regulations
    FROM syllabus_embeddings se;
END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Update timestamp trigger
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER syllabus_embeddings_updated_at
    BEFORE UPDATE ON syllabus_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════════
-- Update uploaded_files table to add V2 column
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS chunks_count INTEGER DEFAULT 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- ✅ Migration Complete!
-- 
-- V2 Schema Changes:
-- - Added chunk_id (unique identifier for each chunk)
-- - Added chunk_type (syllabus_content, topic_list, topic_detail, etc.)
-- - Added module_id (canonical ID like "cs201_m1")
-- - Added topic_id (canonical ID like "cs201_m1_arrays")
-- - Changed index from IVFFlat to HNSW (faster)
-- - Added new filtering functions
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT 'Migration V1 → V2 completed successfully!' as status;
