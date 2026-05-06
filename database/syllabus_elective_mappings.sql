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
CREATE INDEX IF NOT EXISTS idx_elective_mappings_branch_regulation ON syllabus_elective_mappings(branch, regulation);

-- Enable Row Level Security
ALTER TABLE syllabus_elective_mappings ENABLE ROW LEVEL SECURITY;

-- Policy: Authenticated users can SELECT (read) all mappings
CREATE POLICY "Allow authenticated users to select mappings"
    ON syllabus_elective_mappings
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy: Admins can INSERT new mappings (create for admin users only)
CREATE POLICY "Allow admins to insert mappings"
    ON syllabus_elective_mappings
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM auth.users
            WHERE auth.uid() = id
            AND raw_user_meta_data->>'role' = 'admin'
        )
    );

-- Policy: Admins can UPDATE mappings
CREATE POLICY "Allow admins to update mappings"
    ON syllabus_elective_mappings
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM auth.users
            WHERE auth.uid() = id
            AND raw_user_meta_data->>'role' = 'admin'
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM auth.users
            WHERE auth.uid() = id
            AND raw_user_meta_data->>'role' = 'admin'
        )
    );

-- Policy: Admins can DELETE mappings
CREATE POLICY "Allow admins to delete mappings"
    ON syllabus_elective_mappings
    FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM auth.users
            WHERE auth.uid() = id
            AND raw_user_meta_data->>'role' = 'admin'
        )
    );

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
