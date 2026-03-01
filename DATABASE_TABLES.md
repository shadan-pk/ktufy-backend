# KTUfy Backend - Database Tables Reference

> All tables are hosted in **Supabase (PostgreSQL)** with Row Level Security (RLS) and a **Neo4j** knowledge graph.

---

## Supabase (PostgreSQL) Tables

### 1. `users` (Supabase Auth + public.users)

Managed by Supabase Auth (`auth.users`) with a linked `public.users` table for extended profile data.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | User ID (from auth.users) |
| email | TEXT | User email |
| name | TEXT | Full name |
| registration_number | TEXT | KTU registration number |
| college | TEXT | College name |
| branch | TEXT | Branch (CSE, ECE, etc.) |
| year_joined | INTEGER | Year of admission |
| year_ending | INTEGER | Expected graduation year |
| roll_number | TEXT | Roll number |
| metadata | JSONB | Additional user data |

**RLS**: Users can only read/update their own profile.

---

### 2. `notes`

Stores user-uploaded study materials with AI processing status.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| user_id | UUID (FK -> auth.users) | Owner |
| file_path | TEXT | Storage path |
| file_url | TEXT | Public/signed URL |
| file_name | TEXT | Original filename |
| file_size | INTEGER | Size in bytes |
| file_type | TEXT | MIME type |
| subject | TEXT | Subject name |
| semester | INTEGER (1-8) | Semester number |
| title | TEXT | Note title |
| description | TEXT | Optional description |
| status | TEXT | `pending` / `processing` / `completed` / `failed` |
| processing_error | TEXT | Error message if failed |
| ai_results | JSONB | AI-generated results |
| embeddings_generated | BOOLEAN | Whether embeddings exist |
| chunk_count | INTEGER | Number of text chunks |
| created_at | TIMESTAMPTZ | Created timestamp |
| updated_at | TIMESTAMPTZ | Auto-updated timestamp |

**RLS**: Users can CRUD their own notes only.

---

### 3. `progress`

Tracks user progress through syllabus modules.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| user_id | UUID (FK -> auth.users) | Owner |
| subject | TEXT | Subject name |
| semester | INTEGER (1-8) | Semester number |
| module_id | TEXT | Module identifier |
| module_name | TEXT | Module display name |
| completed | BOOLEAN | Module completed? |
| completion_percentage | INTEGER (0-100) | Progress percentage |
| time_spent_minutes | INTEGER | Total study time |
| last_studied | TIMESTAMPTZ | Last study timestamp |
| topics_completed | TEXT[] | Array of completed topic names |
| notes | TEXT | User notes |
| created_at | TIMESTAMPTZ | Created timestamp |
| updated_at | TIMESTAMPTZ | Auto-updated timestamp |

**Unique constraint**: (user_id, subject, semester, module_id)
**RLS**: Users can CRUD their own progress only.

---

### 4. `generated_content`

Stores AI-generated study materials (Q&A, flashcards, summaries, quizzes, mind maps).

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| user_id | UUID (FK -> auth.users) | Owner |
| note_id | UUID (FK -> notes) | Source note (optional) |
| content_type | TEXT | `qa` / `flashcard` / `summary` / `quiz` / `mind_map` |
| content | JSONB | Generated content data |
| title | TEXT | Content title |
| difficulty | TEXT | `easy` / `medium` / `hard` |
| subject | TEXT | Subject name |
| semester | INTEGER (1-8) | Semester number |
| module_id | TEXT | Module identifier |
| view_count | INTEGER | Times viewed |
| rating | DECIMAL(3,2) | User rating (0-5) |
| created_at | TIMESTAMPTZ | Created timestamp |
| updated_at | TIMESTAMPTZ | Auto-updated timestamp |

**RLS**: Users can CRUD their own generated content only.

---

### 5. `study_sessions`

Records individual study sessions with time tracking and performance.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| user_id | UUID (FK -> auth.users) | Owner |
| subject | TEXT | Subject studied |
| semester | INTEGER (1-8) | Semester number |
| duration_minutes | INTEGER | Session duration |
| session_date | DATE | Date of session |
| started_at | TIMESTAMPTZ | Session start time |
| ended_at | TIMESTAMPTZ | Session end time |
| topics_covered | TEXT[] | Array of topic names |
| notes_used | UUID[] | Array of note IDs used |
| questions_attempted | INTEGER | Questions attempted |
| questions_correct | INTEGER | Correct answers |
| accuracy_percentage | DECIMAL(5,2) | Accuracy % |
| session_notes | TEXT | Session notes |
| created_at | TIMESTAMPTZ | Created timestamp |

