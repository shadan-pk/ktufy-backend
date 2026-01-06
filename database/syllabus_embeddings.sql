-- ═══════════════════════════════════════════════════════════════════════════════
-- KTUfy Syllabus Embeddings V2 - Corrected Schema
-- Run this in Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- ═══════════════════════════════════════════════════════════════════════════════
-- DROP old table if migrating (UNCOMMENT IF NEEDED)
-- ═══════════════════════════════════════════════════════════════════════════════
-- DROP TABLE IF EXISTS syllabus_embeddings CASCADE;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Syllabus Embeddings Table V2
-- Stores proper content chunks with rich metadata
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS syllabus_embeddings (
    id BIGSERIAL PRIMARY KEY,
    
    -- Chunk identification
    chunk_id TEXT UNIQUE,                    -- e.g., "cs201_m1_overview"
    chunk_type TEXT NOT NULL DEFAULT 'unknown', -- syllabus_content, topic_list, topic_detail, course_outcomes, references
    
    -- Content (what we embed and retrieve)
    content TEXT NOT NULL,
    
    -- Vector embedding (768 dimensions for BAAI/bge-base-en-v1.5)
    embedding vector(768),
    
    -- Subject metadata
    subject_code TEXT,
    subject_name TEXT,
    
    -- Module metadata
    module_id TEXT,                          -- Canonical ID: "cs201_m1"
    module_number INTEGER,
    module_name TEXT,
    
    -- Topic/Concept metadata (for topic_detail chunks)
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
-- Indexes
-- ═══════════════════════════════════════════════════════════════════════════════

-- Vector similarity search (HNSW is faster than IVFFlat for this size)
CREATE INDEX IF NOT EXISTS syllabus_embeddings_embedding_hnsw_idx 
ON syllabus_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Chunk type for filtering by content type
CREATE INDEX IF NOT EXISTS idx_chunk_type ON syllabus_embeddings(chunk_type);

-- Filtering indexes
CREATE INDEX IF NOT EXISTS idx_semester ON syllabus_embeddings(semester);
CREATE INDEX IF NOT EXISTS idx_branch ON syllabus_embeddings(branch);
CREATE INDEX IF NOT EXISTS idx_subject ON syllabus_embeddings(subject_code);
CREATE INDEX IF NOT EXISTS idx_regulation ON syllabus_embeddings(regulation);
CREATE INDEX IF NOT EXISTS idx_module ON syllabus_embeddings(module_id);
CREATE INDEX IF NOT EXISTS idx_topic ON syllabus_embeddings(topic_id);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_subject_module ON syllabus_embeddings(subject_code, module_number);
CREATE INDEX IF NOT EXISTS idx_sem_branch_reg ON syllabus_embeddings(semester, branch, regulation);

-- Full text search
CREATE INDEX IF NOT EXISTS idx_content_fts 
ON syllabus_embeddings 
USING GIN (to_tsvector('english', content));

-- ═══════════════════════════════════════════════════════════════════════════════
-- V2 Similarity Search Function
-- Supports chunk_type filtering
-- ═══════════════════════════════════════════════════════════════════════════════

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

-- ═══════════════════════════════════════════════════════════════════════════════
-- Get chunks by concept ID
-- ═══════════════════════════════════════════════════════════════════════════════

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

-- ═══════════════════════════════════════════════════════════════════════════════
-- Get chunks by module ID
-- ═══════════════════════════════════════════════════════════════════════════════

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

-- ═══════════════════════════════════════════════════════════════════════════════
-- Statistics Function V2
-- ═══════════════════════════════════════════════════════════════════════════════

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
            chunk_type,
            COUNT(*) as cnt
        FROM syllabus_embeddings
        GROUP BY chunk_type
    )
    SELECT 
        COUNT(*)::BIGINT as total_chunks,
        (SELECT jsonb_object_agg(chunk_type, cnt) FROM type_counts) as chunks_by_type,
        COUNT(DISTINCT subject_code)::BIGINT as total_subjects,
        COUNT(DISTINCT module_id)::BIGINT as total_modules,
        COUNT(DISTINCT topic_id)::BIGINT as total_topics,
        ARRAY_AGG(DISTINCT branch) FILTER (WHERE branch IS NOT NULL) as branches,
        ARRAY_AGG(DISTINCT semester) FILTER (WHERE semester IS NOT NULL) as semesters,
        ARRAY_AGG(DISTINCT regulation) FILTER (WHERE regulation IS NOT NULL) as regulations
    FROM syllabus_embeddings;
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

DROP TRIGGER IF EXISTS syllabus_embeddings_updated_at ON syllabus_embeddings;
CREATE TRIGGER syllabus_embeddings_updated_at
    BEFORE UPDATE ON syllabus_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════════
-- Uploaded Files Table (unchanged)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    original_filename TEXT,
    file_type TEXT DEFAULT 'pdf',
    file_size BIGINT,
    semester INTEGER,
    branch TEXT,
    regulation TEXT DEFAULT '2019',
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    subjects_count INTEGER DEFAULT 0,
    modules_count INTEGER DEFAULT 0,
    topics_count INTEGER DEFAULT 0,
    chunks_count INTEGER DEFAULT 0,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    uploaded_by UUID REFERENCES auth.users(id)
);

CREATE INDEX IF NOT EXISTS uploaded_files_status_idx ON uploaded_files(status);
CREATE INDEX IF NOT EXISTS uploaded_files_sem_branch_idx ON uploaded_files(semester, branch, regulation);

-- ═══════════════════════════════════════════════════════════════════════════════
-- IMPORTANT: After running this, update your embedding model to 768 dimensions
-- The default model should be: BAAI/bge-base-en-v1.5
-- ═══════════════════════════════════════════════════════════════════════════════
