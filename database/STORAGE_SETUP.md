# Supabase Storage Buckets Setup Guide

## 📦 Storage Buckets to Create

You need to create 3 storage buckets in your Supabase project for file management.

---

## 🚀 How to Create Buckets

### Step 1: Access Supabase Dashboard
1. Go to https://supabase.com/dashboard
2. Select your KTUfy project
3. Click on **Storage** in the left sidebar

### Step 2: Create Buckets

Click **"New bucket"** for each of the following:

---

## 📁 Bucket 1: notes

**Purpose**: Store user-uploaded PDF/image files

**Settings**:
- **Name**: `notes`
- **Public**: ❌ No (Private)
- **File size limit**: 10 MB
- **Allowed MIME types**: 
  - `application/pdf`
  - `image/jpeg`
  - `image/jpg`
  - `image/png`

**Folder Structure**:
```
notes/
├── {user_id}/
│   ├── {note_id}_original.pdf
│   ├── {note_id}_thumbnail.jpg
│   └── ...
```

**RLS Policies**:

```sql
-- Allow users to upload to their own folder
CREATE POLICY "Users can upload to their folder"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'notes' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow users to read their own files
CREATE POLICY "Users can read their own files"
ON storage.objects FOR SELECT
USING (
    bucket_id = 'notes' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow users to update their own files
CREATE POLICY "Users can update their own files"
ON storage.objects FOR UPDATE
USING (
    bucket_id = 'notes' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow users to delete their own files
CREATE POLICY "Users can delete their own files"
ON storage.objects FOR DELETE
USING (
    bucket_id = 'notes' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);
```

---

## 📚 Bucket 2: study-packs

**Purpose**: Store downloadable study pack ZIP files

**Settings**:
- **Name**: `study-packs`
- **Public**: ✅ Yes (or use signed URLs)
- **File size limit**: 50 MB
- **Allowed MIME types**: 
  - `application/zip`
  - `application/pdf`

**Folder Structure**:
```
study-packs/
├── {user_id}/
│   ├── S4_OOP_StudyPack.zip
│   ├── S5_Web_Development_Pack.zip
│   └── ...
├── public/  (optional - for shared packs)
│   └── Sample_Pack.zip
```

**RLS Policies**:

```sql
-- Allow users to upload to their folder
CREATE POLICY "Users can upload study packs"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'study-packs' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow users to read their own study packs
CREATE POLICY "Users can read their study packs"
ON storage.objects FOR SELECT
USING (
    bucket_id = 'study-packs' 
    AND (
        (storage.foldername(name))[1] = auth.uid()::text
        OR (storage.foldername(name))[1] = 'public'
    )
);

-- Allow users to delete their own study packs
CREATE POLICY "Users can delete their study packs"
ON storage.objects FOR DELETE
USING (
    bucket_id = 'study-packs' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);
```

---

## 🎯 Bucket 3: generated-content

**Purpose**: Store AI-generated PDFs (Q&A sheets, flashcard PDFs, etc.)

**Settings**:
- **Name**: `generated-content`
- **Public**: ❌ No (Private)
- **File size limit**: 5 MB
- **Allowed MIME types**: 
  - `application/pdf`
  - `image/png`
  - `image/jpeg`

**Folder Structure**:
```
generated-content/
├── {user_id}/
│   ├── qa/
│   │   ├── {content_id}_questions.pdf
│   │   └── ...
│   ├── flashcards/
│   │   ├── {content_id}_cards.pdf
│   │   └── ...
│   └── summaries/
│       ├── {content_id}_summary.pdf
│       └── ...
```

**RLS Policies**:

```sql
-- Allow users to upload to their folder
CREATE POLICY "Users can upload generated content"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'generated-content' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow users to read their own generated content
CREATE POLICY "Users can read their generated content"
ON storage.objects FOR SELECT
USING (
    bucket_id = 'generated-content' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow users to delete their own generated content
CREATE POLICY "Users can delete their generated content"
ON storage.objects FOR DELETE
USING (
    bucket_id = 'generated-content' 
    AND (storage.foldername(name))[1] = auth.uid()::text
);
```

