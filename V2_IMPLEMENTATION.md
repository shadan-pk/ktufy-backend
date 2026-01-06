# KG-RAG V2 Implementation Complete

## Summary

The KTUfy backend has been upgraded to V2 with a corrected KG-RAG (Knowledge Graph + Retrieval Augmented Generation) implementation following strict architectural guidelines.

## What Was Built

### V2 Services Created

| File | Purpose | Key Features |
|------|---------|--------------|
| `services/llm_extractor_v2.py` | Verbatim syllabus extraction | Atomic concepts, canonical naming, relationship extraction |
| `services/neo4j_service_v2.py` | Knowledge Graph with ontology | Concept nodes, semantic relationships, graph queries |
| `services/embedding_service_v2.py` | Chunk-based embeddings | Content chunks, chunk_type filtering, BGE prefix support |
| `services/query_router.py` | Intelligent query routing | KG_ONLY, VECTOR_ONLY, HYBRID routing |
| `services/syllabus_processor_v2.py` | V2 pipeline orchestrator | Connects all V2 services |
| `routers/admin_v2.py` | V2 API endpoints | `/api/v2/admin/*` routes |
| `database/syllabus_embeddings_v2.sql` | Updated Supabase schema | chunk_type, HNSW index, V2 functions |

### Architecture Corrections

#### 1. Verbatim Extraction (No Paraphrasing)
- **Before**: LLM would rephrase syllabus text
- **After**: Strict extraction with `temperature=0.05` and explicit instructions to copy exact text

#### 2. Atomic Concepts (Not Compound Topics)
- **Before**: Topics like "DFS and BFS", "Stacks and Queues"
- **After**: Split into atomic concepts: "DFS", "BFS" with RELATED_TO relationship

#### 3. Canonical Naming Convention
- **Format**: `{subject_code}_{module}_{concept}` in snake_case
- **Example**: `cs201_m1_arrays`, `cs201_m2_binary_search`

#### 4. Semantic Relationships
- **Before**: Only `HAS_MODULE` and `CONTAINS`
- **After**: Full ontology with:
  - `IS_A` - Taxonomic (Binary Search IS_A Search Algorithm)
  - `PART_OF` - Compositional (Node PART_OF Linked List)
  - `PREREQUISITE_OF` - Learning dependency
  - `USES` - Usage relationship
  - `IMPLEMENTS` - Implementation relationship
  - `RELATED_TO` - Generic association

#### 5. Proper Content Chunking
- **Before**: Embedded only topic titles
- **After**: Full content chunks with types:
  - `syllabus_content` - Full syllabus text
  - `topic_list` - List of topics per module
  - `topic_detail` - Individual topic explanations
  - `course_outcomes` - COs with Bloom's levels
  - `references` - Textbooks and references

#### 6. Query Routing
- **KG_ONLY**: "What topics are in Module 2?"
- **VECTOR_ONLY**: "Explain how binary search works"
- **KG_THEN_VECTOR**: "Prerequisites for graph algorithms"
- **VECTOR_THEN_KG**: "What is DFS and how is it related to BFS?"
- **HYBRID**: Complex queries needing both

## Data Flow

```
PDF Upload
    │
    ▼
┌─────────────────────────────────────┐
│  LLM Extractor V2                   │
│  - Verbatim extraction              │
│  - Atomic concept splitting         │
│  - Canonical ID generation          │
│  - Relationship extraction          │
│  - Content chunk generation         │
└─────────────────────────────────────┘
    │
    ├────────────────────┬────────────────────┐
    ▼                    ▼                    ▼
┌──────────┐      ┌──────────────┐    ┌──────────────┐
│  Neo4j   │      │   Neo4j      │    │   Supabase   │
│ Structure│      │ Relationships│    │  Embeddings  │
│ (Nodes)  │      │ (Semantic)   │    │  (Chunks)    │
└──────────┘      └──────────────┘    └──────────────┘
    │                    │                    │
    └────────────────────┴────────────────────┘
                         │
                         ▼
                 ┌──────────────┐
                 │ Query Router │
                 │ Determines   │
                 │ data source  │
                 └──────────────┘
                         │
                         ▼
                 ┌──────────────┐
                 │    Chat      │
                 │   Service    │
                 └──────────────┘
```

