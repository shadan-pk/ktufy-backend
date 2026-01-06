"""
Admin schemas for KG-RAG management
Pydantic models for admin API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    """Status of PDF processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ═══════════════════════════════════════════════════════════════════════════
# Syllabus Upload & Processing
# ═══════════════════════════════════════════════════════════════════════════

class SyllabusUploadRequest(BaseModel):
    """Request model for syllabus upload"""
    semester: int = Field(..., ge=1, le=8, description="Semester number (1-8)")
    branch: str = Field(..., description="Branch code (CSE, ECE, ME, etc.)")
    regulation: str = Field(default="2019", description="KTU regulation year")
    
    class Config:
        json_schema_extra = {
            "example": {
                "semester": 3,
                "branch": "CSE",
                "regulation": "2019"
            }
        }


class SyllabusUploadResponse(BaseModel):
    """Response after syllabus upload"""
    id: str
    filename: str
    semester: int
    branch: str
    status: ProcessingStatus
    message: str
    created_at: datetime


class ProcessingJobResponse(BaseModel):
    """Response for processing job status"""
    job_id: str
    status: ProcessingStatus
    progress: int = Field(ge=0, le=100)
    message: str
    subjects_processed: int = 0
    total_subjects: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════════
# Subject & Module Schemas
# ═══════════════════════════════════════════════════════════════════════════

class TopicBase(BaseModel):
    """Base topic model"""
    name: str
    description: Optional[str] = None
    keywords: List[str] = []


class TopicResponse(TopicBase):
    """Topic response with ID"""
    id: str
    module_id: str


class ModuleBase(BaseModel):
    """Base module model"""
    number: int
    name: str
    hours: int = 0


class ModuleResponse(ModuleBase):
    """Module response with topics"""
    id: str
    subject_code: str
    topics: List[TopicResponse] = []


class SubjectBase(BaseModel):
    """Base subject model"""
    code: str
    name: str
    credits: int
    category: Optional[str] = None  # PCC, OEC, etc.


class SubjectCreate(SubjectBase):
    """Create subject with modules"""
    semester: int
    branch: str
    regulation: str = Field(default="2019", description="KTU regulation year (2019, 2024, etc.)")
    modules: List[ModuleBase] = []
    textbooks: List[str] = []
    objectives: List[str] = []


class SubjectResponse(SubjectBase):
    """Subject response with full details"""
    id: str
    semester: int
    branch: str
    regulation: str = "2019"
    modules: List[ModuleResponse] = []
    textbooks: List[str] = []
    objectives: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


class SubjectListResponse(BaseModel):
    """List of subjects"""
    subjects: List[SubjectResponse]
    total: int
    semester: Optional[int] = None
    branch: Optional[str] = None
    regulation: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# Knowledge Graph Stats
# ═══════════════════════════════════════════════════════════════════════════

class KnowledgeGraphStats(BaseModel):
    """Statistics about the knowledge graph"""
    total_subjects: int
    total_modules: int
    total_topics: int
    total_relationships: int
    branches: List[str]
    semesters: List[int]
    regulations: List[str] = []
    last_updated: Optional[datetime] = None


class EmbeddingStats(BaseModel):
    """Statistics about vector embeddings"""
    total_embeddings: int
    subjects_covered: int
    topics_covered: int
    last_updated: Optional[datetime] = None


class RAGStats(BaseModel):
    """Combined RAG system statistics"""
    knowledge_graph: KnowledgeGraphStats
    embeddings: EmbeddingStats
    system_status: str


# ═══════════════════════════════════════════════════════════════════════════
# Manual Data Entry
# ═══════════════════════════════════════════════════════════════════════════

class TopicCreate(BaseModel):
    """Create a new topic"""
    name: str
    description: Optional[str] = None
    keywords: List[str] = []
    module_id: str


class ModuleCreate(BaseModel):
    """Create a new module"""
    number: int
    name: str
    hours: int = 0
    subject_code: str
    topics: List[TopicBase] = []


class RelationshipCreate(BaseModel):
    """Create a relationship between entities"""
    from_type: str  # Subject, Module, Topic
    from_id: str
    to_type: str
    to_id: str
    relationship: str  # PREREQUISITE, RELATED_TO, etc.


# ═══════════════════════════════════════════════════════════════════════════
# Search & Query
# ═══════════════════════════════════════════════════════════════════════════

class SearchQuery(BaseModel):
    """Search query for RAG"""
    query: str
    semester: Optional[int] = None
    branch: Optional[str] = None
    subject_code: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    """Single search result"""
    content: str
    subject_code: str
    subject_name: str
    module_name: Optional[str] = None
    topic_name: Optional[str] = None
    similarity_score: float
    metadata: dict = {}


class SearchResponse(BaseModel):
    """Search response with results"""
    query: str
    results: List[SearchResult]
    total_results: int
    search_time_ms: float


# ═══════════════════════════════════════════════════════════════════════════
# Uploaded Files Management
# ═══════════════════════════════════════════════════════════════════════════

class UploadedFileResponse(BaseModel):
    """Response for uploaded file"""
    id: str
    filename: str
    file_type: str
    semester: int
    branch: str
    status: ProcessingStatus
    file_size: int
    uploaded_at: datetime
    processed_at: Optional[datetime] = None


class UploadedFilesListResponse(BaseModel):
    """List of uploaded files"""
    files: List[UploadedFileResponse]
    total: int