**RLS**: Users can CRUD their own sessions only.

---

### 6. `chat_history`

Logs KG-RAG chatbot conversations (legacy, per-message format).

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| user_id | UUID (FK -> auth.users) | Owner |
| query | TEXT | User's question |
| response | TEXT | AI response |
| sources | JSONB | Source references used |
| context_used | TEXT[] | Context snippets used |
| confidence | DECIMAL(3,2) | AI confidence (0-1) |
| model_used | TEXT | LLM model name |
| tokens_used | INTEGER | Tokens consumed |
| subject | TEXT | Related subject |
| semester | INTEGER (1-8) | Related semester |
| helpful | BOOLEAN | User feedback |
| feedback | TEXT | User feedback text |
| rating | INTEGER (1-5) | User rating |
| created_at | TIMESTAMPTZ | Created timestamp |

**RLS**: Users can CRUD their own chat history only.

---

### 7. `chat_sessions`

Chat sessions for the multi-turn conversation system.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| user_id | UUID (FK -> auth.users) | Owner |
| title | TEXT | Session title (default: 'New Chat') |
| model_name | TEXT | LLM model (default: 'llama3') |
| created_at | TIMESTAMPTZ | Created timestamp |
| updated_at | TIMESTAMPTZ | Auto-updated timestamp |
| metadata | JSONB | Additional session data |

**RLS**: Users can CRUD their own sessions only.

---

### 8. `chat_messages`

Individual messages within chat sessions.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| session_id | UUID (FK -> chat_sessions, CASCADE) | Parent session |
| role | TEXT | `user` / `assistant` / `system` |
| content | TEXT | Message content |
| tokens_used | INTEGER | Tokens consumed |
| created_at | TIMESTAMPTZ | Created timestamp |
| metadata | JSONB | Additional message data |

**RLS**: Users can access messages in their own sessions only (via JOIN on chat_sessions).

---

### 9. `syllabus_embeddings`

Vector embeddings for RAG-based syllabus search. Used by both V1 and V2 pipelines.

#### V1 Columns

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL (PK) | Auto-incremented |
| content | TEXT | Embedded text content |
| embedding | vector(768) | Vector embedding (BAAI/bge-base-en-v1.5) |
| subject_code | TEXT | Subject code |
| subject_name | TEXT | Subject name |
| module_number | INTEGER | Module number |
| module_name | TEXT | Module name |
| topic_name | TEXT | Topic name |
| keywords | TEXT[] | Related keywords |
| semester | INTEGER | Semester |
| branch | TEXT | Branch |
| regulation | TEXT | KTU regulation (default: '2019') |
| created_at | TIMESTAMPTZ | Created timestamp |
| updated_at | TIMESTAMPTZ | Auto-updated timestamp |

#### V2 Additional Columns

| Column | Type | Description |
|--------|------|-------------|
| chunk_id | TEXT (UNIQUE) | Chunk identifier (e.g., "cs201_m1_overview") |
| chunk_type | TEXT | `syllabus_content` / `topic_list` / `topic_detail` / `course_outcomes` / `references` |
| module_id | TEXT | Canonical module ID (e.g., "cs201_m1") |
| topic_id | TEXT | Canonical topic ID (e.g., "cs201_m1_arrays") |

**Index**: HNSW index for fast vector similarity search (cosine distance).

**Functions**:
- `search_syllabus()` - V1 similarity search
- `search_syllabus_v2()` - V2 similarity search with chunk_type filtering
- `get_concept_chunks()` - Get chunks by concept ID
- `get_module_chunks()` - Get chunks by module ID
- `get_syllabus_stats()` / `get_syllabus_stats_v2()` - Statistics

---

### 10. `uploaded_files`

