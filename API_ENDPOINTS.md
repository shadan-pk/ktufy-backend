# KTUfy Backend API - All Endpoints

> Total: **62 endpoints** across 5 routers + main app

---

## General Endpoints (main.py)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/` | Root endpoint - API welcome & health check | No |
| GET | `/health` | Detailed health check (API, Neo4j, embeddings status) | No |
| GET | `/admin` | Admin dashboard (HTML page) | No |
| GET | `/api/v1/status` | V1 API status and feature availability | No |
| GET | `/api/v2/status` | V2 API status with KG-RAG feature details | No |

---

## Authentication (`/api/v1/auth`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/auth/me` | Get current user profile | Required |
| PUT | `/api/v1/auth/me` | Update current user profile (name, college, branch, etc.) | Required |
| POST | `/api/v1/auth/request-password-reset` | Send password reset email (public) | No |
| POST | `/api/v1/auth/verify-email` | Send email verification link | Required |
| DELETE | `/api/v1/auth/users/{user_id}` | Delete user account (own or admin) | Required |
| GET | `/api/v1/auth/status` | Check authentication status | Optional |
| POST | `/api/v1/auth/verify-token` | Verify a JWT token validity | No |
| GET | `/api/v1/auth/protected-example` | Example protected endpoint | Required |
| GET | `/api/v1/auth/public-example` | Example public endpoint | No |

---

## Chat (`/api/v1/chat`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/chat/sessions` | Create a new chat session | Required |
| GET | `/api/v1/chat/sessions` | Get all sessions for current user (paginated) | Required |
| GET | `/api/v1/chat/sessions/{session_id}` | Get session with all messages | Required |
| POST | `/api/v1/chat/message` | Send message and get AI response (KG-RAG) | Required |
| PUT | `/api/v1/chat/sessions/{session_id}` | Update session (title, model) | Required |
| DELETE | `/api/v1/chat/sessions/{session_id}` | Delete session and all messages | Required |
| GET | `/api/v1/chat/info` | Get chat service info (provider, features) | Required |

---

## Flashcards (`/api/v1/flashcards`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/flashcards/generate` | Generate flashcards for a topic (cached or fresh via LLM) | Required |
| GET | `/api/v1/flashcards` | List all saved flashcard sets for current user | Required |
| GET | `/api/v1/flashcards/search?topic={topic}` | Search flashcard sets by topic (fuzzy match) | Required |
| GET | `/api/v1/flashcards/{id}` | Get a specific flashcard set by ID | Required |
| DELETE | `/api/v1/flashcards/{id}` | Delete a saved flashcard set | Required |

---

## Admin V1 - KG-RAG Management (`/api/v1/admin`)

### System

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/admin/status` | Get system status (Neo4j, LLM, embeddings) | No |
| GET | `/api/v1/admin/stats` | Get full KG and embedding statistics | No |
| GET | `/api/v1/admin/active-users` | Get active authenticated users (window_minutes param) | No |

### PDF Upload & Processing

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/admin/upload` | Upload syllabus PDF (background processing) | No |
| GET | `/api/v1/admin/jobs` | List all processing jobs | No |
| GET | `/api/v1/admin/jobs/{job_id}` | Get specific job status | No |

### Subject Management

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/admin/subjects` | List all subjects (filter by semester, branch, regulation) | No |
| GET | `/api/v1/admin/subjects/{subject_code}` | Get subject details with modules and topics | No |
| POST | `/api/v1/admin/subjects` | Add subject manually | No |
| DELETE | `/api/v1/admin/subjects/{subject_code}` | Delete subject from KG and embeddings | No |

### Module & Topic Management

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/admin/subjects/{subject_code}/modules` | Get modules for a subject | No |
| POST | `/api/v1/admin/modules` | Add a module to a subject | No |
| POST | `/api/v1/admin/topics` | Add a topic to a module (with embedding) | No |

### Relationships

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/admin/relationships/prerequisite` | Create prerequisite between subjects | No |
| GET | `/api/v1/admin/subjects/{subject_code}/prerequisites` | Get prerequisites for a subject | No |

### Search

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/admin/search` | Search syllabus by vector similarity | No |
| GET | `/api/v1/admin/search/topics` | Search topics by name/keywords in KG | No |

### Data & File Management

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/admin/neo4j/setup` | Setup Neo4j constraints and indexes | No |
| DELETE | `/api/v1/admin/data/clear` | Clear all KG and embedding data (requires confirm=true) | No |
| GET | `/api/v1/admin/files` | List uploaded syllabus PDF files | No |
| DELETE | `/api/v1/admin/files/{filename}` | Delete an uploaded file | No |

---

## Admin V2 - KG-RAG Corrected (`/api/v2/admin`)

### System

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v2/admin/status` | Get V2 system status | No |
| GET | `/api/v2/admin/stats` | Get V2 KG and chunk statistics | No |

### PDF Upload & Processing

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v2/admin/upload` | Upload syllabus PDF (V2 pipeline with atomic concepts) | No |
| GET | `/api/v2/admin/jobs` | List all V2 processing jobs | No |
| GET | `/api/v2/admin/jobs/{job_id}` | Get V2 job status (includes concepts/chunks/relationships count) | No |

### Subject Management

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v2/admin/subjects` | List all subjects (V2 KG) | No |
| GET | `/api/v2/admin/subjects/{subject_code}` | Get subject with modules, concepts, relationships | No |
| DELETE | `/api/v2/admin/subjects/{subject_code}` | Delete subject (V2) | No |

### Concept Management

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v2/admin/subjects/{subject_code}/modules` | Get modules with atomic concepts | No |
| GET | `/api/v2/admin/concepts/{canonical_id}` | Get concept details with relationships | No |
| GET | `/api/v2/admin/concepts/{canonical_id}/prerequisites` | Get concept prerequisites | No |
| GET | `/api/v2/admin/concepts/{canonical_id}/hierarchy` | Get IS_A/PART_OF hierarchy | No |
| POST | `/api/v2/admin/concepts` | Add concept manually | No |

### Relationships

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v2/admin/relationships` | Create semantic relationship between concepts | No |
| GET | `/api/v2/admin/relationships/types` | Get all relationship types with descriptions | No |

### Search

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v2/admin/search` | Intelligent search with query routing (KG/Vector/Hybrid) | No |
| GET | `/api/v2/admin/search/concepts` | Search concepts by name/keywords | No |
| POST | `/api/v2/admin/search/analyze` | Analyze query routing without executing | No |

### Learning & Graph

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v2/admin/learning-path/{concept_id}` | Get recommended learning path from prerequisites | No |
| GET | `/api/v2/admin/graph/explore/{concept_id}` | Explore knowledge graph around a concept | No |

### Data & File Management

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v2/admin/neo4j/setup` | Setup Neo4j V2 schema (constraints, full-text index) | No |
| DELETE | `/api/v2/admin/data/clear` | Clear all V2 data (requires confirm=true) | No |
| GET | `/api/v2/admin/files` | List uploaded files | No |
| DELETE | `/api/v2/admin/files/{filename}` | Delete uploaded file | No |

---

## Auth Legend

| Label | Meaning |
|-------|---------|
| **Required** | Must include `Authorization: Bearer <token>` header |
| **Optional** | Works with or without auth token |
| **No** | Public endpoint, no auth needed |

---

## API Documentation URLs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
