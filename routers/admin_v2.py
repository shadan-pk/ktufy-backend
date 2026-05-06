"""
Admin Router V2 - KG-RAG Corrected Version
API endpoints for managing KG-RAG system with proper ontology
"""
import os
import shutil
import logging
import uuid
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.syllabus_processor_v2 import syllabus_processor
from services.neo4j_service_v2 import neo4j_service
from services.embedding_service_v2 import embedding_service
from services.query_router import query_router
from services.curriculum_extractor import curriculum_extractor
from utils.supabase_client import supabase_admin_client
from services.queue import get_queue
from services.processing_worker import process_syllabus_job
from services.processing_jobs import (
    create_uploaded_file,
    create_processing_job,
    get_processing_job,
    list_processing_jobs,
    format_jobs_response,
    update_processing_job,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v2/admin",
    tags=["Admin V2 - KG-RAG Management"]
)

# Upload directory
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/syllabus")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Models for V2
# ═══════════════════════════════════════════════════════════════════════════════

class SyllabusUploadResponseV2(BaseModel):
    id: str
    filename: str
    semester: int
    branch: str
    regulation: str
    status: str
    message: str
    created_at: datetime


class ProcessingJobResponseV2(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    subjects_processed: int
    total_subjects: int
    concepts_created: int
    chunks_stored: int
    relationships_created: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class ConceptResponse(BaseModel):
    id: str
    name: str
    canonical_id: str
    description: Optional[str] = None
    hours: Optional[int] = None
    subject_code: Optional[str] = None
    module_number: Optional[int] = None


class RelationshipResponse(BaseModel):
    from_concept: str
    to_concept: str
    relationship_type: str
    properties: dict = {}


class SearchQueryV2(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    semester: Optional[int] = Field(None, ge=1, le=8)
    branch: Optional[str] = None
    subject_code: Optional[str] = None
    chunk_types: Optional[List[str]] = None  # Filter by chunk type


class ConceptCreate(BaseModel):
    name: str = Field(..., min_length=2)
    subject_code: str
    module_number: int = Field(..., ge=1, le=6)
    description: Optional[str] = None
    hours: Optional[int] = None
    keywords: List[str] = []


class RelationshipCreate(BaseModel):
    from_concept_id: str
    to_concept_id: str
    relationship_type: str = Field(..., pattern="^(IS_A|PART_OF|PREREQUISITE_OF|USES|IMPLEMENTS|RELATED_TO)$")


class CurriculumExtractionResponse(BaseModel):
    status: str
    message: str
    mappings_extracted: int
    mappings_inserted: int
    branch: str
    regulation: str
    timestamp: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# System Status
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status", summary="Get system status (V2)")
async def get_system_status():
    """
    Get the current status of all KG-RAG V2 system components
    """
    status = syllabus_processor.get_status()
    return {
        "version": "2.0",
        "status": "operational" if all([
            status["neo4j"],
            status["llm_extractor"],
            status["embedding_model"],
            status.get("chat_service", True)
        ]) else "partial",
        "components": status,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/stats", summary="Get complete statistics (V2)")
async def get_statistics():
    """
    Get complete statistics for Knowledge Graph and Embeddings (V2)
    """
    stats = syllabus_processor.get_full_statistics(supabase_admin_client)
    
    kg_stats = stats.get("knowledge_graph", {})
    emb_stats = stats.get("embeddings", {}) or {}
    
    return {
        "version": "2.0",
        "total_subjects": kg_stats.get("total_subjects", 0),
        "total_modules": kg_stats.get("total_modules", 0),
        "total_concepts": kg_stats.get("total_concepts", 0),
        "total_topics": kg_stats.get("total_concepts", 0),
        "total_embeddings": emb_stats.get("total_embeddings", 0),
        "total_chunks": emb_stats.get("total_embeddings", 0),
        "knowledge_graph": {
            "total_subjects": kg_stats.get("total_subjects", 0),
            "total_modules": kg_stats.get("total_modules", 0),
            "total_concepts": kg_stats.get("total_concepts", 0),
            "total_relationships": kg_stats.get("total_relationships", 0),
            "relationship_types": kg_stats.get("relationship_types", {}),
            "branches": kg_stats.get("branches", []),
            "semesters": kg_stats.get("semesters", []),
            "regulations": kg_stats.get("regulations", [])
        },
        "embeddings": {
            "total_chunks": emb_stats.get("total_embeddings", 0),
            "subjects_covered": emb_stats.get("subjects_covered", 0),
            "chunk_types": emb_stats.get("chunk_types", {})
        },
        "system_status": "operational" if stats["system_status"]["neo4j"] else "degraded"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PDF Upload & Processing (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze-pdf", summary="Analyze syllabus PDF for metadata (V2)")
async def analyze_pdf(
    file: UploadFile = File(..., description="Syllabus PDF file")
):
    """
    Extract metadata (branch, semester, regulation) from the first page of a PDF
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    # Save temporary file for analysis
    temp_path = f"temp_{uuid.uuid4()}.pdf"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract first page text
        from services.pdf_processor import pdf_processor
        first_page_text = pdf_processor.extract_text_by_pages(temp_path, start_page=0, end_page=1)
        
        # Analyze with LLM
        from services.llm_extractor_v2 import llm_extractor
        metadata = llm_extractor.analyze_syllabus_metadata(first_page_text)
        
        return metadata
    except Exception as e:
        logger.error(f"Error analyzing PDF: {e}")
        return {"branch": None, "semester": None, "regulation": "2019", "confidence": 0}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/upload", response_model=SyllabusUploadResponseV2, summary="Upload syllabus PDF (V2)")
async def upload_syllabus(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Syllabus PDF file"),
    semester: int = Form(..., ge=1, le=8, description="Semester number"),
    branch: str = Form(..., description="Branch code (CSE, ECE, etc.)"),
    regulation: str = Form(default="2019", description="KTU regulation year (2019, 2024, 2028)")
):
    """
    Upload a KTU syllabus PDF for V2 processing
    
    The V2 pipeline:
    1. Extract text from PDF
    2. Use AI to extract VERBATIM syllabus text with ATOMIC concepts
    3. Build knowledge graph with semantic relationships (IS_A, PREREQUISITE_OF, etc.)
    4. Generate proper content chunk embeddings for RAG
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    # Validate regulation
    valid_regulations = ["2019", "2024", "2028"]
    if regulation not in valid_regulations:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid regulation. Must be one of: {valid_regulations}"
        )
    
    # Generate unique filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{branch}_S{semester}_{regulation}_{timestamp}.pdf"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    if not supabase_admin_client:
        raise HTTPException(status_code=500, detail="Supabase admin client not configured")

    file_size = os.path.getsize(file_path)
    file_row = create_uploaded_file(
        supabase_admin_client,
        filename=safe_filename,
        original_filename=file.filename,
        file_size=file_size,
        semester=semester,
        branch=branch,
        regulation=regulation,
    )

    if not file_row:
        raise HTTPException(status_code=500, detail="Failed to record uploaded file")

    job_row = create_processing_job(
        supabase_admin_client,
        file_id=file_row.get("id"),
        status="pending",
        progress=0,
        message="Queued for processing",
    )

    if not job_row:
        raise HTTPException(status_code=500, detail="Failed to create processing job")

    queue = get_queue()
    queue.enqueue(
        process_syllabus_job,
        job_row["id"],
        file_path,
        semester,
        branch,
        regulation,
        file_row.get("id"),
        job_timeout=1800,
    )

    update_processing_job(
        supabase_admin_client,
        job_row["id"],
        status="queued",
        message="Queued for processing",
    )

    return SyllabusUploadResponseV2(
        id=job_row["id"],
        filename=safe_filename,
        semester=semester,
        branch=branch,
        regulation=regulation,
        status="queued",
        message="File uploaded. Processing queued.",
        created_at=datetime.utcnow()
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Curriculum Extraction (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/extract-curriculum", response_model=CurriculumExtractionResponse, summary="Extract curriculum mappings from PDF (V2)")
async def extract_curriculum(
    file: UploadFile = File(..., description="Curriculum PDF file"),
    branch: str = Form(..., description="Branch code (CSE, ECE, etc.)"),
    regulation: str = Form(default="2019", description="KTU regulation year (2019, 2024, 2028)")
):
    """
    Extract elective group mappings from a curriculum PDF
    
    This endpoint:
    1. Reads the curriculum PDF
    2. Uses LLM to extract subject → elective group mappings
    3. Validates and stores mappings in the database
    4. Returns extraction statistics
    
    The mappings are stored in the syllabus_elective_mappings table and used
    during syllabus processing to automatically assign program_elective values.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    # Validate regulation
    valid_regulations = ["2019", "2024", "2028"]
    if regulation not in valid_regulations:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid regulation. Must be one of: {valid_regulations}"
        )
    
    # Save temporary file
    temp_path = f"temp_curriculum_{uuid.uuid4()}.pdf"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Extracting curriculum mappings from {file.filename} for {branch}/{regulation}")
        
        # Extract mappings from PDF
        mappings = curriculum_extractor.extract_elective_mappings_from_pdf(
            temp_path, 
            branch, 
            regulation
        )
        
        if not mappings:
            raise HTTPException(
                status_code=400, 
                detail="No mappings could be extracted from the PDF. Check file format."
            )
        
        logger.info(f"Extracted {len(mappings)} mappings from curriculum PDF")
        
        # Populate database
        if supabase_admin_client:
            inserted_count = curriculum_extractor.populate_elective_mappings(
                supabase_admin_client,
                mappings,
                branch,
                regulation
            )
            logger.info(f"Inserted {inserted_count} mappings into database")
        else:
            raise HTTPException(status_code=500, detail="Supabase admin client not configured")
        
        return CurriculumExtractionResponse(
            status="success",
            message=f"Extracted and stored {len(mappings)} elective mappings",
            mappings_extracted=len(mappings),
            mappings_inserted=inserted_count,
            branch=branch,
            regulation=regulation,
            timestamp=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Error extracting curriculum: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error extracting curriculum mappings: {str(e)}"
        )
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/curriculum-mappings", summary="Get curriculum elective mappings (V2)")
async def get_curriculum_mappings(
    branch: Optional[str] = Query(None, description="Filter by branch"),
    regulation: Optional[str] = Query(None, description="Filter by regulation")
):
    """
    Retrieve all stored curriculum elective mappings
    """
    if not supabase_admin_client:
        raise HTTPException(status_code=500, detail="Supabase admin client not configured")
    
    try:
        query = supabase_admin_client.table("syllabus_elective_mappings").select("*")
        
        if branch:
            query = query.eq("branch", branch)
        if regulation:
            query = query.eq("regulation", regulation)
        
        result = query.execute()
        
        return {
            "status": "success",
            "total": len(result.data) if result.data else 0,
            "mappings": result.data or [],
            "branch": branch,
            "regulation": regulation
        }
    except Exception as e:
        logger.error(f"Error retrieving curriculum mappings: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving mappings: {str(e)}"
        )


async def process_syllabus_background_v2(
    file_path: str, 
    semester: int, 
    branch: str, 
    job_id: str, 
    regulation: str = "2019"
):
    """Background task to process syllabus using V2 pipeline"""
    job = syllabus_processor.get_job(job_id)
    if job:
        await syllabus_processor.process_pdf(
            pdf_path=file_path,
            semester=semester,
            branch=branch,
            job=job,
            supabase_client=supabase_admin_client,
            regulation=regulation
        )


@router.get("/jobs", summary="List all processing jobs (V2)")
async def list_jobs():
    """
    Get a list of all V2 processing jobs
    """
    if not supabase_admin_client:
        raise HTTPException(status_code=500, detail="Supabase admin client not configured")

    jobs = list_processing_jobs(supabase_admin_client)
    formatted = format_jobs_response(supabase_admin_client, jobs)
    return {"jobs": formatted, "total": len(formatted), "version": "2.0"}


@router.get("/jobs/{job_id}", response_model=ProcessingJobResponseV2, summary="Get job status (V2)")
async def get_job_status(job_id: str):
    """
    Get the status of a specific V2 processing job
    """
    if not supabase_admin_client:
        raise HTTPException(status_code=500, detail="Supabase admin client not configured")

    job = get_processing_job(supabase_admin_client, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    formatted = format_jobs_response(supabase_admin_client, [job])[0]
    return ProcessingJobResponseV2(
        job_id=formatted.get("job_id"),
        status=formatted.get("status"),
        progress=formatted.get("progress", 0),
        message=formatted.get("message", ""),
        subjects_processed=formatted.get("subjects_processed", 0),
        total_subjects=formatted.get("total_subjects", 0),
        concepts_created=formatted.get("concepts_created", 0),
        chunks_stored=formatted.get("chunks_stored", 0),
        relationships_created=formatted.get("relationships_created", 0),
        started_at=formatted.get("started_at"),
        completed_at=formatted.get("completed_at"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Subject Management (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/subjects", summary="List all subjects (V2)")
async def list_subjects(
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester"),
    branch: Optional[str] = Query(None, description="Filter by branch"),
    regulation: Optional[str] = Query(None, description="Filter by regulation")
):
    """
    Get all subjects from the V2 knowledge graph
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    subjects = neo4j_service.get_all_subjects(
        semester=semester, 
        branch=branch, 
        regulation=regulation
    )
    
    return {
        "subjects": subjects,
        "total": len(subjects),
        "filters": {"semester": semester, "branch": branch, "regulation": regulation},
        "version": "2.0"
    }


@router.get("/subjects/{subject_code}", summary="Get subject details (V2)")
async def get_subject(subject_code: str, regulation: str = "2019"):
    """
    Get detailed information about a subject including modules, concepts, and relationships
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    subject = neo4j_service.get_subject(subject_code, regulation)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Get modules with concepts
    modules = neo4j_service.get_modules(subject_code, regulation)
    # V2 returns concepts; rename to topics for frontend compatibility
    for m in modules:
        if "concepts" in m:
            m["topics"] = m.pop("concepts")
    subject["modules"] = modules    
    # Count concepts
    total_concepts = sum(len(m.get("topics", [])) for m in modules)
    subject["total_concepts"] = total_concepts
    
    return subject


@router.delete("/subjects/{subject_code}", summary="Delete a subject (V2)")
async def delete_subject(subject_code: str, regulation: str = "2019"):
    """
    Delete a subject from knowledge graph, embeddings, and syllabus database
    """
    result = syllabus_processor.delete_subject(
        subject_code=subject_code,
        regulation=regulation,
        supabase_client=supabase_admin_client
    )
    
    if not result["knowledge_graph"] and not result.get("database_deleted"):
        raise HTTPException(status_code=404, detail="Subject not found")
    
    return {
        "message": "Subject deleted successfully",
        "subject_code": subject_code,
        "regulation": regulation,
        "embeddings_deleted": result["embeddings_deleted"],
        "database_deleted": result.get("database_deleted", False),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Concept Management (V2 - replaces Topic Management)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/subjects/{subject_code}/modules", summary="Get modules with concepts (V2)")
async def get_subject_modules(subject_code: str, regulation: str = "2019"):
    """
    Get all modules with their atomic concepts for a specific subject
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    modules = neo4j_service.get_modules(subject_code, regulation)
    # V2 returns concepts; rename to topics for frontend compatibility
    for m in modules:
        if "concepts" in m:
            m["topics"] = m.pop("concepts")

    return {
        "subject_code": subject_code,
        "regulation": regulation,
        "modules": modules,
        "total_modules": len(modules),
        "total_concepts": sum(len(m.get("topics", [])) for m in modules)
    }


@router.get("/concepts/{canonical_id}", summary="Get concept details (V2)")
async def get_concept(canonical_id: str):
    """
    Get detailed information about a concept including its relationships
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    # Get concept details
    concept = neo4j_service.get_concept(canonical_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    
    # Get relationships
    relationships = neo4j_service.get_concept_relationships(canonical_id)
    concept["relationships"] = relationships
    
    return concept


@router.get("/concepts/{canonical_id}/prerequisites", summary="Get concept prerequisites (V2)")
async def get_concept_prerequisites(canonical_id: str):
    """
    Get prerequisites for a concept
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    prereqs = neo4j_service.get_prerequisites(canonical_id)
    
    return {
        "concept_id": canonical_id,
        "prerequisites": prereqs,
        "total": len(prereqs)
    }


@router.get("/concepts/{canonical_id}/hierarchy", summary="Get concept hierarchy (V2)")
async def get_concept_hierarchy(canonical_id: str):
    """
    Get the IS_A and PART_OF hierarchy for a concept
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    hierarchy = neo4j_service.get_hierarchy(canonical_id)
    
    return {
        "concept_id": canonical_id,
        "parents": hierarchy.get("parents", []),
        "children": hierarchy.get("children", [])
    }


@router.post("/concepts", summary="Add a concept manually (V2)")
async def create_concept(concept: ConceptCreate):
    """
    Manually add an atomic concept to the knowledge graph
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    from services.llm_extractor_v2 import llm_extractor
    
    # Generate canonical ID
    canonical_id = llm_extractor.to_canonical_id(
        concept.subject_code,
        concept.module_number,
        concept.name
    )
    
    result = neo4j_service.create_concept({
        "canonical_id": canonical_id,
        "name": concept.name,
        "subject_code": concept.subject_code,
        "module_number": concept.module_number,
        "description": concept.description,
        "hours": concept.hours,
        "keywords": concept.keywords
    })
    
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create concept")
    
    return {
        "message": "Concept created successfully",
        "concept": result
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Relationships (V2 - Semantic Relationships)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/relationships", summary="Create relationship (V2)")
async def create_relationship(rel: RelationshipCreate):
    """
    Create a semantic relationship between two concepts
    
    Supported relationship types:
    - IS_A: Concept A is a type of Concept B
    - PART_OF: Concept A is part of Concept B
    - PREREQUISITE_OF: Concept A must be learned before Concept B
    - USES: Concept A uses Concept B
    - IMPLEMENTS: Concept A implements Concept B
    - RELATED_TO: Generic relationship
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    success = neo4j_service.create_relationship(
        from_id=rel.from_concept_id,
        to_id=rel.to_concept_id,
        rel_type=rel.relationship_type
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create relationship")
    
    return {
        "message": "Relationship created successfully",
        "from": rel.from_concept_id,
        "to": rel.to_concept_id,
        "type": rel.relationship_type
    }


@router.get("/relationships/types", summary="Get relationship types (V2)")
async def get_relationship_types():
    """
    Get all available semantic relationship types with descriptions
    """
    return {
        "relationship_types": [
            {
                "type": "IS_A",
                "description": "Taxonomic relationship - Concept A is a type of Concept B",
                "example": "Binary Search IS_A Search Algorithm"
            },
            {
                "type": "PART_OF",
                "description": "Compositional relationship - Concept A is a component of Concept B",
                "example": "Node PART_OF Linked List"
            },
            {
                "type": "PREREQUISITE_OF",
                "description": "Learning dependency - Concept A should be learned before Concept B",
                "example": "Arrays PREREQUISITE_OF Linked Lists"
            },
            {
                "type": "USES",
                "description": "Usage relationship - Concept A uses/depends on Concept B",
                "example": "Graph Traversal USES Queue"
            },
            {
                "type": "IMPLEMENTS",
                "description": "Implementation relationship - Concept A implements Concept B",
                "example": "Adjacency List IMPLEMENTS Graph"
            },
            {
                "type": "RELATED_TO",
                "description": "Generic association when no specific type fits",
                "example": "Recursion RELATED_TO Stack"
            }
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Search & RAG (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/search", summary="Search syllabus (V2)")
async def search_syllabus(query: SearchQueryV2):
    """
    Search the syllabus using V2 pipeline with intelligent routing
    """
    import time
    import traceback
    start_time = time.time()
    
    try:
        # Route the query
        query_type, route_metadata = query_router.route(query.query)
        chunk_types_for_search = query_router.get_vector_chunk_types(query.query)
        extracted_entities = route_metadata.get("extracted_entities", [])
        
        results = {
            "query": query.query,
            "routing": {
                "type": query_type.value,
                "chunk_types": chunk_types_for_search,
                "entities": extracted_entities
            },
            "kg_results": [],
            "vector_results": [],
            "version": "2.0"
        }
        
        # Execute based on routing
        if query_type.value in ["kg_only", "kg_then_vector", "hybrid"]:
            # Search Knowledge Graph
            if neo4j_service.is_connected():
                entity_values = [e.get("value", "") for e in extracted_entities if isinstance(e.get("value"), str)]
                search_term = entity_values[0] if entity_values else query.query
                kg_results = neo4j_service.search_concepts(search_term, limit=query.limit)
                results["kg_results"] = kg_results
        
        if query_type.value in ["vector_only", "vector_then_kg", "hybrid"]:
            # Search Vector Store
            if embedding_service.is_ready():
                vector_results = embedding_service.search(
                    supabase_client=supabase_admin_client,
                    query=query.query,
                    limit=query.limit,
                    semester=query.semester,
                    branch=query.branch,
                    subject_code=query.subject_code,
                    chunk_types=query.chunk_types or chunk_types_for_search
                )
                results["vector_results"] = vector_results
            else:
                logger.warning("Embedding service not ready for search")
        
        results["search_time_ms"] = (time.time() - start_time) * 1000
        results["total_results"] = len(results["kg_results"]) + len(results["vector_results"])
        
        return results
        
    except Exception as e:
        logger.error(f"Search failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/graph/search", summary="Search concepts (V2 Alias)")
@router.get("/search/concepts", summary="Search concepts in knowledge graph (V2)")
async def search_concepts(query: str = Query(..., alias="query"), q: Optional[str] = None, limit: int = 10):
    """
    Search atomic concepts by name or keywords in the knowledge graph
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    search_term = query or q
    concepts = neo4j_service.search_concepts(search_term, limit)
    
    return {
        "query": search_term,
        "results": concepts,
        "total": len(concepts),
        "nodes": concepts # Compat for graph view if needed
    }


@router.post("/search/analyze", summary="Analyze query routing (V2)")
async def analyze_query(query: str):
    """
    Analyze how a query would be routed without executing it
    """
    query_type, metadata = query_router.route(query)
    chunk_types = query_router.get_vector_chunk_types(query)
    kg_query_type = query_router.get_kg_query_type(query)
    
    return {
        "query": query,
        "analysis": {
            "query_type": query_type.value,
            "recommended_chunk_types": chunk_types,
            "extracted_entities": metadata.get("extracted_entities", []),
            "detected_patterns": metadata.get("detected_patterns", []),
            "kg_query_type": kg_query_type,
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Data Management (V2)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/neo4j/setup", summary="Setup Neo4j V2 schema")
async def setup_neo4j():
    """
    Setup Neo4j V2 database constraints, indexes, and full-text search
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    try:
        neo4j_service.setup_schema()
        return {
            "message": "Neo4j V2 schema created successfully",
            "features": [
                "Concept node constraints",
                "Full-text search index",
                "Semantic relationship types"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/data/clear", summary="Clear all V2 data (DANGER!)")
async def clear_all_data(confirm: bool = Query(False, description="Confirm deletion")):
    """
    Clear all V2 data from knowledge graph and embeddings
    
    ⚠️ WARNING: This action is irreversible!
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Please confirm deletion by setting confirm=true"
        )
    
    results = {
        "knowledge_graph": False,
        "embeddings_deleted": 0
    }
    
    # Clear Neo4j
    if neo4j_service.is_connected():
        results["knowledge_graph"] = neo4j_service.clear_all_data()
    
    # Clear V2 embeddings
    if supabase_admin_client:
        try:
            # Delete all V2 embeddings (those with chunk_type)
            response = supabase_admin_client.table("syllabus_embeddings").delete().neq(
                "chunk_type", None
            ).execute()
            results["embeddings_deleted"] = len(response.data) if response.data else 0
        except Exception as e:
            logger.error(f"Error clearing embeddings: {e}")
    
    return {
        "message": "V2 data cleared",
        "results": results
    }


# ═══════════════════════════════════════════════════════════════════════════════
# File Management (same as V1)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/files", summary="List uploaded files")
async def list_uploaded_files():
    """
    List all uploaded syllabus files
    """
    files = []
    
    if os.path.exists(UPLOAD_DIR):
        for filename in os.listdir(UPLOAD_DIR):
            if filename.endswith(".pdf"):
                filepath = os.path.join(UPLOAD_DIR, filename)
                stat = os.stat(filepath)
                
                # Parse filename for metadata
                parts = filename.replace(".pdf", "").split("_")
                branch = parts[0] if len(parts) > 0 else ""
                semester = int(parts[1].replace("S", "")) if len(parts) > 1 and parts[1].startswith("S") else 0
                regulation = parts[2] if len(parts) > 2 else "2019"
                
                files.append({
                    "filename": filename,
                    "branch": branch,
                    "semester": semester,
                    "regulation": regulation,
                    "size_bytes": stat.st_size,
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
    
    return {
        "files": files,
        "total": len(files),
        "upload_directory": UPLOAD_DIR
    }


@router.delete("/files/{filename}", summary="Delete uploaded file")
async def delete_file(filename: str):
    """
    Delete an uploaded file
    """
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    os.remove(filepath)
    
    return {"message": f"File '{filename}' deleted successfully"}


# ═══════════════════════════════════════════════════════════════════════════════
# Learning Path (V2 - New Feature)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/learning-path/{concept_id}", summary="Get learning path (V2)")
async def get_learning_path(concept_id: str, to_concept_id: Optional[str] = None):
    """
    Get the recommended learning path for a concept based on prerequisites.
    If to_concept_id is provided, finds shortest path between the two concepts.
    Otherwise returns the prerequisite chain.
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    if to_concept_id:
        path = neo4j_service.get_learning_path(concept_id, to_concept_id)
    else:
        # Fall back to prerequisites
        path = neo4j_service.get_topic_prerequisites(concept_id)
    
    return {
        "target_concept": concept_id,
        "learning_path": path,
        "total_steps": len(path)
    }


@router.get("/graph/explore/{concept_id}", summary="Explore concept graph (V2)")
async def explore_graph(concept_id: str, depth: int = 2):
    """
    Explore the knowledge graph around a concept
    
    Returns all connected concepts up to the specified depth
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    graph = neo4j_service.explore_graph(concept_id, depth)
    
    return {
        "center_concept": concept_id,
        "depth": depth,
        "nodes": graph.get("nodes", []),
        "edges": graph.get("edges", [])
    }
