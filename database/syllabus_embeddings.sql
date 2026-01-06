-- ═══════════════════════════════════════════════════════════════════════════════
-- KTUfy Syllabus Embeddings Table Setup
-- Run this in Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable the pgvector extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Syllabus Embeddings Table
-- Stores vector embeddings for RAG search
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS syllabus_embeddings (
    id BIGSERIAL PRIMARY KEY,
    
    -- Content
    content TEXT NOT NULL,
    
    -- Vector embedding (384 dimensions for all-MiniLM-L6-v2)
    embedding vector(384),
    
    -- Metadata for filtering
    subject_code TEXT,
    subject_name TEXT,
    module_number INTEGER,
    module_name TEXT,
    topic_name TEXT,
    keywords TEXT[],
    semester INTEGER,
    branch TEXT,
    regulation TEXT DEFAULT '2019',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Indexes for fast queries
-- ═══════════════════════════════════════════════════════════════════════════════

-- Vector similarity search index (IVFFlat for approximate nearest neighbor)
CREATE INDEX IF NOT EXISTS syllabus_embeddings_embedding_idx 
ON syllabus_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Filtering indexes
CREATE INDEX IF NOT EXISTS syllabus_embeddings_semester_idx ON syllabus_embeddings(semester);
CREATE INDEX IF NOT EXISTS syllabus_embeddings_branch_idx ON syllabus_embeddings(branch);
CREATE INDEX IF NOT EXISTS syllabus_embeddings_subject_idx ON syllabus_embeddings(subject_code);
CREATE INDEX IF NOT EXISTS syllabus_embeddings_topic_idx ON syllabus_embeddings(topic_name);

-- Full text search index
CREATE INDEX IF NOT EXISTS syllabus_embeddings_content_idx 
ON syllabus_embeddings 
USING GIN (to_tsvector('english', content));

-- ═══════════════════════════════════════════════════════════════════════════════
-- Similarity Search Function
-- Use this function to search for similar content
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION search_syllabus(
    query_embedding vector(384),
    match_count INT DEFAULT 5,
    filter_semester INT DEFAULT NULL,
    filter_branch TEXT DEFAULT NULL,
    filter_subject TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    subject_code TEXT,
    subject_name TEXT,
    module_number INTEGER,
    module_name TEXT,
    topic_name TEXT,
    semester INTEGER,
    branch TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        se.id,
        se.content,
        se.subject_code,
        se.subject_name,
        se.module_number,
        se.module_name,
        se.topic_name,
        se.semester,
        se.branch,
        1 - (se.embedding <=> query_embedding) AS similarity
    FROM syllabus_embeddings se
    WHERE 
        (filter_semester IS NULL OR se.semester = filter_semester)
        AND (filter_branch IS NULL OR se.branch = filter_branch)
        AND (filter_subject IS NULL OR se.subject_code = filter_subject)
    ORDER BY se.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Uploaded Files Tracking Table
-- Tracks uploaded syllabus PDFs and their processing status
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
    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    error_message TEXT,
    subjects_count INTEGER DEFAULT 0,
    modules_count INTEGER DEFAULT 0,
    topics_count INTEGER DEFAULT 0,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    uploaded_by UUID REFERENCES auth.users(id)
);

-- Index for file queries
CREATE INDEX IF NOT EXISTS uploaded_files_status_idx ON uploaded_files(status);
CREATE INDEX IF NOT EXISTS uploaded_files_semester_branch_idx ON uploaded_files(semester, branch);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Processing Jobs Table
-- Tracks background processing jobs
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID REFERENCES uploaded_files(id),
    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0,
    message TEXT,
    subjects_processed INTEGER DEFAULT 0,
    total_subjects INTEGER DEFAULT 0,
    result JSONB,
    error TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Row Level Security (RLS) Policies
-- Uncomment these if you want to restrict access
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable RLS
-- ALTER TABLE syllabus_embeddings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE uploaded_files ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read all embeddings
-- CREATE POLICY "Allow authenticated read" ON syllabus_embeddings
--     FOR SELECT TO authenticated USING (true);

-- Allow service role to manage all data
-- CREATE POLICY "Allow service role all" ON syllabus_embeddings
--     FOR ALL TO service_role USING (true);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Helper Functions
-- ═══════════════════════════════════════════════════════════════════════════════

-- Function to get statistics
CREATE OR REPLACE FUNCTION get_syllabus_stats()
RETURNS TABLE (
    total_embeddings BIGINT,
    total_subjects BIGINT,
    total_topics BIGINT,
    branches TEXT[],
    semesters INTEGER[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_embeddings,
        COUNT(DISTINCT subject_code)::BIGINT as total_subjects,
        COUNT(DISTINCT topic_name)::BIGINT as total_topics,
        ARRAY_AGG(DISTINCT branch) FILTER (WHERE branch IS NOT NULL) as branches,
        ARRAY_AGG(DISTINCT semester) FILTER (WHERE semester IS NOT NULL) as semesters
    FROM syllabus_embeddings;
END;
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Update Trigger
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
