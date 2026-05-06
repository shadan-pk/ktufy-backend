-- Elective mappings: map subject codes to program elective groups (PEC1, PEC2, PEC3, OEC, etc.)
CREATE TABLE IF NOT EXISTS syllabus_elective_mappings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    subject_code TEXT NOT NULL,
    program_elective TEXT NOT NULL,
    branch TEXT,
    regulation TEXT NOT NULL DEFAULT '2019',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(subject_code, regulation)
);

CREATE INDEX IF NOT EXISTS idx_elective_mappings_subject ON syllabus_elective_mappings(subject_code, regulation);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_elective_mappings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_elective_mappings_updated_at
    BEFORE UPDATE ON syllabus_elective_mappings
    FOR EACH ROW EXECUTE FUNCTION update_elective_mappings_updated_at();
