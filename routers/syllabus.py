"""
Syllabus Router
Browse subjects, modules, and topics.
Primary source: Supabase (syllabus_subjects/modules/topics tables)
Fallback: Neo4j Knowledge Graph (for legacy data)
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user, AuthenticatedUser
from schemas.syllabus import BranchItem, SubjectListItem, SubjectDetail, ModuleItem
from services.syllabus_db_service import syllabus_db_service
from utils.supabase_client import supabase_client

# Neo4j fallback (only used if Supabase tables are empty)
from services.neo4j_service_v2 import neo4j_service

logger = logging.getLogger(__name__)

# Well-known KTU branch names — extend as needed
BRANCH_NAMES = {
    "CSE": "Computer Science & Engineering",
    "ECE": "Electronics & Communication Engineering",
    "EEE": "Electrical & Electronics Engineering",
    "ME": "Mechanical Engineering",
    "CE": "Civil Engineering",
    "IT": "Information Technology",
    "AEI": "Applied Electronics & Instrumentation",
    "BT": "Biotechnology",
    "CHE": "Chemical Engineering",
    "PE": "Production Engineering",
}

router = APIRouter(
    prefix="/api/v1/syllabus",
    tags=["Syllabus"]
)


def _get_neo4j():
    """Return the Neo4j service if connected."""
    if neo4j_service.is_connected():
        return neo4j_service, "v2"
    return None, None


# ─── GET /branches ────────────────────────────────────────────────────────────

@router.get("/branches", response_model=List[BranchItem])
async def get_branches(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Return all available branches (departments) that have subjects.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        # ── Primary: Supabase ──
        branches_db = syllabus_db_service.get_branches(supabase_client)
        if branches_db:
            return [
                BranchItem(
                    code=b["code"],
                    name=BRANCH_NAMES.get(b["code"], b["code"]),
                    subject_count=b["count"],
                )
                for b in branches_db
            ]
    except Exception as e:
        logger.warning(f"Supabase branch query failed, falling back to Neo4j: {e}")

    # ── Fallback: Neo4j ──
    svc, _ = _get_neo4j()
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No data source available (Supabase tables empty and Neo4j not connected)"
        )

    try:
        with svc.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Subject)
                WHERE s.branch IS NOT NULL
                RETURN s.branch AS code, count(s) AS cnt
                ORDER BY s.branch
                """
            )
            branches = []
            for record in result:
                code = record["code"]
                branches.append(BranchItem(
                    code=code,
                    name=BRANCH_NAMES.get(code, code),
                    subject_count=record["cnt"],
                ))
            return branches

    except Exception as e:
        logger.error(f"Failed to fetch branches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch branches: {str(e)}"
        )


# ─── GET /subjects ────────────────────────────────────────────────────────────

