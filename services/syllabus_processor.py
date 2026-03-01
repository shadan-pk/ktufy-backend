"""
Syllabus Processor Service
Main orchestrator for PDF → Knowledge Graph + RAG pipeline
"""
import os
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from services.pdf_processor import pdf_processor
from services.llm_extractor import llm_extractor
from services.neo4j_service import neo4j_service
from services.embedding_service import embedding_service
from services.syllabus_db_service import syllabus_db_service

logger = logging.getLogger(__name__)


class ProcessingJob:
    """Represents a syllabus processing job"""
    
    def __init__(self, job_id: str, filename: str, semester: int, branch: str):
        self.job_id = job_id
        self.filename = filename
        self.semester = semester
        self.branch = branch
        self.status = "pending"
        self.progress = 0
        self.message = "Job created"
        self.subjects_processed = 0
        self.total_subjects = 0
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
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "subjects_processed": self.subjects_processed,
            "total_subjects": self.total_subjects,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }


class SyllabusProcessor:
    """
    Main orchestrator for processing KTU syllabus PDFs
    Coordinates: PDF extraction → LLM parsing → Neo4j KG → pgvector embeddings
    """
    
    def __init__(self):
        self.jobs: Dict[str, ProcessingJob] = {}
        self.upload_dir = os.getenv("UPLOAD_DIR", "uploads/syllabus")
        os.makedirs(self.upload_dir, exist_ok=True)
    
    def get_status(self) -> dict:
        """Get overall system status"""
        return {
            "pdf_processor": pdf_processor.pdfplumber is not None,
            "llm_extractor": llm_extractor.groq_client is not None or llm_extractor.openai_client is not None,
            "neo4j": neo4j_service.is_connected(),
            "embedding_model": embedding_service.is_ready(),
            "active_jobs": len([j for j in self.jobs.values() if j.status == "processing"])
        }
    
    def create_job(self, filename: str, semester: int, branch: str) -> ProcessingJob:
        """Create a new processing job"""
        job_id = str(uuid.uuid4())
        job = ProcessingJob(job_id, filename, semester, branch)
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
        job: Optional[ProcessingJob] = None,
        supabase_client=None,
        regulation: str = "2019"
    ) -> dict:
        """
        Process a syllabus PDF end-to-end
        
        Args:
            pdf_path: Path to the PDF file
            semester: Semester number
            branch: Branch code
            job: Optional job to track progress
            supabase_client: Supabase client for embeddings
            regulation: KTU regulation year (2019, 2024, etc.)
            
        Returns:
            Processing results
        """
        result = {
            "success": False,
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
                job.progress = 20
                job.message = "PDF text extracted. Analyzing with AI..."
            
            # ═══════════════════════════════════════════════════════════════
            # Step 2: Extract structured data using LLM
            # ═══════════════════════════════════════════════════════════════
            logger.info("Step 2: Extracting structured data with LLM")
            
            structured_data = llm_extractor.extract_syllabus_structure(
                raw_text=raw_text,
                semester=semester,
                branch=branch
            )
            
            subjects_count = len(structured_data.get("subjects", []))
            result["llm_extraction"] = {
                "subjects_found": subjects_count,
                "status": "success"
            }
            
            # Add regulation to structured data
            structured_data["regulation"] = regulation
            for subject in structured_data.get("subjects", []):
                subject["regulation"] = regulation
            
            if job:
                job.total_subjects = subjects_count
                job.progress = 45
                job.message = f"Found {subjects_count} subjects. Storing to database..."
            
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
            
            if job:
                job.progress = 50
                job.message = f"Stored to DB. Building knowledge graph..."
            
            # ═══════════════════════════════════════════════════════════════
            # Step 3: Load into Neo4j Knowledge Graph
            # ═══════════════════════════════════════════════════════════════
            logger.info("Step 3: Loading data into Neo4j Knowledge Graph")
            
            if neo4j_service.is_connected():
                kg_stats = neo4j_service.load_syllabus_data(structured_data)
                result["knowledge_graph"] = {
                    **kg_stats,
                    "status": "success"
                }
                
                if job:
                    job.subjects_processed = kg_stats["subjects_created"]
                    job.progress = 75
                    job.message = "Knowledge graph updated. Generating embeddings..."
            else:
                result["knowledge_graph"] = {"status": "skipped", "reason": "Neo4j not connected"}
                result["errors"].append("Neo4j not connected - knowledge graph not updated")
            
            # ═══════════════════════════════════════════════════════════════
            # Step 4: Generate and store embeddings
            # ═══════════════════════════════════════════════════════════════
            logger.info("Step 4: Generating embeddings for RAG")
            
            if supabase_client and embedding_service.is_ready():
                emb_stats = embedding_service.store_syllabus_embeddings(
                    supabase_client=supabase_client,
                    syllabus_data=structured_data
                )
                result["embeddings"] = {
                    **emb_stats,
                    "status": "success"
                }
                
                if job:
                    job.progress = 95
                    job.message = "Embeddings generated. Finalizing..."
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
            result["structured_data"] = structured_data
            
            if job:
                job.status = "completed"
                job.progress = 100
                job.message = "Processing completed successfully!"
                job.completed_at = datetime.utcnow()
                job.result = result
            
            logger.info("Syllabus processing completed successfully")
            
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
    
    def process_pdf_sync(
        self,
        pdf_path: str,
        semester: int,
        branch: str,
        supabase_client=None
    ) -> dict:
        """
        Synchronous version for simple use cases
        """
        import asyncio
        return asyncio.run(self.process_pdf(pdf_path, semester, branch, None, supabase_client))
    
    # ═══════════════════════════════════════════════════════════════════════
    # Manual Operations
    # ═══════════════════════════════════════════════════════════════════════
    
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
            # Add to Neo4j
            if neo4j_service.is_connected():
                neo4j_service.create_subject(subject_data)
                
                for module in subject_data.get("modules", []):
                    neo4j_service.create_module(module, subject_data["code"])
                    module_id = f"{subject_data['code']}_M{module['number']}"
                    
                    for topic in module.get("topics", []):
                        neo4j_service.create_topic(topic, module_id)
                
                result["knowledge_graph"] = {"status": "success"}
            
            # Add embeddings
            if supabase_client and embedding_service.is_ready():
                data = {
                    "semester": subject_data.get("semester", 0),
                    "branch": subject_data.get("branch", ""),
                    "subjects": [subject_data]
                }
                emb_result = embedding_service.store_syllabus_embeddings(supabase_client, data)
                result["embeddings"] = emb_result
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def delete_subject(
        self,
        subject_code: str,
        supabase_client=None
    ) -> dict:
        """
        Delete a subject from both KG and embeddings
        
        Args:
            subject_code: Subject code to delete
            supabase_client: Supabase client
            
        Returns:
            Deletion result
        """
        result = {
            "knowledge_graph": False,
            "embeddings_deleted": 0
        }
        
        # Delete from Neo4j
        if neo4j_service.is_connected():
            result["knowledge_graph"] = neo4j_service.delete_subject(subject_code)
        
        # Delete embeddings
        if supabase_client:
            try:
                deleted = embedding_service.delete_embeddings(
                    supabase_client,
                    subject_code=subject_code
                )
                result["embeddings_deleted"] = deleted
            except Exception as e:
                logger.error(f"Error deleting embeddings: {e}")
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_full_statistics(self, supabase_client=None) -> dict:
        """Get complete system statistics"""
        stats = {
            "system_status": self.get_status(),
            "knowledge_graph": neo4j_service.get_statistics(),
            "embeddings": None,
            "processing_jobs": {
                "total": len(self.jobs),
                "completed": len([j for j in self.jobs.values() if j.status == "completed"]),
                "failed": len([j for j in self.jobs.values() if j.status == "failed"]),
                "processing": len([j for j in self.jobs.values() if j.status == "processing"])
            }
        }
        
        if supabase_client:
            stats["embeddings"] = embedding_service.get_statistics(supabase_client)
        
        return stats


# Global instance
syllabus_processor = SyllabusProcessor()
