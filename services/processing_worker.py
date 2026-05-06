"""RQ worker entrypoint and job execution for syllabus processing."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from redis import Redis
from rq import Connection, Worker

from services.curriculum_extractor import curriculum_extractor
from services.syllabus_processor_v2 import syllabus_processor, ProcessingJob
from services.processing_jobs import update_processing_job, update_uploaded_file
from utils.supabase_client import supabase_admin_client

logger = logging.getLogger(__name__)

QUEUE_NAME = os.getenv("RQ_QUEUE_NAME", "ktufy")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


def _sync_job(job_id: str, job: ProcessingJob) -> None:
    update_processing_job(
        supabase_admin_client,
        job_id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        subjects_processed=job.subjects_processed,
        total_subjects=job.total_subjects,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
        result=job.result,
    )


def process_curriculum_job(job_id: str, pdf_path: str, branch: str, regulation: str) -> dict:
    """Run curriculum extraction in the background worker."""
    logger.info("[WORKER][CURRICULUM] Starting job %s for %s (%s)", job_id, branch, regulation)

    update_processing_job(
        supabase_admin_client,
        job_id,
        status="processing",
        progress=10,
        message="Extracting curriculum text...",
        started_at=datetime.utcnow(),
    )

    result = {
        "success": False,
        "mappings_extracted": 0,
        "mappings_inserted": 0,
        "errors": [],
    }

    try:
        extraction_result = curriculum_extractor.extract_elective_mappings_from_pdf(
            pdf_path,
            branch,
            regulation,
        )

        mappings = extraction_result.get("mappings", []) if isinstance(extraction_result, dict) else []
        errors = extraction_result.get("errors", []) if isinstance(extraction_result, dict) else []

        update_processing_job(
            supabase_admin_client,
            job_id,
            progress=45,
            message=f"Extracted {len(mappings)} curriculum mappings. Saving to database...",
        )

        insert_stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": []}
        if extraction_result.get("success") and mappings:
            insert_stats = curriculum_extractor.populate_elective_mappings(
                supabase_admin_client,
                mappings,
                branch,
                regulation,
            )

        result = {
            "success": bool(extraction_result.get("success") and mappings),
            "mappings_extracted": len(mappings),
            "mappings_inserted": insert_stats.get("inserted", 0),
            "mappings_updated": insert_stats.get("updated", 0),
            "mappings_skipped": insert_stats.get("skipped", 0),
            "errors": errors + insert_stats.get("errors", []),
        }

        completed_at = datetime.utcnow()
        update_processing_job(
            supabase_admin_client,
            job_id,
            status="completed" if result["success"] else "failed",
            progress=100 if result["success"] else 90,
            message=(
                f"Stored {result['mappings_inserted']} curriculum mappings"
                if result["success"]
                else "Curriculum extraction failed"
            ),
            completed_at=completed_at,
            error="; ".join(result["errors"]) if result["errors"] else None,
            result={"curriculum_extraction": result},
        )

        logger.info(
            "[WORKER][CURRICULUM] Job %s finished: extracted=%s inserted=%s updated=%s skipped=%s",
            job_id,
            result["mappings_extracted"],
            result["mappings_inserted"],
            result.get("mappings_updated", 0),
            result.get("mappings_skipped", 0),
        )
        return result

    except Exception as exc:
        logger.error("[WORKER][CURRICULUM] Job %s failed: %s", job_id, exc, exc_info=True)
        error_str = str(exc)
        update_processing_job(
            supabase_admin_client,
            job_id,
            status="failed",
            progress=100,
            message="Curriculum extraction failed",
            completed_at=datetime.utcnow(),
            error=error_str,
            result={"curriculum_extraction": {"success": False, "errors": [error_str], "mappings_extracted": 0, "mappings_inserted": 0}},
        )
        return {"success": False, "errors": [error_str], "mappings_extracted": 0, "mappings_inserted": 0}
    finally:
        try:
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
        except Exception as cleanup_exc:
            logger.warning("[WORKER][CURRICULUM] Could not clean up %s: %s", pdf_path, cleanup_exc)


def process_syllabus_job(
    job_id: str,
    pdf_path: str,
    semester: int,
    branch: str,
    regulation: str,
    file_id: Optional[str] = None,
) -> dict:
    """Run the syllabus processing pipeline and update Supabase job status."""
    filename = os.path.basename(pdf_path)
    job = ProcessingJob(job_id, filename, semester, branch, regulation)

    if file_id:
        update_uploaded_file(
            supabase_admin_client,
            file_id,
            status="processing",
            processed_at=None,
        )

    job.status = "processing"
    job.started_at = datetime.utcnow()
    job.message = "Processing started"
    _sync_job(job_id, job)

    def update_hook(updated: ProcessingJob) -> None:
        _sync_job(job_id, updated)

    result = asyncio.run(
        syllabus_processor.process_pdf(
            pdf_path=pdf_path,
            semester=semester,
            branch=branch,
            regulation=regulation,
            job=job,
            supabase_client=supabase_admin_client,
            job_update_fn=update_hook,
        )
    )

    if file_id:
        status = "completed" if result.get("success") else "failed"
        error_message = None
        if not result.get("success"):
            error_message = "; ".join(result.get("errors", []))

        update_uploaded_file(
            supabase_admin_client,
            file_id,
            status=status,
            error_message=error_message,
            subjects_count=result.get("llm_extraction", {}).get("subjects_found", 0),
            modules_count=result.get("database_store", {}).get("modules_stored", 0),
            topics_count=result.get("database_store", {}).get("topics_stored", 0),
            processed_at=datetime.utcnow(),
        )

    return result


def main() -> None:
    redis_conn = Redis.from_url(REDIS_URL)
    with Connection(redis_conn):
        worker = Worker([QUEUE_NAME])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
