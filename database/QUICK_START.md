# 🎯 Phase 3: Database Setup - Quick Start Guide

## What You Need to Do Now

Phase 3 requires you to set up the database in **Supabase Dashboard**. I've created all the SQL scripts and documentation you need!

---

## 📝 Step-by-Step (Simple Version)

### Step 1: Run SQL Script (5 minutes)

1. **Go to Supabase**:
   - Visit: https://supabase.com/dashboard
   - Select your KTUfy project

2. **Open SQL Editor**:
   - Click "SQL Editor" in left sidebar
   - Click "New query"

3. **Copy & Run**:
   - Open file: `database/schema.sql`
   - Copy ALL the SQL (Ctrl+A, Ctrl+C)
   - Paste into Supabase SQL Editor
   - Click **"Run"** button

4. **Verify Success**:
   - Look for green ✅ success message
   - Should say "Database schema created successfully!"

### Step 2: Create Storage Buckets (5 minutes)

1. **Go to Storage**:
   - Click "Storage" in Supabase sidebar
   - Click "New bucket"

2. **Create 3 Buckets**:

   **Bucket 1:**
   - Name: `notes`
   - Public: NO (keep private)
   - Click "Create bucket"

   **Bucket 2:**
   - Name: `study-packs`
   - Public: YES
   - Click "Create bucket"

   **Bucket 3:**
   - Name: `generated-content`
   - Public: NO (keep private)
   - Click "Create bucket"

3. **Add Storage Policies**:
   - For each bucket, follow instructions in `database/STORAGE_SETUP.md`
   - Or I'll help you create these in the next step

### Step 3: Get Database URL (1 minute)

1. **In Supabase Dashboard**:
   - Go to Settings → Database
   - Find "Connection string"
   - Copy the "URI" format

2. **Add to `.env` file**:
   ```
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@[YOUR-PROJECT-REF].supabase.co:5432/postgres
   ```

---

## ✅ Verification

After setup, verify in Supabase:

### Check Tables Exist:
1. Go to "Table Editor"
2. Should see 5 tables:
   - notes
   - progress
   - generated_content
   - study_sessions
   - chat_history

### Check Storage Buckets:
1. Go to "Storage"
2. Should see 3 buckets:
   - notes
   - study-packs
   - generated-content

---

## 📚 Detailed Documentation

I've created complete documentation for you:

### 1. `database/schema.sql`
- Complete SQL script
- Creates all 5 tables
- Sets up Row Level Security
- Adds indexes and triggers
- **Just run this file!**

### 2. `database/SETUP_INSTRUCTIONS.md`
- Detailed step-by-step guide
- Troubleshooting tips
- Test queries
- Verification steps

### 3. `database/STORAGE_SETUP.md`
- Storage bucket configuration
- RLS policies for storage
- Usage examples
- Security best practices

---

## 🎯 What Gets Created

### **5 Database Tables:**

1. **notes** 📄
   - Stores uploaded PDFs/images
   - Tracks processing status
   - Links to AI results

2. **progress** 📊
   - Syllabus completion tracking
   - Per-user, per-subject, per-module
   - Time spent tracking

3. **generated_content** 🤖
   - AI-generated Q&A
   - Flashcards
   - Summaries

4. **study_sessions** ⏱️
   - Study time logging
   - Performance metrics
   - Topics covered

5. **chat_history** 💬
   - KG-RAG conversations
   - Sources and confidence
   - User feedback

### **3 Storage Buckets:**

1. **notes** 📁
   - User-uploaded files
   - Private access only

2. **study-packs** 📦
   - Downloadable ZIP files
   - Public access

3. **generated-content** 📝
   - AI-generated PDFs
   - Private access only

### **Security Features:**

- ✅ Row Level Security on all tables
- ✅ Users can only see their own data
- ✅ Automatic cascade deletion
- ✅ Data validation constraints
- ✅ Storage access policies

---

## 🚨 Important Notes

### **Before Running SQL:**
- ✅ Make sure you're in the correct Supabase project
- ✅ Backup if you have existing data
- ✅ Run in Supabase SQL Editor (not locally)

### **After Running SQL:**
- ✅ Verify all 5 tables created
- ✅ Check RLS is enabled
- ✅ Create storage buckets
- ✅ Add DATABASE_URL to .env

---

## 🤔 What If Something Goes Wrong?

### SQL Errors:
- **Check the error message** in Supabase
- **Read `database/SETUP_INSTRUCTIONS.md`** for troubleshooting
- **Try running in sections** if full script fails

### Storage Issues:
- **Follow `database/STORAGE_SETUP.md`** exactly
- **Check bucket names** are exactly: `notes`, `study-packs`, `generated-content`
- **Verify RLS policies** are added

### Need Help:
- Check Supabase Logs: Dashboard → Logs
- Review documentation files in `database/`
- Run verification queries from SETUP_INSTRUCTIONS.md

---

## ⏭️ After Database Setup

Once database is set up, we'll continue Phase 3 with:

1. **Create database models** (SQLAlchemy)
2. **Build database utilities** (connection, sessions)
3. **Create CRUD operations** (Create, Read, Update, Delete)
4. **Test everything** works

I'll help you with all of this once the Supabase setup is complete!

---

## 📊 Your Progress

```
Phase 1: Environment Setup              ✅ COMPLETE
Phase 2: Authentication Integration      ✅ COMPLETE
Phase 3: Database Schema Design          🔄 IN PROGRESS
  ├─ SQL Schema                          ✅ Created
  ├─ Storage Documentation               ✅ Created
  ├─ Setup Instructions                  ✅ Created
  ├─ Run SQL in Supabase                 ⏳ YOUR TURN
  ├─ Create Storage Buckets              ⏳ YOUR TURN
  ├─ Database Models                     ⏳ Next
  └─ CRUD Operations                     ⏳ Next
```

---

## 🎯 Action Items for You

1. [ ] Open Supabase Dashboard
2. [ ] Run `database/schema.sql` in SQL Editor
3. [ ] Create 3 storage buckets
4. [ ] Add DATABASE_URL to `.env`
5. [ ] Verify tables and buckets exist
6. [ ] Come back here when done!

---

## 📞 Ready for Next Step?

Once you've completed the Supabase setup:
1. ✅ Verify 5 tables exist in Table Editor
2. ✅ Verify 3 buckets exist in Storage
3. ✅ DATABASE_URL added to .env

Then tell me: **"Database setup complete"** and I'll help you build the database models and CRUD operations!

---

**Files to Use:**
- `database/schema.sql` → Copy & paste into Supabase SQL Editor
- `database/SETUP_INSTRUCTIONS.md` → Detailed guide
- `database/STORAGE_SETUP.md` → Storage bucket guide

**Time Required:** ~10-15 minutes

**Let me know when you're ready or if you need help!** 🚀
