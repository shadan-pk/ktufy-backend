# 🗄️ Database Setup Instructions

## Overview

This guide will walk you through setting up the complete database schema for KTUfy Backend in Supabase.

---

## 📋 Prerequisites

- ✅ Supabase account created
- ✅ KTUfy project created in Supabase
- ✅ Supabase credentials in `.env` file

---

## 🚀 Step-by-Step Setup

### Step 1: Access Supabase SQL Editor

1. Go to https://supabase.com/dashboard
2. Select your **KTUfy project**
3. Click on **SQL Editor** in the left sidebar
4. Click **"New query"**

### Step 2: Run Database Schema

1. **Open the schema file**:
   - Open `database/schema.sql` in VS Code
   - Select all content (Ctrl+A)
   - Copy (Ctrl+C)

2. **Paste into SQL Editor**:
   - Paste in Supabase SQL Editor
   - Click **"Run"** button (or F5)

3. **Verify Success**:
   - Should see green success message
   - Check for "✅ Database schema created successfully!"
   - No red errors

### Step 3: Verify Tables Created

Run this query to verify all tables exist:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('notes', 'progress', 'generated_content', 'study_sessions', 'chat_history')
ORDER BY table_name;
```

**Expected result**: 5 rows

### Step 4: Verify RLS Policies

Run this query to check RLS is enabled:

```sql
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('notes', 'progress', 'generated_content', 'study_sessions', 'chat_history');
```

**Expected**: All tables should have `rowsecurity = true`

### Step 5: Set Up Storage Buckets

Follow the instructions in `database/STORAGE_SETUP.md` to:
1. Create 3 storage buckets
2. Configure RLS policies for storage

---

## 📊 Database Schema Overview

### Tables Created:

1. **notes** - User uploaded study materials
   - Stores file paths, URLs, metadata
   - Tracks AI processing status
   - Links to embeddings

2. **progress** - Syllabus completion tracking
   - Per-user, per-subject, per-module progress
   - Completion percentages
   - Study time tracking

3. **generated_content** - AI-generated materials
   - Q&A pairs
   - Flashcards
   - Summaries
   - Quiz questions

4. **study_sessions** - Study time tracking
   - Session duration
   - Topics covered
   - Performance metrics

5. **chat_history** - KG-RAG conversations
   - User queries
   - AI responses
   - Sources and confidence scores

### Security Features:

- ✅ **Row Level Security (RLS)** enabled on all tables
- ✅ Users can only access their own data
- ✅ Foreign key constraints to auth.users
- ✅ CASCADE deletion (delete user → delete all their data)
- ✅ CHECK constraints for data validation

### Performance Features:

- ✅ Indexes on frequently queried columns
- ✅ Automatic `updated_at` triggers
- ✅ Optimized for user_id lookups
- ✅ Date-based indexes for time-series queries

---

## 🧪 Testing the Database

### Test 1: Insert a Test Note

```sql
-- Insert test note (replace YOUR_USER_ID with actual UUID from auth.users)
INSERT INTO notes (
    user_id, 
    file_path, 
    file_url, 
    file_name,
    subject, 
    semester, 
    title
) VALUES (
    'YOUR_USER_ID'::uuid,
    'test/path/file.pdf',
    'https://example.com/file.pdf',
    'test_file.pdf',
    'Computer Science',
    4,
    'Test Note'
);

-- Verify it was created
SELECT id, title, status, created_at 
FROM notes 
WHERE user_id = 'YOUR_USER_ID'::uuid;
```

### Test 2: Insert Progress Entry

```sql
INSERT INTO progress (
    user_id,
    subject,
    semester,
    module_id,
    module_name,
    completion_percentage
) VALUES (
    'YOUR_USER_ID'::uuid,
    'Computer Science',
    4,
    'M1',
    'Introduction to Programming',
    75
);

-- Verify
SELECT * FROM progress WHERE user_id = 'YOUR_USER_ID'::uuid;
```

### Test 3: Test RLS Policy

```sql
-- This should work (selecting your own data)
SELECT * FROM notes WHERE user_id = auth.uid();

