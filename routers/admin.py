"""
Admin Router
API endpoints for managing KG-RAG system
"""
import os
import shutil
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from schemas.admin import (
    SyllabusUploadRequest, SyllabusUploadResponse, ProcessingJobResponse,
    SubjectResponse, SubjectListResponse, SubjectCreate,
    KnowledgeGraphStats, EmbeddingStats, RAGStats,
    SearchQuery, SearchResponse, SearchResult,
    UploadedFileResponse, UploadedFilesListResponse,
    ModuleCreate, TopicCreate, RelationshipCreate
)
from services.syllabus_processor_v2 import syllabus_processor
from services.neo4j_service_v2 import neo4j_service
from services.embedding_service_v2 import embedding_service
from services.active_users import active_user_tracker
from utils.supabase_client import supabase_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin - KG-RAG Management"]
)

# Upload directory
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/syllabus")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# System Status
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status", summary="Get system status")
async def get_system_status():
    """
    Get the current status of all KG-RAG system components
    """
    status = syllabus_processor.get_status()
    return {
        "status": "operational" if all([
            status["neo4j"],
            status["llm_extractor"],
            status["embedding_model"]
        ]) else "partial",
        "components": status,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/stats", response_model=RAGStats, summary="Get complete statistics")
async def get_statistics():
    """
    Get complete statistics for Knowledge Graph and Embeddings
    """
    stats = syllabus_processor.get_full_statistics(supabase_admin_client)
    
    kg_stats = stats.get("knowledge_graph", {})
    emb_stats = stats.get("embeddings", {}) or {}
    
    return RAGStats(
        knowledge_graph=KnowledgeGraphStats(
            total_subjects=kg_stats.get("total_subjects", 0),
            total_modules=kg_stats.get("total_modules", 0),
            total_topics=kg_stats.get("total_topics", 0),
            total_relationships=kg_stats.get("total_relationships", 0),
            branches=kg_stats.get("branches", []),
            semesters=kg_stats.get("semesters", []),
            regulations=kg_stats.get("regulations", []),
            last_updated=None
        ),
        embeddings=EmbeddingStats(
            total_embeddings=emb_stats.get("total_embeddings", 0),
            subjects_covered=emb_stats.get("subjects_covered", 0),
            topics_covered=emb_stats.get("topics_covered", 0),
            last_updated=None
        ),
        system_status="operational" if stats["system_status"]["neo4j"] else "degraded"
    )


@router.get("/active-users", summary="Get active authenticated users")
async def get_active_users(window_minutes: int = Query(10, ge=1, le=1440)):
    """Return users seen within the last N minutes (based on authenticated requests)."""
    active = await active_user_tracker.get_active(window_seconds=window_minutes * 60)
    return {
        "window_minutes": window_minutes,
        "total": len(active),
        "users": [u.to_dict() for u in active],
        "timestamp": datetime.utcnow().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PDF Upload & Processing
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/upload", response_model=SyllabusUploadResponse, summary="Upload syllabus PDF")
async def upload_syllabus(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Syllabus PDF file"),
    semester: int = Form(..., ge=1, le=8, description="Semester number"),
    branch: str = Form(..., description="Branch code (CSE, ECE, etc.)"),
    regulation: str = Form(default="2019", description="KTU regulation year")
):
    """
    Upload a KTU syllabus PDF for processing
    
    The PDF will be processed in the background:
    1. Extract text from PDF
    2. Use AI to identify subjects, modules, and topics
    3. Create knowledge graph in Neo4j
    4. Generate embeddings for RAG
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
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
    
    # Create processing job
    job = syllabus_processor.create_job(safe_filename, semester, branch)
    
    # Process in background
    background_tasks.add_task(
        process_syllabus_background,
        file_path, semester, branch, job.job_id, regulation
    )
    
    return SyllabusUploadResponse(
        id=job.job_id,
        filename=safe_filename,
        semester=semester,
        branch=branch,
        status=job.status,
        message="File uploaded. Processing started in background.",
        created_at=datetime.utcnow()
    )


async def process_syllabus_background(file_path: str, semester: int, branch: str, job_id: str, regulation: str = "2019"):
    """Background task to process syllabus"""
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


@router.get("/jobs", summary="List all processing jobs")
async def list_jobs():
    """
    Get a list of all processing jobs
    """
    return {
        "jobs": syllabus_processor.get_all_jobs(),
        "total": len(syllabus_processor.jobs)
    }


@router.get("/jobs/{job_id}", response_model=ProcessingJobResponse, summary="Get job status")
async def get_job_status(job_id: str):
    """
    Get the status of a specific processing job
    """
    job = syllabus_processor.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return ProcessingJobResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        subjects_processed=job.subjects_processed,
        total_subjects=job.total_subjects,
        started_at=job.started_at,
        completed_at=job.completed_at
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Visualization
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/graph/data", summary="Get full knowledge graph for visualization")
async def get_graph_data(
    semester: Optional[int] = Query(None, ge=1, le=8),
    branch: Optional[str] = Query(None),
    regulation: Optional[str] = Query(None),
):
    """Return all nodes and edges for the interactive graph visualization"""
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")

    graph = neo4j_service.get_full_graph(
        semester=semester, branch=branch, regulation=regulation
    )
    return graph


# ═══════════════════════════════════════════════════════════════════════════════
# Subject Management
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/subjects", summary="List all subjects")
async def list_subjects(
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester"),
    branch: Optional[str] = Query(None, description="Filter by branch"),
    regulation: Optional[str] = Query(None, description="Filter by regulation (2019, 2024, etc.)")
):
    """
    Get all subjects from the knowledge graph
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    subjects = neo4j_service.get_all_subjects(semester=semester, branch=branch, regulation=regulation)
    
    return {
        "subjects": subjects,
        "total": len(subjects),
        "filters": {"semester": semester, "branch": branch, "regulation": regulation}
    }


@router.get("/subjects/{subject_code}", summary="Get subject details")
async def get_subject(subject_code: str, regulation: str = "2019"):
    """
    Get detailed information about a subject including modules and topics
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    subject = neo4j_service.get_subject(subject_code, regulation)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Get modules with topics (Neo4j stores them as 'concepts', frontend expects 'topics')
    modules = neo4j_service.get_modules(subject_code, regulation)
    for m in modules:
        if "concepts" in m and "topics" not in m:
            m["topics"] = m.pop("concepts")
    subject["modules"] = modules
    
    return subject


@router.post("/subjects", summary="Add subject manually")
async def create_subject(subject: SubjectCreate):
    """
    Manually add a subject to the knowledge graph
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    result = syllabus_processor.add_subject_manual(
        subject_data=subject.model_dump(),
        supabase_client=supabase_admin_client
    )
    
    if result.get("errors"):
        raise HTTPException(status_code=500, detail=result["errors"][0])
    
    return {
        "message": "Subject created successfully",
        "subject_code": subject.code,
        "result": result
    }


@router.delete("/subjects/{subject_code}", summary="Delete a subject")
async def delete_subject(subject_code: str):
    """
    Delete a subject from knowledge graph, embeddings, and syllabus database
    """
    result = syllabus_processor.delete_subject(
        subject_code=subject_code,
        supabase_client=supabase_admin_client
    )
    
    if not result["knowledge_graph"] and not result.get("database_deleted"):
        raise HTTPException(status_code=404, detail="Subject not found")
    
    return {
        "message": "Subject deleted successfully",
        "subject_code": subject_code,
        "embeddings_deleted": result["embeddings_deleted"],
        "database_deleted": result.get("database_deleted", False),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Module & Topic Management
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/subjects/{subject_code}/modules", summary="Get modules for a subject")
async def get_subject_modules(subject_code: str, regulation: str = "2019"):
    """
    Get all modules for a specific subject
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    modules = neo4j_service.get_modules(subject_code, regulation)
    for m in modules:
        if "concepts" in m and "topics" not in m:
            m["topics"] = m.pop("concepts")
    return {
        "subject_code": subject_code,
        "modules": modules,
        "total": len(modules)
    }


@router.post("/modules", summary="Add a module")
async def create_module(module: ModuleCreate):
    """
    Add a module to an existing subject
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    result = neo4j_service.create_module(
        module_data=module.model_dump(),
        subject_code=module.subject_code
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create module")
    
    return {
        "message": "Module created successfully",
        "module": result
    }


@router.post("/topics", summary="Add a topic")
async def create_topic(topic: TopicCreate):
    """
    Add a topic to an existing module
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    result = neo4j_service.create_topic(
        topic_data=topic.model_dump(),
        module_id=topic.module_id
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create topic")
    
    # Also create embedding
    try:
        # Get module and subject info for embedding
        # For now, use basic info
        if embedding_service.is_ready():
            content = f"Topic: {topic.name}\nDescription: {topic.description or ''}\nKeywords: {', '.join(topic.keywords)}"
            embedding = embedding_service.generate_embedding(content)
            
            supabase_admin_client.table("syllabus_embeddings").insert({
                "content": content,
                "embedding": embedding,
                "topic_name": topic.name,
                "module_id": topic.module_id
            }).execute()
    except Exception as e:
        logger.warning(f"Could not create embedding: {e}")
    
    return {
        "message": "Topic created successfully",
        "topic": result
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Relationships
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/relationships/prerequisite", summary="Create prerequisite relationship")
async def create_prerequisite(from_code: str, to_code: str, reason: str = ""):
    """
    Create a prerequisite relationship between two subjects
    Example: CS201 (Data Structures) is prerequisite for CS301 (Algorithms)
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    success = neo4j_service.create_prerequisite(from_code, to_code, reason)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create relationship")
    
    return {
        "message": "Prerequisite relationship created",
        "from": from_code,
        "to": to_code,
        "relationship": "PREREQUISITE_OF"
    }


@router.get("/subjects/{subject_code}/prerequisites", summary="Get prerequisites")
async def get_prerequisites(subject_code: str):
    """
    Get prerequisite subjects for a given subject
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    prereqs = neo4j_service.get_prerequisites(subject_code)
    
    return {
        "subject_code": subject_code,
        "prerequisites": prereqs,
        "total": len(prereqs)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Search & RAG
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/search", response_model=SearchResponse, summary="Search syllabus")
async def search_syllabus(query: SearchQuery):
    """
    Search the syllabus using vector similarity
    """
    import time
    start_time = time.time()
    
    if not embedding_service.is_ready():
        raise HTTPException(status_code=503, detail="Embedding service not ready")
    
    results = embedding_service.search_similar(
        supabase_client=supabase_admin_client,
        query=query.query,
        limit=query.limit,
        semester=query.semester,
        branch=query.branch,
        subject_code=query.subject_code
    )
    
    search_results = []
    for r in results:
        search_results.append(SearchResult(
            content=r.get("content", ""),
            subject_code=r.get("subject_code", ""),
            subject_name=r.get("subject_name", ""),
            module_name=r.get("module_name"),
            topic_name=r.get("topic_name"),
            similarity_score=r.get("similarity", 0.0),
            metadata={}
        ))
    
    return SearchResponse(
        query=query.query,
        results=search_results,
        total_results=len(search_results),
        search_time_ms=(time.time() - start_time) * 1000
    )


@router.get("/search/topics", summary="Search topics in knowledge graph")
async def search_topics(q: str, limit: int = 10):
    """
    Search topics by name or keywords in the knowledge graph
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    topics = neo4j_service.search_topics(q, limit)
    
    return {
        "query": q,
        "results": topics,
        "total": len(topics)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Data Management
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/neo4j/setup", summary="Setup Neo4j constraints")
async def setup_neo4j():
    """
    Setup Neo4j database constraints and indexes
    """
    if not neo4j_service.is_connected():
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    
    try:
        neo4j_service.setup_constraints()
        return {"message": "Neo4j constraints and indexes created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/data/clear", summary="Clear all data (DANGER!)")
async def clear_all_data(confirm: bool = Query(False, description="Confirm deletion")):
    """
    Clear all data from knowledge graph and embeddings
    
    ⚠️ WARNING: This action is irreversible!
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Please confirm deletion by setting confirm=true"
        )
    
    results = {
        "knowledge_graph": False,
        "embeddings": False
    }
    
    # Clear Neo4j
    if neo4j_service.is_connected():
        results["knowledge_graph"] = neo4j_service.clear_all_data()
    
    # Clear embeddings (would need proper implementation)
    # For safety, not implementing full clear here
    
    return {
        "message": "Data cleared",
        "results": results
    }


# ═══════════════════════════════════════════════════════════════════════════════
# File Management
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
                semester = int(parts[1].replace("S", "")) if len(parts) > 1 else 0
                
                files.append({
                    "filename": filename,
                    "branch": branch,
                    "semester": semester,
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