@router.get("/subjects", response_model=List[SubjectListItem])
async def get_subjects(
    branch: Optional[str] = Query(None, description="Branch code (e.g. CSE)"),
    semester: Optional[str] = Query(None, description="Semester (e.g. S3 or 3)"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    List subjects, optionally filtered by branch and/or semester.

    **Requires authentication**: Bearer token in Authorization header
    """
    # Normalise semester: accept "S3" or "3" → int 3
    sem_int = None
    if semester:
        sem_clean = semester.upper().lstrip("S")
        if sem_clean.isdigit():
            sem_int = int(sem_clean)

    try:
        # ── Primary: Supabase ──
        subjects_db = syllabus_db_service.get_subjects(
            client=supabase_client,
            branch=branch.upper() if branch else None,
            semester=sem_int,
        )
        if subjects_db:
            return [
                SubjectListItem(
                    name=s.get("name", ""),
                    code=s.get("code", ""),
                    credits=s.get("credits"),
                    semester=s.get("semester"),
                    module_count=s.get("module_count", 0),
                    category=s.get("category"),
                )
                for s in subjects_db
            ]
    except Exception as e:
        logger.warning(f"Supabase subjects query failed, falling back to Neo4j: {e}")

    # ── Fallback: Neo4j ──
    svc, version = _get_neo4j()
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No data source available"
        )

    try:
        subjects = svc.get_all_subjects(
            semester=sem_int,
            branch=branch.upper() if branch else None,
        )

        items = []
        for s in subjects:
            items.append(SubjectListItem(
                name=s.get("name", ""),
                code=s.get("code", ""),
                credits=s.get("credits"),
                semester=s.get("semester"),
                module_count=s.get("module_count", 0),
            ))
        return items

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch subjects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subjects: {str(e)}"
        )


# ─── GET /subject/{subjectCode} ──────────────────────────────────────────────

@router.get("/subject/{subject_code}", response_model=SubjectDetail)
async def get_subject_detail(
    subject_code: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Get full detail for a subject: modules, topics, textbooks, course outcomes.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        # ── Primary: Supabase ──
        subject = syllabus_db_service.get_subject_detail(supabase_client, subject_code)
        if subject:
            modules = []
            for m in subject.get("modules", []):
                modules.append(ModuleItem(
                    module_number=m.get("module_number", 0),
                    title=m.get("name", f"Module {m.get('module_number', '?')}"),
                    hours=m.get("hours"),
                    topics=m.get("topics", []),
                ))
            modules.sort(key=lambda x: x.module_number)

            textbooks = subject.get("textbooks", [])
            if isinstance(textbooks, str):
                textbooks = [textbooks]
            course_outcomes = subject.get("course_outcomes", subject.get("objectives", []))
            if isinstance(course_outcomes, str):
                course_outcomes = [course_outcomes]

            return SubjectDetail(
                subject_name=subject.get("name", ""),
                subject_code=subject.get("code", subject_code),
                credits=subject.get("credits"),
                semester=subject.get("semester"),
                branch=subject.get("branch"),
                category=subject.get("category"),
                modules=modules,
                course_outcomes=course_outcomes or [],
                textbooks=textbooks or [],
                references=subject.get("references", []) or [],
            )
    except Exception as e:
        logger.warning(f"Supabase subject detail query failed, falling back to Neo4j: {e}")

    # ── Fallback: Neo4j ──
    svc, version = _get_neo4j()
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No data source available"
        )

    try:
        subject = svc.get_subject(subject_code)
        if not subject:
            subject = svc.get_subject(subject_code.replace(" ", ""))
        if not subject:
            subject = _fuzzy_subject_lookup(svc, subject_code)

        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subject '{subject_code}' not found"
            )

        modules_raw = subject.get("modules", [])
        modules = []
        for m in modules_raw:
            topic_items = m.get("concepts", m.get("topics", []))
            topic_names = []
            for t in topic_items:
                if isinstance(t, dict):
                    topic_names.append(t.get("name", t.get("display_name", str(t))))
                elif isinstance(t, str):
                    topic_names.append(t)

            modules.append(ModuleItem(
                module_number=m.get("number", 0),
                title=m.get("name", m.get("display_name", f"Module {m.get('number', '?')}")),
                hours=m.get("hours") if m.get("hours") else None,
                topics=topic_names,
            ))
        modules.sort(key=lambda x: x.module_number)

        textbooks = subject.get("textbooks", [])
        if isinstance(textbooks, str):
            textbooks = [textbooks]
        course_outcomes = subject.get("course_outcomes", subject.get("objectives", []))
        if isinstance(course_outcomes, str):
            course_outcomes = [course_outcomes]

        return SubjectDetail(
            subject_name=subject.get("name", ""),
            subject_code=subject.get("code", subject_code),
            credits=subject.get("credits"),
            semester=subject.get("semester"),
            branch=subject.get("branch"),
            category=subject.get("category"),
            modules=modules,
            course_outcomes=course_outcomes or [],
            textbooks=textbooks or [],
            references=[],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch subject detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subject detail: {str(e)}"
        )


def _fuzzy_subject_lookup(svc, code_query: str):
    """
    Try to find a subject when the exact code doesn't match.
    Handles cases like "CST201" vs "CST 201", or partial matches.
    """
    try:
        with svc.driver.session() as session:
            # Case-insensitive CONTAINS search on code
            result = session.run(
                """
                MATCH (s:Subject)
                WHERE toLower(replace(s.code, ' ', '')) = toLower(replace($code, ' ', ''))
                OPTIONAL MATCH (s)-[:HAS_MODULE]->(m:Module)
                OPTIONAL MATCH (m)-[:CONTAINS]->(t)
                WITH s, m, collect(DISTINCT t) as topics
                ORDER BY m.number
                WITH s, collect({module: m, concepts: topics, topics: topics}) as modules_data
                RETURN s, modules_data
                LIMIT 1
                """,
                code=code_query
            )
            record = result.single()
            if not record:
                return None

            subject = dict(record["s"])
            subject["modules"] = []
            for md in record["modules_data"]:
                if md["module"]:
                    module = dict(md["module"])
                    # Merge concepts/topics into a single list
                    items = md.get("concepts", md.get("topics", []))
                    module["topics"] = [dict(t) for t in items] if items else []
                    module["concepts"] = module["topics"]
                    subject["modules"].append(module)
            return subject

    except Exception as e:
        logger.warning(f"Fuzzy subject lookup failed: {e}")
        return None