-- This will return empty (cannot see other users' data)
SELECT * FROM notes WHERE user_id != auth.uid();
```

---

## 🔍 Useful Queries

### Check Table Row Counts:

```sql
SELECT 
    'notes' as table_name, COUNT(*) as row_count FROM notes
UNION ALL
SELECT 'progress', COUNT(*) FROM progress
UNION ALL
SELECT 'generated_content', COUNT(*) FROM generated_content
UNION ALL
SELECT 'study_sessions', COUNT(*) FROM study_sessions
UNION ALL
SELECT 'chat_history', COUNT(*) FROM chat_history;
```

### View User Statistics:

```sql
-- Get study stats for a user
SELECT * FROM user_study_stats 
WHERE user_id = 'YOUR_USER_ID'::uuid;

-- Get note processing stats
SELECT * FROM note_processing_stats 
WHERE user_id = 'YOUR_USER_ID'::uuid;
```

### Check Indexes:

```sql
SELECT 
    tablename, 
    indexname, 
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('notes', 'progress', 'generated_content', 'study_sessions', 'chat_history')
ORDER BY tablename, indexname;
```

---

## 🐛 Troubleshooting

### Error: "relation already exists"

**Cause**: Tables already created

**Solution**: Either:
1. Drop existing tables:
   ```sql
   DROP TABLE IF EXISTS chat_history CASCADE;
   DROP TABLE IF EXISTS study_sessions CASCADE;
   DROP TABLE IF EXISTS generated_content CASCADE;
   DROP TABLE IF EXISTS progress CASCADE;
   DROP TABLE IF EXISTS notes CASCADE;
   ```
2. Or skip and continue with storage setup

### Error: "permission denied for schema public"

**Cause**: Missing permissions

**Solution**: Run as superuser or check project permissions in Supabase

### Error: "could not create unique index"

**Cause**: Duplicate data violates unique constraint

**Solution**: 
```sql
-- Find duplicates in progress table
SELECT user_id, subject, semester, module_id, COUNT(*)
FROM progress
GROUP BY user_id, subject, semester, module_id
HAVING COUNT(*) > 1;

-- Delete duplicates, keep the most recent
DELETE FROM progress p1
USING progress p2
WHERE p1.id < p2.id
AND p1.user_id = p2.user_id
AND p1.subject = p2.subject
AND p1.semester = p2.semester
AND p1.module_id = p2.module_id;
```

---

## 📝 Schema Modifications

### Adding a Column:

```sql
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS new_column TEXT;
```

### Adding an Index:

```sql
CREATE INDEX IF NOT EXISTS idx_name 
ON table_name(column_name);
```

### Modifying RLS Policy:

```sql
DROP POLICY IF EXISTS "policy_name" ON table_name;

CREATE POLICY "new_policy_name"
ON table_name FOR SELECT
USING (auth.uid() = user_id);
```

---

## ✅ Setup Checklist

### Database Tables:
- [ ] `notes` table created
- [ ] `progress` table created
- [ ] `generated_content` table created
- [ ] `study_sessions` table created
- [ ] `chat_history` table created

### Security:
- [ ] RLS enabled on all tables
- [ ] SELECT policies created
- [ ] INSERT policies created
- [ ] UPDATE policies created
- [ ] DELETE policies created

### Performance:
- [ ] Indexes created
- [ ] Triggers created (updated_at)
- [ ] Helper functions created

### Storage:
- [ ] `notes` bucket created
- [ ] `study-packs` bucket created
- [ ] `generated-content` bucket created
- [ ] Storage RLS policies configured

### Testing:
- [ ] Test insert queries work
- [ ] Test RLS prevents unauthorized access
- [ ] Verify row counts
- [ ] Check user statistics views

---

## 📚 Next Steps

After completing database setup:

1. **Update `.env` file**:
   - Add `DATABASE_URL` (from Supabase Settings → Database)

2. **Create database models** (Phase 3 continuation):
   - SQLAlchemy models
   - Pydantic schemas
   - CRUD utilities

3. **Test with backend**:
   - Connect from FastAPI
   - Test CRUD operations
   - Verify RLS works

---

## 🔗 Resources

- **Supabase Documentation**: https://supabase.com/docs
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **RLS Guide**: https://supabase.com/docs/guides/auth/row-level-security

---

**Questions?** Check the Supabase logs in Dashboard → Logs → Postgres Logs
