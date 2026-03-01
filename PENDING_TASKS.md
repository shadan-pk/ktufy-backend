# KTUfy Backend — Pending Tasks

> Generated: 2026-03-01
> Source: Compared frontend spec (`BACKEND_SPEC.md`, `endpoints.md`, `ktufy_full_schema.sql`)
> against current backend implementation.

---

## Priority Legend

| Tag | Meaning |
|-----|---------|
| P0 | Blocks the app from working — implement first |
| P1 | Core feature the frontend actively calls |
| P2 | Important but has a fallback or is lower priority |
| P3 | Nice to have / admin-only |

---

## 1. API Response Format Fixes (P0) — DONE

The frontend expects specific response shapes that differ from what the backend currently returns.

### 1.1 `GET /api/v1/auth/me` — Flatten response
- [x] Frontend expects a flat JSON object with top-level fields:
  `user_id`, `email`, `name`, `registration_number`, `college`, `branch`, `semester`,
  `year_joined`, `year_ending`, `roll_number`, `metadata`, `role`, `created_at`
- [x] Backend currently returns `{ user_id, email, role, metadata: { ...all fields nested... } }`
- [x] Fix: Return all `public.users` columns as top-level fields, not nested inside `metadata`

### 1.2 `PUT /api/v1/auth/me` — Add `semester` field
- [x] Frontend sends `semester` (string like `"S6"`) as an update field
- [x] Backend `UserUpdateRequest` schema does **not** have a `semester` field
- [x] Fix: Add `semester: Optional[str]` to `UserUpdateRequest` and handle it in the upsert logic
- [x] Response must match the flat shape described in 1.1

### 1.3 `DELETE /api/v1/users/{user_id}` — Path mismatch
- [x] Frontend calls `DELETE /api/v1/users/{user_id}`
- [x] Backend has it at `DELETE /api/v1/auth/users/{user_id}`
- [x] Fix: Either add a new route at the expected path, or redirect/alias it

---

## 2. Missing Endpoints — Must Implement (P1)

These endpoints are actively called by the frontend and have no fallback.

### 2.1 `POST /api/v1/flashcards/generate` — DONE
- [x] Create a new router: `routers/flashcards.py`
- [x] Accept: `{ "topic": "string", "count": 10, "force_regenerate": false }`  (count defaults to 10)
- [x] Return: `{ "id": "uuid", "topic": "...", "flashcards": [...], "cached": bool, "created_at": "..." }`
- [x] Use Groq/Ollama LLM to generate flashcards for the given topic
- [x] Cache results in `generated_content` table (`content_type = 'flashcard'`)
- [x] Return cached version if topic already generated (bypass with `force_regenerate: true`)
- [x] Additional endpoints: `GET /` (list sets), `GET /{id}`, `DELETE /{id}`
- [x] Register router in `main.py`

### 2.2 `GET /api/v1/syllabus/branches`
- [ ] Create a new router: `routers/syllabus.py`
- [ ] Return all available branch codes from Neo4j KG
- [ ] Response: `[{ "code": "CSE", "name": "Computer Science & Engineering" }, ...]`

### 2.3 `GET /api/v1/syllabus/subjects?branch={branch}&semester={semester}`
- [ ] Add to syllabus router
- [ ] Query params: `branch` (e.g. "CSE"), `semester` (e.g. "S6")
- [ ] Return: `[{ "name": "...", "code": "CST302", "credits": 4 }, ...]`
- [ ] Source data from Neo4j knowledge graph

### 2.4 `GET /api/v1/syllabus/subject/{subjectCode}`
- [ ] Add to syllabus router
- [ ] Return full subject detail:
  ```json
  {
    "subject_name": "...",
    "subject_code": "...",
    "credits": 4,
    "modules": [{ "module_number": 1, "title": "...", "topics": ["..."], "hours": 9 }],
    "course_outcomes": ["CO1: ..."],
    "textbooks": ["..."],
    "references": ["..."]
  }
  ```
- [ ] Source from Neo4j KG + syllabus_embeddings chunks (course_outcomes, references)

### 2.5 `POST /api/v1/learning/quiz/generate`
- [ ] Create a new router: `routers/learning.py`
- [ ] Accept: `{ "topic": "...", "count": 5, "difficulty": "medium" }`
  - `count` defaults to 5, `difficulty` defaults to `"medium"`
  - `difficulty` values: `"easy"` | `"medium"` | `"hard"`
- [ ] Return:
  ```json
  {
    "topic": "...",
    "questions": [{
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "correctAnswer": 2,
      "explanation": "..."
    }]
  }
  ```
- [ ] `correctAnswer` is a **0-based index** into `options`
- [ ] Register router in `main.py`

### 2.6 `POST /api/v1/learning/match/generate`
- [ ] Add to learning router
- [ ] Accept: `{ "topic": "...", "count": 6 }`  (count defaults to 6)
- [ ] Return: `{ "topic": "...", "pairs": [{ "term": "...", "definition": "..." }] }`

---

## 3. Missing Endpoint — Should Implement (P2)

### 3.1 `POST /api/v1/coding/execute`
- [ ] Create a new router: `routers/coding.py`
- [ ] Accept: `{ "source_code": "...", "language": "python", "stdin": "" }`
- [ ] Supported languages: `python` (71), `c` (50), `cpp` (54), `java` (62) — Judge0 IDs
- [ ] Return: `{ "stdout", "stderr", "compile_output", "status": { "id", "description" }, "time", "memory" }`
- [ ] Implementation: Proxy to Judge0 CE (self-hosted or `ce.judge0.com`)
- [ ] **Has fallback**: Frontend auto-falls back to free Judge0 CE public API if this fails
- [ ] Register router in `main.py`

