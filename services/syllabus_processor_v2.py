"""
Syllabus Processor V2 - KG-RAG Corrected Version
Orchestrates the corrected pipeline
"""
import os
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from services.pdf_processor import pdf_processor
from services.llm_extractor_v2 import llm_extractor
from services.neo4j_service_v2 import neo4j_service
from services.embedding_service_v2 import embedding_service
from services.syllabus_db_service import syllabus_db_service

logger = logging.getLogger(__name__)


class ProcessingJob:
    """Represents a syllabus processing job"""
    
    def __init__(self, job_id: str, filename: str, semester: int, branch: str, regulation: str = "2019"):
        self.job_id = job_id
        self.filename = filename
        self.semester = semester
        self.branch = branch
        self.regulation = regulation
        self.status = "pending"
        self.progress = 0
        self.message = "Job created"
        self.subjects_processed = 0
        self.total_subjects = 0
        self.concepts_created = 0
        self.chunks_stored = 0
        self.relationships_created = 0
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "filename": self.filename,
            "semester": self.semester,
            "branch": self.branch,
            "regulation": self.regulation,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "subjects_processed": self.subjects_processed,
            "total_subjects": self.total_subjects,
            "concepts_created": self.concepts_created,
            "chunks_stored": self.chunks_stored,
            "relationships_created": self.relationships_created,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }


