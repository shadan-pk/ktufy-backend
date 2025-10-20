    -- ============================================
    -- KTUfy Backend - Database Schema Setup
    -- Run this SQL in Supabase SQL Editor
    -- ============================================

    -- Enable UUID extension (if not already enabled)
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    -- ============================================
    -- TABLE 1: notes
    -- Stores user-uploaded study materials
    -- ============================================

    CREATE TABLE IF NOT EXISTS notes (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        
        -- File information
        file_path TEXT NOT NULL,
        file_url TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_size INTEGER,
        file_type TEXT,
        
        -- Metadata
        subject TEXT NOT NULL,
        semester INTEGER NOT NULL CHECK (semester >= 1 AND semester <= 8),
        title TEXT NOT NULL,
        description TEXT,
        
        -- Processing status
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
        processing_error TEXT,
        
        -- AI-generated results (JSON)
        ai_results JSONB DEFAULT '{}'::jsonb,
        
        -- Embeddings status
        embeddings_generated BOOLEAN DEFAULT FALSE,
        chunk_count INTEGER DEFAULT 0,
        
        -- Timestamps
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        -- Indexes
        CONSTRAINT notes_user_id_idx CHECK (user_id IS NOT NULL)
    );

    -- Create indexes for notes table
    CREATE INDEX IF NOT EXISTS notes_user_id_idx ON notes(user_id);
    CREATE INDEX IF NOT EXISTS notes_subject_idx ON notes(subject);
    CREATE INDEX IF NOT EXISTS notes_semester_idx ON notes(semester);
    CREATE INDEX IF NOT EXISTS notes_status_idx ON notes(status);
    CREATE INDEX IF NOT EXISTS notes_created_at_idx ON notes(created_at DESC);

    -- Create updated_at trigger for notes
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER update_notes_updated_at
        BEFORE UPDATE ON notes
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();

    -- ============================================
    -- TABLE 2: progress
    -- Tracks syllabus completion progress
    -- ============================================

    CREATE TABLE IF NOT EXISTS progress (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        
        -- Course information
        subject TEXT NOT NULL,
        semester INTEGER NOT NULL CHECK (semester >= 1 AND semester <= 8),
        
        -- Module information
        module_id TEXT NOT NULL,
        module_name TEXT NOT NULL,
        
        -- Progress tracking
        completed BOOLEAN DEFAULT FALSE,
        completion_percentage INTEGER DEFAULT 0 CHECK (completion_percentage >= 0 AND completion_percentage <= 100),
        
        -- Study time
        time_spent_minutes INTEGER DEFAULT 0,
        last_studied TIMESTAMP WITH TIME ZONE,
        
        -- Notes and topics
        topics_completed TEXT[] DEFAULT ARRAY[]::TEXT[],
        notes TEXT,
        
        -- Timestamps
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        -- Unique constraint: one progress entry per user per module
        UNIQUE(user_id, subject, semester, module_id)
    );

    -- Create indexes for progress table
    CREATE INDEX IF NOT EXISTS progress_user_id_idx ON progress(user_id);
    CREATE INDEX IF NOT EXISTS progress_subject_semester_idx ON progress(subject, semester);
    CREATE INDEX IF NOT EXISTS progress_completed_idx ON progress(completed);

    -- Create updated_at trigger for progress
    CREATE TRIGGER update_progress_updated_at
        BEFORE UPDATE ON progress
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();

    -- ============================================
    -- TABLE 3: generated_content
    -- Stores AI-generated study materials
    -- ============================================

    CREATE TABLE IF NOT EXISTS generated_content (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        note_id UUID REFERENCES notes(id) ON DELETE CASCADE,
        
        -- Content type
        content_type TEXT NOT NULL CHECK (content_type IN ('qa', 'flashcard', 'summary', 'quiz', 'mind_map')),
        
        -- Content data (JSON)
        content JSONB NOT NULL,
        
        -- Metadata
        title TEXT,
        difficulty TEXT CHECK (difficulty IN ('easy', 'medium', 'hard')),
        subject TEXT,
        semester INTEGER CHECK (semester >= 1 AND semester <= 8),
        module_id TEXT,
        
        -- Statistics
        view_count INTEGER DEFAULT 0,
        rating DECIMAL(3,2) CHECK (rating >= 0 AND rating <= 5),
        
        -- Timestamps
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Create indexes for generated_content table
    CREATE INDEX IF NOT EXISTS generated_content_user_id_idx ON generated_content(user_id);
    CREATE INDEX IF NOT EXISTS generated_content_note_id_idx ON generated_content(note_id);
    CREATE INDEX IF NOT EXISTS generated_content_type_idx ON generated_content(content_type);
    CREATE INDEX IF NOT EXISTS generated_content_difficulty_idx ON generated_content(difficulty);

    -- Create updated_at trigger for generated_content
    CREATE TRIGGER update_generated_content_updated_at
        BEFORE UPDATE ON generated_content
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();

    -- ============================================
    -- TABLE 4: study_sessions
    -- Tracks user study sessions
    -- ============================================

    CREATE TABLE IF NOT EXISTS study_sessions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        
        -- Session information
        subject TEXT NOT NULL,
        semester INTEGER CHECK (semester >= 1 AND semester <= 8),
        
        -- Time tracking
        duration_minutes INTEGER NOT NULL CHECK (duration_minutes >= 0),
        session_date DATE NOT NULL DEFAULT CURRENT_DATE,
        started_at TIMESTAMP WITH TIME ZONE,
        ended_at TIMESTAMP WITH TIME ZONE,
        
        -- Content covered
        topics_covered TEXT[] DEFAULT ARRAY[]::TEXT[],
        notes_used UUID[] DEFAULT ARRAY[]::UUID[],
        
        -- Performance metrics
        questions_attempted INTEGER DEFAULT 0,
        questions_correct INTEGER DEFAULT 0,
        accuracy_percentage DECIMAL(5,2),
        
        -- Notes
        session_notes TEXT,
        
        -- Timestamps
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Create indexes for study_sessions table
    CREATE INDEX IF NOT EXISTS study_sessions_user_id_idx ON study_sessions(user_id);
    CREATE INDEX IF NOT EXISTS study_sessions_date_idx ON study_sessions(session_date DESC);
    CREATE INDEX IF NOT EXISTS study_sessions_subject_idx ON study_sessions(subject);

    -- ============================================
    -- TABLE 5: chat_history
    -- Stores KG-RAG chatbot conversations
    -- ============================================

    CREATE TABLE IF NOT EXISTS chat_history (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        
        -- Conversation
        query TEXT NOT NULL,
        response TEXT NOT NULL,
        
        -- Context and sources
        sources JSONB DEFAULT '[]'::jsonb,
        context_used TEXT[] DEFAULT ARRAY[]::TEXT[],
        
        -- AI metadata
        confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
        model_used TEXT,
        tokens_used INTEGER,
        
        -- Filtering
        subject TEXT,
        semester INTEGER CHECK (semester >= 1 AND semester <= 8),
        
        -- User feedback
        helpful BOOLEAN,
        feedback TEXT,
        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
        
        -- Timestamps
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Create indexes for chat_history table
    CREATE INDEX IF NOT EXISTS chat_history_user_id_idx ON chat_history(user_id);
    CREATE INDEX IF NOT EXISTS chat_history_created_at_idx ON chat_history(created_at DESC);
    CREATE INDEX IF NOT EXISTS chat_history_subject_idx ON chat_history(subject);

    -- ============================================
    -- ROW LEVEL SECURITY (RLS) POLICIES
    -- Ensure users can only access their own data
    -- ============================================

    -- Enable RLS on all tables
    ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
    ALTER TABLE progress ENABLE ROW LEVEL SECURITY;
    ALTER TABLE generated_content ENABLE ROW LEVEL SECURITY;
    ALTER TABLE study_sessions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;

    -- ============================================
    -- RLS POLICIES: notes table
    -- ============================================

    -- Users can view their own notes
    CREATE POLICY "Users can view their own notes"
        ON notes FOR SELECT
        USING (auth.uid() = user_id);

    -- Users can insert their own notes
    CREATE POLICY "Users can insert their own notes"
        ON notes FOR INSERT
        WITH CHECK (auth.uid() = user_id);

    -- Users can update their own notes
    CREATE POLICY "Users can update their own notes"
        ON notes FOR UPDATE
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id);

    -- Users can delete their own notes
    CREATE POLICY "Users can delete their own notes"
        ON notes FOR DELETE
        USING (auth.uid() = user_id);

    -- ============================================
    -- RLS POLICIES: progress table
    -- ============================================

    CREATE POLICY "Users can view their own progress"
        ON progress FOR SELECT
        USING (auth.uid() = user_id);

    CREATE POLICY "Users can insert their own progress"
        ON progress FOR INSERT
        WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can update their own progress"
        ON progress FOR UPDATE
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can delete their own progress"
        ON progress FOR DELETE
        USING (auth.uid() = user_id);

    -- ============================================
    -- RLS POLICIES: generated_content table
    -- ============================================

    CREATE POLICY "Users can view their own generated content"
        ON generated_content FOR SELECT
        USING (auth.uid() = user_id);

    CREATE POLICY "Users can insert their own generated content"
        ON generated_content FOR INSERT
        WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can update their own generated content"
        ON generated_content FOR UPDATE
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can delete their own generated content"
        ON generated_content FOR DELETE
        USING (auth.uid() = user_id);

    -- ============================================
    -- RLS POLICIES: study_sessions table
    -- ============================================

    CREATE POLICY "Users can view their own study sessions"
        ON study_sessions FOR SELECT
        USING (auth.uid() = user_id);

    CREATE POLICY "Users can insert their own study sessions"
        ON study_sessions FOR INSERT
        WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can update their own study sessions"
        ON study_sessions FOR UPDATE
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can delete their own study sessions"
        ON study_sessions FOR DELETE
        USING (auth.uid() = user_id);

    -- ============================================
    -- RLS POLICIES: chat_history table
    -- ============================================

    CREATE POLICY "Users can view their own chat history"
        ON chat_history FOR SELECT
        USING (auth.uid() = user_id);

    CREATE POLICY "Users can insert their own chat history"
        ON chat_history FOR INSERT
        WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can update their own chat history"
        ON chat_history FOR UPDATE
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can delete their own chat history"
        ON chat_history FOR DELETE
        USING (auth.uid() = user_id);

    -- ============================================
    -- HELPER FUNCTIONS
    -- ============================================

    -- Function to get user's total study time
    CREATE OR REPLACE FUNCTION get_user_total_study_time(p_user_id UUID)
    RETURNS INTEGER AS $$
    DECLARE
        total_minutes INTEGER;
    BEGIN
        SELECT COALESCE(SUM(duration_minutes), 0)
        INTO total_minutes
        FROM study_sessions
        WHERE user_id = p_user_id;
        
        RETURN total_minutes;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;

    -- Function to get user's subject progress
    CREATE OR REPLACE FUNCTION get_user_subject_progress(p_user_id UUID, p_subject TEXT, p_semester INTEGER)
    RETURNS TABLE (
        total_modules INTEGER,
        completed_modules INTEGER,
        overall_percentage DECIMAL
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            COUNT(*)::INTEGER as total_modules,
            COUNT(*) FILTER (WHERE completed = TRUE)::INTEGER as completed_modules,
            ROUND(AVG(completion_percentage), 2) as overall_percentage
        FROM progress
        WHERE user_id = p_user_id 
            AND subject = p_subject 
            AND semester = p_semester;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;

    -- ============================================
    -- VIEWS (for analytics)
    -- ============================================

    -- View: User study statistics
    CREATE OR REPLACE VIEW user_study_stats AS
    SELECT 
        user_id,
        COUNT(DISTINCT session_date) as total_study_days,
        SUM(duration_minutes) as total_minutes,
        AVG(duration_minutes) as avg_session_minutes,
        COUNT(*) as total_sessions,
        MAX(session_date) as last_study_date
    FROM study_sessions
    GROUP BY user_id;

    -- View: Note processing status
    CREATE OR REPLACE VIEW note_processing_stats AS
    SELECT 
        user_id,
        COUNT(*) as total_notes,
        COUNT(*) FILTER (WHERE status = 'completed') as completed_notes,
        COUNT(*) FILTER (WHERE status = 'processing') as processing_notes,
        COUNT(*) FILTER (WHERE status = 'failed') as failed_notes,
        COUNT(*) FILTER (WHERE status = 'pending') as pending_notes,
        COUNT(*) FILTER (WHERE embeddings_generated = TRUE) as notes_with_embeddings
    FROM notes
    GROUP BY user_id;

    -- ============================================
    -- COMMENTS (for documentation)
    -- ============================================

    COMMENT ON TABLE notes IS 'Stores user-uploaded study materials with AI processing status';
    COMMENT ON TABLE progress IS 'Tracks user progress through syllabus modules';
    COMMENT ON TABLE generated_content IS 'Stores AI-generated study materials (Q&A, flashcards, etc.)';
    COMMENT ON TABLE study_sessions IS 'Records individual study sessions with time and performance metrics';
    COMMENT ON TABLE chat_history IS 'Logs KG-RAG chatbot conversations for context and analytics';

    -- ============================================
    -- SUCCESS MESSAGE
    -- ============================================

    DO $$ 
    BEGIN 
        RAISE NOTICE '✅ Database schema created successfully!';
        RAISE NOTICE 'Tables created: notes, progress, generated_content, study_sessions, chat_history';
        RAISE NOTICE 'RLS policies: Enabled and configured';
        RAISE NOTICE 'Next step: Create storage buckets in Supabase Dashboard';
    END $$;
