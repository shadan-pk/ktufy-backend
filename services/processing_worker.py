"""RQ worker entrypoint and job execution for syllabus processing."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from redis import Redis
from rq import Connection, Worker

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