## API Endpoints

### V2 Admin API (`/api/v2/admin`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | System status (V2) |
| GET | `/stats` | Full statistics |
| POST | `/upload` | Upload syllabus PDF |
| GET | `/jobs` | List processing jobs |
| GET | `/jobs/{id}` | Job status |
| GET | `/subjects` | List subjects |
| GET | `/subjects/{code}` | Subject details |
| GET | `/subjects/{code}/modules` | Modules with concepts |
| GET | `/concepts/{id}` | Concept details |
| GET | `/concepts/{id}/prerequisites` | Prerequisites |
| GET | `/concepts/{id}/hierarchy` | IS_A/PART_OF hierarchy |
| POST | `/concepts` | Create concept |
| POST | `/relationships` | Create relationship |
| GET | `/relationships/types` | Available relationship types |
| POST | `/search` | Search with routing |
| GET | `/search/concepts` | Search concepts |
| POST | `/search/analyze` | Analyze query routing |
| GET | `/learning-path/{id}` | Get learning path |
| GET | `/graph/explore/{id}` | Explore graph |
| POST | `/neo4j/setup` | Setup V2 schema |
| DELETE | `/data/clear` | Clear all data |

## Setup Instructions

### 1. Run SQL Migration

Execute in Supabase SQL Editor:
```sql
-- Run the contents of database/syllabus_embeddings_v2.sql
```

### 2. Configure Neo4j

Update `.env` with correct Neo4j credentials:
```env
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=KTUfy
```

### 3. Setup Neo4j Schema

Call the setup endpoint:
```bash
curl -X POST http://localhost:8000/api/v2/admin/neo4j/setup
```

### 4. Start the Server

```bash
python main.py
```

### 5. Upload a Syllabus

Via API:
```bash
curl -X POST "http://localhost:8000/api/v2/admin/upload" \
  -F "file=@syllabus.pdf" \
  -F "semester=3" \
  -F "branch=CSE" \
  -F "regulation=2019"
```

Or via the Admin Dashboard at `/admin`

## Key Differences V1 vs V2

| Aspect | V1 | V2 |
|--------|----|----|
| Extraction | Paraphrased | Verbatim |
| Topics | Compound | Atomic |
| Naming | Inconsistent | Canonical snake_case |
| Relationships | 2 types | 6 semantic types |
| Embeddings | Title only | Full content chunks |
| Chunk types | None | 5 distinct types |
| Query routing | None | Intelligent routing |
| API prefix | `/api/v1/admin` | `/api/v2/admin` |

## Testing

Test the V2 status endpoint:
```bash
curl http://localhost:8000/api/v2/status
```

Expected response:
```json
{
  "api_version": "v2",
  "status": "active",
  "features": {
    "kg_rag_v2": "operational",
    "verbatim_extraction": "operational",
    "atomic_concepts": "operational",
    "semantic_relationships": "operational",
    "query_routing": "operational",
    "chunk_based_embeddings": "operational"
  }
}
```

## Files Modified

- `main.py` - Added V2 router import and V2 status endpoint
- `requirements.txt` - Added pydantic-settings

## Files Created

- `services/llm_extractor_v2.py`
- `services/neo4j_service_v2.py`
- `services/embedding_service_v2.py`
- `services/query_router.py`
- `services/syllabus_processor_v2.py`
- `routers/admin_v2.py`
- `database/syllabus_embeddings_v2.sql`
- `V2_IMPLEMENTATION.md` (this file)

## Next Steps

1. **Test with real PDF**: Upload a KTU syllabus PDF
2. **Verify atomic splitting**: Check concepts are properly atomic
3. **Update chat service**: Integrate query routing into chat
4. **Build V2 admin dashboard**: Update UI for concepts/relationships
5. **Add more relationship inference**: Auto-detect prerequisites