---

## 4. Database Schema Sync (P0)

The frontend uses `ktufy_full_schema.sql` which defines tables the backend's `schema.sql` doesn't have.

### 4.1 `public.users` table — Schema mismatch
- [x] Frontend schema has a `semester` column (TEXT, e.g. "S6")
- [x] Backend schema does not define the `users` table at all (relies on Supabase Auth)
- [x] Fix: Ensure `public.users` table matches `ktufy_full_schema.sql` definition
- [x] Run `ktufy_full_schema.sql` in Supabase, or create a migration to add missing columns

### 4.2 New tables needed (frontend uses directly via Supabase client)
The backend doesn't need REST endpoints for these, but the tables MUST exist in Supabase:
- [ ] `public.ticklists` — Study checklists (CRUD via Supabase client with RLS)
- [ ] `public.game_stats` — Learning Zone scores (UPSERT via Supabase client)
- [ ] `public.coding_progress` — Coding Hub stats (UPSERT via Supabase client)
- [ ] `public.study_dashboard` — Streak & study time (auto-created by trigger)
- [ ] `public.user_notes` — Library notes (CRUD via Supabase client)
- [ ] `public.user_bookmarks` — Library bookmarks (CRUD via Supabase client)
- [ ] `public.exam_schedule` — Exam/event calendar (read via Supabase, populated by admin)

### 4.3 Triggers needed -- create if not exist
- [ ] `on_auth_user_created` — Auto-create `public.users` row when a user signs up
- [ ] `create_study_dashboard` — Auto-create `public.study_dashboard` row on sign-up

### 4.4 Action
<!-- - [ ] Run `ktufy_full_schema.sql` in Supabase SQL Editor (it's idempotent) -->
- [ ] Verify RLS policies are active: `SELECT * FROM pg_policies WHERE schemaname = 'public'`
<!-- - [ ] Create `notes` storage bucket (public download, auth upload) -->

---

## 5. Backend Code Changes Summary

### New routers to create:
| Router | File | Endpoints |
|--------|------|-----------|
| Flashcards | `routers/flashcards.py` | `POST /generate`, `GET /`, `GET /{id}`, `DELETE /{id}` |
| Syllabus | `routers/syllabus.py` | `GET /branches`, `GET /subjects`, `GET /subject/{code}` |
| Learning | `routers/learning.py` | `POST /quiz/generate`, `POST /match/generate` |
| Coding | `routers/coding.py` | `POST /execute` |

### Files to modify:
| File | Change |
|------|--------|
| `main.py` | Register 4 new routers |
| `schemas/user.py` | Add `semester` field to `UserUpdateRequest`; create flat `UserProfileResponse` |
| `routers/auth.py` | Fix `GET /me` response shape (flatten); add `semester` to `PUT /me`; add route alias for `DELETE /api/v1/users/{user_id}` |

### New schema files:
| File | Models |
|------|--------|
| `schemas/flashcard.py` | `FlashcardRequest`, `FlashcardResponse` |
| `schemas/syllabus.py` | `BranchResponse`, `SubjectListItem`, `SubjectDetail`, `ModuleDetail` |
| `schemas/learning.py` | `QuizRequest`, `QuizResponse`, `MatchRequest`, `MatchResponse` |
| `schemas/coding.py` | `CodeExecuteRequest`, `CodeExecuteResponse` |

---

## 6. Implementation Order (Fastest to Working MVP)

```
Step 1: Database sync
  → Run ktufy_full_schema.sql in Supabase
  → Verify triggers and RLS

Step 2: Fix existing endpoints (P0)
  → Fix GET /api/v1/auth/me response shape (flatten)
  → Add semester to PUT /api/v1/auth/me
  → Add DELETE /api/v1/users/{user_id} route

Step 3: Flashcards endpoint (P1)
  → POST /api/v1/flashcards/generate

Step 4: Syllabus endpoints (P1)
  → GET /api/v1/syllabus/branches
  → GET /api/v1/syllabus/subjects
  → GET /api/v1/syllabus/subject/{code}

Step 5: Learning endpoints (P1)
  → POST /api/v1/learning/quiz/generate
  → POST /api/v1/learning/match/generate

Step 6: Coding endpoint (P2)
  → POST /api/v1/coding/execute
```

---

## 7. What's Already Done (No Action Needed)

These frontend-expected endpoints already exist and work:

| Endpoint | Status |
|----------|--------|
| `GET /api/v1/auth/me` | Exists (needs response shape fix) |
| `PUT /api/v1/auth/me` | Exists (needs semester field) |
| `POST /api/v1/auth/request-password-reset` | Working |
| `POST /api/v1/auth/verify-email` | Working |
| `POST /api/v1/chat/message` | Working |
| `GET /api/v1/chat/sessions` | Working |
| `POST /api/v1/chat/sessions` | Working |
| `GET /api/v1/chat/sessions/{id}` | Working |
| `PUT /api/v1/chat/sessions/{id}` | Working |
| `DELETE /api/v1/chat/sessions/{id}` | Working |

Tables handled directly by Supabase client (no backend endpoints needed):
- `ticklists` — once table exists
- `user_notes` — once table exists
- `user_bookmarks` — once table exists
- `exam_schedule` — once table exists and admin populates it
- `game_stats` — once table exists
- `coding_progress` — once table exists
- `study_dashboard` — once table + trigger exists