class SyllabusProcessorV2:
    """
    KG-RAG Corrected Syllabus Processor
    
    Pipeline:
    1. PDF → Raw Text (pdfplumber)
    2. Raw Text → Structured Data with atomic concepts (LLM V2)
    3. Structured Data → Knowledge Graph (Neo4j V2)
    4. Content Chunks → Vector Embeddings (pgvector V2)
    """
    
    def __init__(self):
        self.jobs: Dict[str, ProcessingJob] = {}
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads/syllabus")
        os.makedirs(self.upload_dir, exist_ok=True)
    
    def get_status(self) -> dict:
        """Get overall system status"""
        llm_ready = (
            getattr(llm_extractor, "groq_client", None) is not None
            or getattr(llm_extractor, "openai_client", None) is not None
        )
        return {
            "pdf_processor": pdf_processor.pdfplumber is not None,
            "llm_extractor": llm_ready,
            "neo4j": neo4j_service.is_connected(),
            "embedding_model": embedding_service.is_ready(),
            "active_jobs": len([j for j in self.jobs.values() if j.status == "processing"]),
            "version": "2.0"
        }
    
    def create_job(self, filename: str, semester: int, branch: str, regulation: str = "2019") -> ProcessingJob:
        """Create a new processing job"""
        job_id = str(uuid.uuid4())
        job = ProcessingJob(job_id, filename, semester, branch, regulation)
        self.jobs[job_id] = job
        return job
    
    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    def get_all_jobs(self) -> list:
        """Get all jobs"""
        return [job.to_dict() for job in self.jobs.values()]
    
    async def process_pdf(
        self,
        pdf_path: str,
        semester: int,
        branch: str,
        regulation: str = "2019",
        job: Optional[ProcessingJob] = None,
        supabase_client=None
    ) -> dict:
        """
        Process a syllabus PDF using the corrected V2 pipeline
        """
        result = {
            "success": False,
            "version": "2.0",
            "pdf_extraction": None,
            "llm_extraction": None,
            "knowledge_graph": None,
            "embeddings": None,
            "errors": []
        }
        
        try:
            if job:
                job.status = "processing"
                job.started_at = datetime.utcnow()
                job.progress = 5
                job.message = "Extracting text from PDF..."
            
            # ═══════════════════════════════════════════════════════════════
            # Step 1: Extract text from PDF
            # ═══════════════════════════════════════════════════════════════
            logger.info(f"Step 1: Extracting text from {pdf_path}")
            
            raw_text = pdf_processor.extract_text(pdf_path)
            pdf_info = pdf_processor.get_pdf_info(pdf_path)
            
            result["pdf_extraction"] = {
                "pages": pdf_info["total_pages"],
                "characters": len(raw_text),
                "status": "success"
            }
            
            if job:
                job.progress = 15
                job.message = "Text extracted. Parsing syllabus structure..."
            
            # ═══════════════════════════════════════════════════════════════
            # Step 2: Extract structured data with V2 extractor
            # ═══════════════════════════════════════════════════════════════
            logger.info("Step 2: Extracting structured data with LLM V2")
            
            structured_data = llm_extractor.extract_syllabus_structure(
                raw_text=raw_text,
                semester=semester,
                branch=branch,
                regulation=regulation
            )
            
            subjects_count = len(structured_data.get("subjects", []))
            concepts_count = len(structured_data.get("concepts", []))
            relationships_count = len(structured_data.get("relationships", []))
            chunks_count = len(structured_data.get("content_chunks", []))
            
            result["llm_extraction"] = {
                "subjects_found": subjects_count,
                "concepts_extracted": concepts_count,
                "relationships_identified": relationships_count,
                "content_chunks_generated": chunks_count,
                "status": "success"
            }
            
            if job:
                job.total_subjects = subjects_count
                job.progress = 35
                job.message = f"Found {subjects_count} subjects, {concepts_count} concepts. Storing to database..."
            
            # ═══════════════════════════════════════════════════════════════
            # Step 2.5: Store structured syllabus to Supabase (for display)
            # ═══════════════════════════════════════════════════════════════
            logger.info("Step 2.5: Storing structured syllabus data to Supabase")
            
            if supabase_client:
                try:
                    from utils.supabase_client import supabase_admin_client
                    db_stats = syllabus_db_service.store_syllabus(
                        admin_client=supabase_admin_client,
                        structured_data=structured_data,
                        semester=semester,
                        branch=branch,
                        regulation=regulation,
                    )
                    result["database_store"] = {**db_stats, "status": "success"}
                    logger.info(f"Stored to DB: {db_stats['subjects_stored']} subjects, {db_stats['modules_stored']} modules, {db_stats['topics_stored']} topics")
                except Exception as db_err:
                    logger.warning(f"Failed to store syllabus to DB (non-fatal): {db_err}")
                    result["database_store"] = {"status": "failed", "error": str(db_err)}
            else:
                result["database_store"] = {"status": "skipped", "reason": "Supabase client not provided"}
            
            if job:
                job.progress = 40
                job.message = f"Stored to DB. Building knowledge graph..."
            
            # ═══════════════════════════════════════════════════════════════
            # Step 3: Load into Neo4j Knowledge Graph (V2)
            # ═══════════════════════════════════════════════════════════════
            logger.info("Step 3: Loading data into Neo4j V2 Knowledge Graph")
            
            if neo4j_service.is_connected():
                # Setup schema first
                neo4j_service.setup_schema()
                
                # Load data
                kg_stats = neo4j_service.load_syllabus_data(structured_data)
                
                result["knowledge_graph"] = {
                    **kg_stats,
                    "status": "success"
                }
                
                if job:
                    job.subjects_processed = kg_stats["subjects_created"]
                    job.concepts_created = kg_stats["concepts_created"]
                    job.relationships_created = kg_stats["relationships_created"]
                    job.progress = 70
                    job.message = f"KG built: {kg_stats['concepts_created']} concepts, {kg_stats['relationships_created']} relationships. Storing embeddings..."
            else:
                result["knowledge_graph"] = {"status": "skipped", "reason": "Neo4j not connected"}
                result["errors"].append("Neo4j not connected")
            
            # ═══════════════════════════════════════════════════════════════
            # Step 4: Store embeddings in pgvector (V2)
            # ═══════════════════════════════════════════════════════════════
            logger.info("Step 4: Storing content chunk embeddings")
            
            if supabase_client and embedding_service.is_ready():
                content_chunks = structured_data.get("content_chunks", [])
                
                emb_stats = embedding_service.store_content_chunks(
                    supabase_client=supabase_client,
                    content_chunks=content_chunks,
                    semester=semester,
                    branch=branch,
                    regulation=regulation
                )
                
                result["embeddings"] = {
                    **emb_stats,
                    "status": "success"
                }
                
                if job:
                    job.chunks_stored = emb_stats["chunks_stored"]
                    job.progress = 95
                    job.message = f"Stored {emb_stats['chunks_stored']} content chunks. Finalizing..."
            else:
                reason = []
                if not supabase_client:
                    reason.append("Supabase client not provided")
                if not embedding_service.is_ready():
                    reason.append("Embedding model not loaded")
                result["embeddings"] = {"status": "skipped", "reason": "; ".join(reason)}
                result["errors"].append(f"Embeddings skipped: {'; '.join(reason)}")
            
            # ═══════════════════════════════════════════════════════════════
            # Complete
            # ═══════════════════════════════════════════════════════════════
            result["success"] = True
            
            if job:
                job.status = "completed"
                job.progress = 100
                job.message = "Processing completed successfully!"
                job.completed_at = datetime.utcnow()
                job.result = result
            
            logger.info("Syllabus processing V2 completed successfully")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing syllabus: {error_msg}")
            result["errors"].append(error_msg)
            
            if job:
                job.status = "failed"
                job.error = error_msg
                job.message = f"Processing failed: {error_msg}"
                job.completed_at = datetime.utcnow()
        
        return result
    
    def get_full_statistics(self, supabase_client) -> dict:
        """Get full statistics from both KG and embeddings"""
        kg_stats = {}
        emb_stats = {}
        
        if neo4j_service.is_connected():
            kg_stats = neo4j_service.get_statistics()
        
        if supabase_client and embedding_service.is_ready():
            emb_stats = embedding_service.get_statistics(supabase_client)
        
        return {
            "knowledge_graph": kg_stats,
            "embeddings": emb_stats,
            "system_status": self.get_status()
        }
    
    def delete_subject(
        self,
        subject_code: str,
        regulation: str = "2019",
        supabase_client=None
    ) -> dict:
        """Delete a subject from KG, embeddings, and syllabus DB"""
        result = {
            "knowledge_graph": False,
            "embeddings_deleted": 0,
            "database_deleted": False,
        }
        
        # Delete from Neo4j
        if neo4j_service.is_connected():
            result["knowledge_graph"] = neo4j_service.delete_subject(subject_code, regulation)
        
        # Delete from pgvector
        if supabase_client:
            result["embeddings_deleted"] = embedding_service.delete_by_subject(
                supabase_client, subject_code
            )
        
        # Delete from syllabus DB tables
        try:
            from utils.supabase_client import supabase_admin_client
            result["database_deleted"] = syllabus_db_service.delete_subject(
                supabase_admin_client, subject_code, regulation
            )
        except Exception as e:
            logger.warning(f"Failed to delete subject from DB: {e}")
        
        return result
    
    def add_subject_manual(
        self,
        subject_data: dict,
        supabase_client=None
    ) -> dict:
        """
        Manually add a subject to the knowledge graph and embeddings
        
        Args:
            subject_data: Subject information with modules and topics
            supabase_client: Supabase client for embeddings
            
        Returns:
            Result statistics
        """
        result = {
            "knowledge_graph": None,
            "embeddings": None,
            "errors": []
        }
        
        try:
            semester = subject_data.get("semester", 0)
            branch = subject_data.get("branch", "")
            regulation = subject_data.get("regulation", "2019")
            
            # Add to Neo4j
            if neo4j_service.is_connected():
                neo4j_service.create_subject(subject_data, semester, branch, regulation)
                
                for module in subject_data.get("modules", []):
                    neo4j_service.create_module(module, subject_data["code"], regulation)
                    module_id = module.get("id", f"{subject_data['code'].lower()}_m{module['number']}")
                    
                    for topic in module.get("topics", []):
                        neo4j_service.create_concept(topic, module_id)
                
                result["knowledge_graph"] = {"status": "success"}
            
            # Add embeddings
            if supabase_client and embedding_service.is_ready():
                content = f"Subject: {subject_data.get('name', '')}\nCode: {subject_data.get('code', '')}"
                for module in subject_data.get("modules", []):
                    for topic in module.get("topics", []):
                        topic_name = topic.get("name", "") if isinstance(topic, dict) else str(topic)
                        content += f"\nTopic: {topic_name}"
                
                embedding = embedding_service.generate_embedding(content)
                supabase_client.table("syllabus_embeddings").upsert({
                    "content": content,
                    "embedding": embedding,
                    "subject_code": subject_data.get("code", ""),
                    "subject_name": subject_data.get("name", ""),
                    "chunk_type": "syllabus_content",
                    "semester": semester,
                    "branch": branch,
                    "regulation": regulation,
                }).execute()
                result["embeddings"] = {"status": "success", "chunks_stored": 1}
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result


# Global instance
syllabus_processor = SyllabusProcessorV2()