---

## 🔧 Setup Instructions

### Method 1: Using Supabase Dashboard (Recommended)

1. **Go to Storage**:
   - Visit your Supabase project dashboard
   - Click "Storage" in sidebar

2. **Create Each Bucket**:
   - Click "New bucket"
   - Enter name (notes, study-packs, or generated-content)
   - Set public/private as specified
   - Click "Create bucket"

3. **Configure RLS Policies**:
   - Click on the bucket
   - Go to "Policies" tab
   - Click "New policy"
   - Use "Custom" and paste the SQL from above
   - Repeat for each operation (SELECT, INSERT, UPDATE, DELETE)

### Method 2: Using SQL

Run this in Supabase SQL Editor:

```sql
-- Create storage buckets
INSERT INTO storage.buckets (id, name, public)
VALUES 
    ('notes', 'notes', false),
    ('study-packs', 'study-packs', true),
    ('generated-content', 'generated-content', false)
ON CONFLICT (id) DO NOTHING;

-- Then create RLS policies using the SQL above for each bucket
```

---

## ✅ Verification

After setup, verify buckets exist:

```sql
SELECT id, name, public, file_size_limit, created_at
FROM storage.buckets
WHERE id IN ('notes', 'study-packs', 'generated-content');
```

Should return 3 rows.

---

## 📝 Usage Examples

### Upload File (from backend):

```python
from utils.supabase_client import supabase_client

# Upload a note
with open('file.pdf', 'rb') as f:
    response = supabase_client.storage.from_('notes').upload(
        f'{user_id}/{note_id}_original.pdf',
        f,
        file_options={"content-type": "application/pdf"}
    )

# Get public URL (for public buckets)
url = supabase_client.storage.from_('study-packs').get_public_url(
    f'{user_id}/pack.zip'
)

# Get signed URL (for private buckets - expires in 1 hour)
url = supabase_client.storage.from_('notes').create_signed_url(
    f'{user_id}/{note_id}_original.pdf',
    3600  # expires in 1 hour
)
```

### Download File:

```python
# Download file
file_data = supabase_client.storage.from_('notes').download(
    f'{user_id}/{note_id}_original.pdf'
)
```

### Delete File:

```python
# Delete file
response = supabase_client.storage.from_('notes').remove([
    f'{user_id}/{note_id}_original.pdf'
])
```

---

## 🔐 Security Notes

1. **Private Buckets** (`notes`, `generated-content`):
   - Files are not publicly accessible
   - Use signed URLs for temporary access
   - RLS ensures users can only access their own files

2. **Public Bucket** (`study-packs`):
   - Files are publicly accessible via URL
   - Still protected by RLS for upload/delete
   - Good for shareable content

3. **RLS Best Practices**:
   - Always check `auth.uid()` in policies
   - Use folder structure: `{user_id}/...`
   - Test policies with different users

---

## 📊 Storage Limits

**Free Plan** (Supabase):
- 1 GB storage
- 2 GB bandwidth per month

**Pro Plan**:
- 100 GB storage
- 200 GB bandwidth per month

Monitor usage in Supabase Dashboard → Settings → Billing

---

## 🐛 Troubleshooting

### "403 Forbidden" when uploading:
- Check RLS policies are created
- Verify user is authenticated
- Confirm folder structure matches policy

### "File size too large":
- Check bucket file size limit
- Compress files before upload
- Split large files

### "Invalid MIME type":
- Check allowed MIME types in bucket settings
- Ensure file extension matches content type

---

## ✅ Checklist

- [ ] Create `notes` bucket (private)
- [ ] Create `study-packs` bucket (public)
- [ ] Create `generated-content` bucket (private)
- [ ] Add RLS policies for `notes` bucket
- [ ] Add RLS policies for `study-packs` bucket
- [ ] Add RLS policies for `generated-content` bucket
- [ ] Test file upload
- [ ] Test file download
- [ ] Test file deletion
- [ ] Verify RLS prevents unauthorized access

---

**Next Step**: After creating buckets, proceed to build the database models and utilities!