Tracks uploaded syllabus PDF files and their processing status.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| filename | TEXT | Stored filename |
| original_filename | TEXT | Original upload name |
| file_type | TEXT | File type (default: 'pdf') |
| file_size | BIGINT | Size in bytes |
| semester | INTEGER | Semester |
| branch | TEXT | Branch |
| regulation | TEXT | KTU regulation (default: '2019') |
| status | TEXT | `pending` / `processing` / `completed` / `failed` |
| error_message | TEXT | Error details |
| subjects_count | INTEGER | Subjects found |
| modules_count | INTEGER | Modules found |
| topics_count | INTEGER | Topics found |
| chunks_count | INTEGER | Chunks created (V2) |
| uploaded_at | TIMESTAMPTZ | Upload timestamp |
| processed_at | TIMESTAMPTZ | Processing completion time |
| uploaded_by | UUID (FK -> auth.users) | Uploader |

---

### 11. `processing_jobs`

Tracks background syllabus processing jobs.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| file_id | UUID (FK -> uploaded_files) | Associated file |
| status | TEXT | `pending` / `processing` / `completed` / `failed` |
| progress | INTEGER | Progress percentage (0-100) |
| message | TEXT | Current status message |
| subjects_processed | INTEGER | Subjects processed so far |
| total_subjects | INTEGER | Total subjects to process |
| result | JSONB | Processing result data |
| error | TEXT | Error details |
| started_at | TIMESTAMPTZ | Job start time |
| completed_at | TIMESTAMPTZ | Job completion time |
| created_at | TIMESTAMPTZ | Created timestamp |

---

## Neo4j Knowledge Graph

### V1 Node Types

| Node Label | Properties | Description |
|------------|-----------|-------------|
| **Subject** | code, name, semester, branch, regulation, credits | KTU subject |
| **Module** | number, name, hours, subject_code | Subject module |
| **Topic** | name, description, keywords[], subject_code, module_id | Module topic |

### V1 Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| HAS_MODULE | Subject | Module | Subject contains module |
| HAS_TOPIC | Module | Topic | Module contains topic |
| PREREQUISITE_OF | Subject | Subject | Subject dependency |

### V2 Node Types

| Node Label | Properties | Description |
|------------|-----------|-------------|
| **Subject** | code, name, semester, branch, regulation, credits | KTU subject |
| **Module** | number, name, hours, subject_code, canonical_id | Subject module |
| **Concept** | canonical_id, name, description, hours, keywords[], subject_code, module_number | Atomic concept |

### V2 Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| HAS_MODULE | Subject | Module | Subject contains module |
| HAS_CONCEPT | Module | Concept | Module contains concept |
| IS_A | Concept | Concept | Taxonomic (e.g., Binary Search IS_A Search Algorithm) |
| PART_OF | Concept | Concept | Compositional (e.g., Node PART_OF Linked List) |
| PREREQUISITE_OF | Concept | Concept | Learning dependency |
| USES | Concept | Concept | Usage dependency |
| IMPLEMENTS | Concept | Concept | Implementation relationship |
| RELATED_TO | Concept | Concept | Generic association |

---

## Helper Views (PostgreSQL)

| View | Description |
|------|-------------|
| `user_study_stats` | Aggregated study statistics per user (total days, minutes, sessions) |
| `note_processing_stats` | Note processing status counts per user |

## Helper Functions (PostgreSQL)

| Function | Description |
|----------|-------------|
| `get_user_total_study_time(user_id)` | Returns total study minutes for a user |
| `get_user_subject_progress(user_id, subject, semester)` | Returns module completion stats |
| `search_syllabus(embedding, ...)` | V1 vector similarity search |
| `search_syllabus_v2(embedding, ...)` | V2 vector similarity search with chunk filtering |
| `get_concept_chunks(concept_id, ...)` | Get embedding chunks for a concept |
| `get_module_chunks(module_id, ...)` | Get embedding chunks for a module |
| `get_syllabus_stats()` | V1 embedding statistics |
| `get_syllabus_stats_v2()` | V2 embedding statistics |

---

## SQL Files

| File | Description |
|------|-------------|
| `database/schema.sql` | Core tables: notes, progress, generated_content, study_sessions, chat_history |
| `database/syllabus_embeddings.sql` | V1 embeddings table, uploaded_files, processing_jobs |
| `database/syllabus_embeddings_v2.sql` | V2 embeddings table with chunk support |
| `database/migrate_v1_to_v2.sql` | Migration script from V1 to V2 schema |
