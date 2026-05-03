-- ============================================================================
-- Syllabus Tables - Store structured syllabus data for fast display
-- Neo4j is used for KG-RAG only; these tables serve the browse/display API
-- ============================================================================

-- Subjects table
CREATE TABLE IF NOT EXISTS syllabus_subjects (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    branch TEXT NOT NULL,
    semester INTEGER NOT NULL,
    regulation TEXT NOT NULL DEFAULT '2019',
    credits INTEGER,
    category TEXT,
    hours_per_week INTEGER,
    course_outcomes TEXT[] DEFAULT '{}',
    textbooks TEXT[] DEFAULT '{}',
    "references" TEXT[] DEFAULT '{}',
    objectives TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(code, regulation)
);

-- Modules table
CREATE TABLE IF NOT EXISTS syllabus_modules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    subject_code TEXT NOT NULL,
    regulation TEXT NOT NULL DEFAULT '2019',
    module_number INTEGER NOT NULL,
    name TEXT NOT NULL,
    hours INTEGER,
    syllabus_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(subject_code, regulation, module_number),
    FOREIGN KEY (subject_code, regulation) REFERENCES syllabus_subjects(code, regulation) ON DELETE CASCADE
);

-- Topics within modules
CREATE TABLE IF NOT EXISTS syllabus_topics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    module_id UUID NOT NULL REFERENCES syllabus_modules(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_subjects_branch ON syllabus_subjects(branch);
CREATE INDEX IF NOT EXISTS idx_subjects_semester ON syllabus_subjects(semester);
CREATE INDEX IF NOT EXISTS idx_subjects_regulation ON syllabus_subjects(regulation);
CREATE INDEX IF NOT EXISTS idx_subjects_code_reg ON syllabus_subjects(code, regulation);
CREATE INDEX IF NOT EXISTS idx_modules_subject ON syllabus_modules(subject_code, regulation);
CREATE INDEX IF NOT EXISTS idx_topics_module ON syllabus_topics(module_id);

-- Disable RLS for these tables (public syllabus data, not user-specific)
ALTER TABLE syllabus_subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE syllabus_modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE syllabus_topics ENABLE ROW LEVEL SECURITY;

-- Allow all authenticated users to read syllabus data
CREATE POLICY "Authenticated users can read subjects"
    ON syllabus_subjects FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can read modules"
    ON syllabus_modules FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can read topics"
    ON syllabus_topics FOR SELECT
    TO authenticated
    USING (true);

-- Service role can manage syllabus data (insert/update/delete)
CREATE POLICY "Service role can manage subjects"
    ON syllabus_subjects FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role can manage modules"
    ON syllabus_modules FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role can manage topics"
    ON syllabus_topics FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_syllabus_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_syllabus_subjects_updated_at
    BEFORE UPDATE ON syllabus_subjects
    FOR EACH ROW EXECUTE FUNCTION update_syllabus_updated_at();

CREATE TRIGGER update_syllabus_modules_updated_at
    BEFORE UPDATE ON syllabus_modules
    FOR EACH ROW EXECUTE FUNCTION update_syllabus_updated_at();
