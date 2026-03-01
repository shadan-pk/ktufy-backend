"""
Syllabus Router
Browse subjects, modules, and topics from the Neo4j Knowledge Graph
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user, AuthenticatedUser
from schemas.syllabus import BranchItem, SubjectListItem, SubjectDetail, ModuleItem
from services.neo4j_service import neo4j_service
from services.neo4j_service_v2 import neo4j_service_v2

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
    """Return the first connected Neo4j service (prefer V2, fall back to V1)."""
    if neo4j_service_v2.is_connected():
        return neo4j_service_v2, "v2"
    if neo4j_service.is_connected():
        return neo4j_service, "v1"
    return None, None


# ─── GET /branches ────────────────────────────────────────────────────────────

@router.get("/branches", response_model=List[BranchItem])
async def get_branches(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Return all available branches (departments) that have subjects in the KG.

    **Requires authentication**: Bearer token in Authorization header
    """
    svc, _ = _get_neo4j()
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge Graph (Neo4j) is not connected"
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
    svc, version = _get_neo4j()
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge Graph (Neo4j) is not connected"
        )

    try:
        # Normalise semester: accept "S3" or "3" → int 3
        sem_int = None
        if semester:
            sem_clean = semester.upper().lstrip("S")
            if sem_clean.isdigit():
                sem_int = int(sem_clean)

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
    svc, version = _get_neo4j()
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge Graph (Neo4j) is not connected"
        )

    try:
        # Try exact code first (e.g. "CST 201")
        subject = svc.get_subject(subject_code)

        # If not found, try without spaces (e.g. "CST201" → search)
        if not subject:
            subject = svc.get_subject(subject_code.replace(" ", ""))

        # If still not found, do a fuzzy lookup
        if not subject:
            subject = _fuzzy_subject_lookup(svc, subject_code)

        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subject '{subject_code}' not found in Knowledge Graph"
            )

        # Fetch modules with topics
        modules_raw = subject.get("modules", [])
        modules = []
        for m in modules_raw:
            # V2 stores topics as "concepts", V1 as "topics"
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

        # Sort modules by number
        modules.sort(key=lambda x: x.module_number)

        # Extract textbooks / course_outcomes (stored as lists on Subject node)
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
