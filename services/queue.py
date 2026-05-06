"""Queue utilities for background processing."""
from __future__ import annotations

import os
from redis import Redis
from rq import Queue

from services.processing_worker import process_curriculum_job


DEFAULT_REDIS_URL = "redis://redis:6379/0"
DEFAULT_QUEUE_NAME = "ktufy"


def get_queue() -> Queue:
    redis_url = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    return Queue(DEFAULT_QUEUE_NAME, connection=Redis.from_url(redis_url))


def enqueue_curriculum_extraction(job_id: str, pdf_path: str, branch: str, regulation: str):
    """Enqueue curriculum extraction on the shared RQ worker queue."""
    queue = get_queue()
    return queue.enqueue(
        process_curriculum_job,
        job_id,
        pdf_path,
        branch,
        regulation,
        job_id=job_id,
        result_ttl=24 * 60 * 60,
        failure_ttl=24 * 60 * 60,
    )


def cancel_all_jobs():
    """Cancel all jobs in the queue."""
    queue = get_queue()
    # Empty the queue
    queue.empty()
    # Cancel all currently executing or queued jobs if possible
    # Note: RQ doesn't easily let you kill currently running jobs on remote workers
    # from the queue object, but emptying handles the pending ones.
    return True
