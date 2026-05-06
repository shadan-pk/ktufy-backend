"""
Processing Jobs service
Stores and retrieves job status and uploaded file metadata in Supabase.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _to_iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_iso(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_iso(v) for v in value]
    return value


def create_uploaded_file(
    admin_client,
    *,
    filename: str,
    original_filename: Optional[str],
    file_size: Optional[int],
    semester: int,
    branch: str,
    regulation: str,
) -> Optional[dict]:
    """Insert a row into uploaded_files and return it."""
    row = {
        "filename": filename,
        "original_filename": original_filename,
        "file_type": "pdf",
        "file_size": file_size,
        "semester": semester,
        "branch": branch,
        "regulation": regulation,
        "status": "pending",
    }

    try:
        result = admin_client.table("uploaded_files").insert(row).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        logger.error("Failed to create uploaded_files row: %s", exc)
        return None


def update_uploaded_file(admin_client, file_id: str, **fields) -> bool:
    """Update an uploaded_files row by id."""
    payload = {k: _to_iso(v) for k, v in fields.items() if v is not None}
    if not payload:
        return False

    try:
        admin_client.table("uploaded_files").update(payload).eq("id", file_id).execute()
        return True
    except Exception as exc:
        logger.error("Failed to update uploaded_files %s: %s", file_id, exc)
        return False


def create_processing_job(
    admin_client,
    *,
    file_id: Optional[str],
    status: str = "pending",
    progress: int = 0,
    message: str = "Queued",
) -> Optional[dict]:
    """Insert a row into processing_jobs and return it."""
    row = {
        "file_id": file_id,
        "status": status,
        "progress": progress,
        "message": message,
    }

    try:
        result = admin_client.table("processing_jobs").insert(row).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        logger.error("Failed to create processing_jobs row: %s", exc)
        return None


def update_processing_job(admin_client, job_id: str, **fields) -> bool:
    """Update a processing_jobs row by id."""
    payload = {k: _to_iso(v) for k, v in fields.items() if v is not None}
    if not payload:
        return False

    try:
        admin_client.table("processing_jobs").update(payload).eq("id", job_id).execute()
        return True
    except Exception as exc:
        logger.error("Failed to update processing_jobs %s: %s", job_id, exc)
        return False


def get_processing_job(admin_client, job_id: str) -> Optional[dict]:
    """Fetch a processing_jobs row by id."""
    try:
        result = admin_client.table("processing_jobs").select("*").eq("id", job_id).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        logger.error("Failed to fetch processing_jobs %s: %s", job_id, exc)
        return None


def list_processing_jobs(admin_client, limit: int = 100) -> List[dict]:
    """Fetch recent processing_jobs rows."""
    try:
        result = (
            admin_client.table("processing_jobs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("Failed to list processing_jobs: %s", exc)
        return []


def _attach_file_metadata(admin_client, jobs: List[dict]) -> None:
    file_ids = list({j.get("file_id") for j in jobs if j.get("file_id")})
    if not file_ids:
        return

    try:
        files_result = admin_client.table("uploaded_files").select("*").in_("id", file_ids).execute()
        files = files_result.data or []
        files_by_id = {f["id"]: f for f in files}
        for job in jobs:
            job["_file"] = files_by_id.get(job.get("file_id"))
    except Exception as exc:
        logger.error("Failed to attach uploaded_files metadata: %s", exc)


def format_job_response(job: dict) -> dict:
    """Convert a processing_jobs row into the API response shape."""
    file_row = job.get("_file") or {}
    result = job.get("result") or {}
    kg = result.get("knowledge_graph", {}) if isinstance(result, dict) else {}
    emb = result.get("embeddings", {}) if isinstance(result, dict) else {}

    return {
        "job_id": job.get("id"),
        "status": job.get("status"),
        "progress": job.get("progress") or 0,
        "message": job.get("message") or "",
        "subjects_processed": job.get("subjects_processed") or 0,
        "total_subjects": job.get("total_subjects") or 0,
        "concepts_created": kg.get("concepts_created", 0),
        "chunks_stored": emb.get("chunks_stored", 0),
        "relationships_created": kg.get("relationships_created", 0),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "filename": file_row.get("filename"),
        "branch": file_row.get("branch"),
        "semester": file_row.get("semester"),
        "regulation": file_row.get("regulation"),
    }


def format_jobs_response(admin_client, jobs: List[dict]) -> List[dict]:
    """Attach file metadata and format job responses."""
    _attach_file_metadata(admin_client, jobs)
    return [format_job_response(j) for j in jobs]
