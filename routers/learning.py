"""
Learning Router
Handles quiz and match-pair generation using LLM with DB caching
via the generated_content table (content_type = 'quiz' / 'qa').

Follows the same caching pattern as the flashcards router:
  1. Check DB for existing content matching user + topic (fuzzy).
  2. If found → return cached result.
  3. Else → generate via LLM → save to DB → return fresh result.
  4. `force_regenerate` creates a new separate entry (never overwrites).
"""
import json
import logging
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user, AuthenticatedUser
from schemas.learning import (
    QuizRequest,
    QuizResponse,
    MatchRequest,
    MatchResponse,
    LearningSetSummary,
)
from schemas.user import MessageResponse
from services.chat_service import chat_service
from utils.supabase_client import supabase_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/learning",
    tags=["Learning"]
)

# ─── Content-type constants ───────────────────────────────────────────────────
# The generated_content table CHECK constraint allows:
#   'qa', 'flashcard', 'summary', 'quiz', 'mind_map'
# We use 'quiz' for quizzes and 'qa' for match pairs.
QUIZ_TYPE = "quiz"
MATCH_TYPE = "qa"        # reuse the existing allowed value

# ─── System Prompts ──────────────────────────────────────────────────────────

QUIZ_SYSTEM_PROMPT = """You are a study assistant that generates multiple-choice quiz questions for students.

When given a topic, create quiz questions with 4 answer options each. One option must be correct.

IMPORTANT: You MUST respond with ONLY valid JSON, no extra text. Use this exact format:
{
  "questions": [
    {
      "question": "Question text here?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correctAnswer": 0,
      "explanation": "Brief explanation of why this is correct."
    }
  ]
}

Rules:
- correctAnswer is the 0-based index (0, 1, 2, or 3)
- Always provide exactly 4 options per question
- Make incorrect options plausible (no obviously wrong answers)
- Keep explanations concise (1-2 sentences)
- Cover different aspects of the topic
- Do NOT wrap the JSON in markdown code blocks
"""

MATCH_SYSTEM_PROMPT = """You are a study assistant that generates term-definition matching pairs for students.

When given a topic, create pairs where each has a short "term" and its matching "definition".
These are used in a matching exercise where students connect terms to definitions.

IMPORTANT: You MUST respond with ONLY valid JSON, no extra text. Use this exact format:
{
  "pairs": [
    {"term": "Term or concept", "definition": "Matching definition or explanation"},
    {"term": "Term or concept", "definition": "Matching definition or explanation"}
  ]
}

Rules:
- Keep terms short (1-4 words)
- Keep definitions concise but clear (1-2 sentences max)
- Each pair must be clearly distinct from others
- Cover different aspects of the topic
- Do NOT wrap the JSON in markdown code blocks
"""


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — caching, DB, parsing
# ═══════════════════════════════════════════════════════════════════════════════

def _find_cached(user_id: str, topic: str, content_type: str):
    """
    Fuzzy-match an existing row in generated_content for this
    user + topic + content_type.
      1. Exact case-insensitive match.
      2. Partial / contains match.
    """
    try:
        # Exact match
        response = (
            supabase_admin_client
            .table("generated_content")
            .select("*")
            .eq("user_id", user_id)
            .eq("content_type", content_type)
            .ilike("title", topic)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]

        # Fuzzy / contains match
        response = (
            supabase_admin_client
            .table("generated_content")
            .select("*")
            .eq("user_id", user_id)
            .eq("content_type", content_type)
            .ilike("title", f"%{topic}%")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.warning(f"Cache lookup failed (non-fatal): {e}")
    return None


def _search_by_topic(user_id: str, topic: str, content_type: str, limit: int = 10) -> list[dict]:
    """Return all rows matching user + topic + content_type (partial ilike)."""
    try:
        response = (
            supabase_admin_client
            .table("generated_content")
            .select("id, title, content, difficulty, created_at")
            .eq("user_id", user_id)
            .eq("content_type", content_type)
            .ilike("title", f"%{topic}%")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as e:
        logger.warning(f"Topic search failed: {e}")
        return []


def _save_to_db(user_id: str, topic: str, content: dict, content_type: str, difficulty: str | None = None) -> dict:
    """Insert a generated quiz / match set into generated_content."""
    row = {
        "user_id": user_id,
        "content_type": content_type,
        "title": topic,
        "content": content,
    }
    if difficulty:
        row["difficulty"] = difficulty
    response = (
        supabase_admin_client
        .table("generated_content")
        .insert(row)
        .execute()
    )
    if not response.data:
        raise RuntimeError("Insert into generated_content returned no data")
    return response.data[0]


def _parse_json_response(raw: str) -> dict:
    """
    Extract a JSON object from the LLM's raw text.
    Strips markdown fences and surrounding prose.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM did not return valid JSON"
        )
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw text: {raw[:500]}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse JSON from LLM response"
        )


def _validate_quiz(data: dict) -> list[dict]:
    """Validate and normalise quiz questions from parsed JSON."""
    questions = data.get("questions", data if isinstance(data, list) else [])
    if isinstance(data, list):
        questions = data

    validated = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        if "question" not in q or "options" not in q:
            continue
        opts = q["options"]
        if not isinstance(opts, list) or len(opts) < 2:
            continue
        correct = q.get("correctAnswer", q.get("correct_answer", q.get("answer", 0)))
        if isinstance(correct, str):
            # Handle letter answers like "A", "B"
            correct = ord(correct.upper()) - ord("A") if correct.isalpha() else 0
        correct = int(correct) if correct is not None else 0
        correct = max(0, min(correct, len(opts) - 1))

        validated.append({
            "question": str(q["question"]),
            "options": [str(o) for o in opts[:4]],
            "correctAnswer": correct,
            "explanation": str(q.get("explanation", "")),
        })

    if not validated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM returned no valid quiz questions"
        )
    return validated


def _validate_match(data: dict) -> list[dict]:
    """Validate and normalise match pairs from parsed JSON."""
    pairs = data.get("pairs", data if isinstance(data, list) else [])
    if isinstance(data, list):
        pairs = data

    validated = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        if "term" in p and "definition" in p:
            validated.append({
                "term": str(p["term"]),
                "definition": str(p["definition"]),
            })

    if not validated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM returned no valid match pairs"
        )
    return validated


def _content_to_dict(content) -> dict:
    """Safely parse the content field (may be dict or JSON string)."""
    if isinstance(content, str):
        return json.loads(content)
    return content or {}


# ═══════════════════════════════════════════════════════════════════════════════
# QUIZ ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/quiz/generate", response_model=QuizResponse)
async def generate_quiz(
    request: QuizRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generate a multiple-choice quiz for a given topic using AI.

    **Cache behaviour** (identical to flashcards):
    - Checks the DB for an existing quiz matching the topic (fuzzy).
    - If found → returns it with `cached: true`.
    - Use `force_regenerate: true` to generate a **new** quiz (saved separately).

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        # 1. Check cache
        if not request.force_regenerate:
            cached = _find_cached(current_user.user_id, request.topic, QUIZ_TYPE)
            if cached:
                content = _content_to_dict(cached["content"])
                return QuizResponse(
                    id=cached["id"],
                    topic=cached["title"],
                    difficulty=cached.get("difficulty", "medium"),
                    questions=content.get("questions", []),
                    cached=True,
                    created_at=cached.get("created_at"),
                )

        # 2. Generate via LLM
        difficulty_hint = {
            "easy": "Make them straightforward and suitable for beginners.",
            "medium": "Make them moderately challenging for intermediate students.",
            "hard": "Make them challenging, requiring deep understanding of the topic.",
        }
        messages = [
            {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Generate exactly {request.count} multiple-choice questions about: {request.topic}\n"
                    f"Difficulty: {request.difficulty}. {difficulty_hint.get(request.difficulty, '')}"
                ),
            },
        ]

        raw = await chat_service.generate_response(messages, stream=False)
        data = _parse_json_response(raw)
        questions = _validate_quiz(data)

        # 3. Save to DB
        saved = _save_to_db(
            user_id=current_user.user_id,
            topic=request.topic,
            content={"questions": questions},
            content_type=QUIZ_TYPE,
            difficulty=request.difficulty,
        )

        return QuizResponse(
            id=saved["id"],
            topic=request.topic,
            difficulty=request.difficulty,
            questions=questions,
            cached=False,
            created_at=saved.get("created_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quiz: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MATCH PAIR ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/match/generate", response_model=MatchResponse)
async def generate_match_pairs(
    request: MatchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generate term-definition match pairs for a given topic using AI.

    **Cache behaviour** (identical to flashcards):
    - Checks the DB for existing match pairs matching the topic (fuzzy).
    - If found → returns with `cached: true`.
    - Use `force_regenerate: true` to generate a **new** set (saved separately).

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        # 1. Check cache
        if not request.force_regenerate:
            cached = _find_cached(current_user.user_id, request.topic, MATCH_TYPE)
            if cached:
                content = _content_to_dict(cached["content"])
                return MatchResponse(
                    id=cached["id"],
                    topic=cached["title"],
                    pairs=content.get("pairs", []),
                    cached=True,
                    created_at=cached.get("created_at"),
                )

        # 2. Generate via LLM
        messages = [
            {"role": "system", "content": MATCH_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Generate exactly {request.count} term-definition matching pairs about: {request.topic}"
            },
        ]

        raw = await chat_service.generate_response(messages, stream=False)
        data = _parse_json_response(raw)
        pairs = _validate_match(data)

        # 3. Save to DB
        saved = _save_to_db(
            user_id=current_user.user_id,
            topic=request.topic,
            content={"pairs": pairs},
            content_type=MATCH_TYPE,
        )

        return MatchResponse(
            id=saved["id"],
            topic=request.topic,
            pairs=pairs,
            cached=False,
            created_at=saved.get("created_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Match pair generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate match pairs: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED CRUD ENDPOINTS (list / get / delete / search)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/search", response_model=List[LearningSetSummary])
async def search_learning_sets(
    topic: str = Query(..., min_length=1, description="Topic to search (partial match)"),
    type: str = Query(default="all", description="Filter by type: quiz, match, or all"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Search saved quizzes and match sets by topic name (partial, case-insensitive).

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        results: list[LearningSetSummary] = []

        types_to_search = []
        if type in ("quiz", "all"):
            types_to_search.append(QUIZ_TYPE)
        if type in ("match", "all"):
            types_to_search.append(MATCH_TYPE)

        for ct in types_to_search:
            rows = _search_by_topic(current_user.user_id, topic, ct, limit)
            for row in rows:
                content = _content_to_dict(row.get("content", {}))
                ct_label = "quiz" if ct == QUIZ_TYPE else "match"
                item_key = "questions" if ct == QUIZ_TYPE else "pairs"
                results.append(LearningSetSummary(
                    id=row["id"],
                    topic=row["title"] or "Untitled",
                    type=ct_label,
                    item_count=len(content.get(item_key, [])),
                    difficulty=row.get("difficulty"),
                    created_at=row["created_at"],
                ))

        # Sort by newest first
        results.sort(key=lambda x: x.created_at or "", reverse=True)
        return results[:limit]

    except Exception as e:
        logger.error(f"Learning search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search learning sets: {str(e)}"
        )


@router.get("", response_model=List[LearningSetSummary])
async def list_learning_sets(
    type: str = Query(default="all", description="Filter by type: quiz, match, or all"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    List all saved quizzes and match sets for the current user.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        results: list[LearningSetSummary] = []

        types_to_query = []
        if type in ("quiz", "all"):
            types_to_query.append(QUIZ_TYPE)
        if type in ("match", "all"):
            types_to_query.append(MATCH_TYPE)

        for ct in types_to_query:
            response = (
                supabase_admin_client
                .table("generated_content")
                .select("id, title, content, difficulty, created_at")
                .eq("user_id", current_user.user_id)
                .eq("content_type", ct)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            for row in response.data or []:
                content = _content_to_dict(row.get("content", {}))
                ct_label = "quiz" if ct == QUIZ_TYPE else "match"
                item_key = "questions" if ct == QUIZ_TYPE else "pairs"
                results.append(LearningSetSummary(
                    id=row["id"],
                    topic=row["title"] or "Untitled",
                    type=ct_label,
                    item_count=len(content.get(item_key, [])),
                    difficulty=row.get("difficulty"),
                    created_at=row["created_at"],
                ))

        results.sort(key=lambda x: x.created_at or "", reverse=True)
        return results

    except Exception as e:
        logger.error(f"Failed to list learning sets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list learning sets: {str(e)}"
        )


@router.get("/{item_id}")
async def get_learning_set(
    item_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieve a specific saved quiz or match set by ID.
    Returns either a QuizResponse or MatchResponse depending on the content type.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        response = (
            supabase_admin_client
            .table("generated_content")
            .select("*")
            .eq("id", str(item_id))
            .eq("user_id", current_user.user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learning set not found"
            )

        row = response.data[0]
        content = _content_to_dict(row.get("content", {}))
        ct = row["content_type"]

        if ct == QUIZ_TYPE:
            return QuizResponse(
                id=row["id"],
                topic=row["title"] or "Untitled",
                difficulty=row.get("difficulty", "medium"),
                questions=content.get("questions", []),
                cached=True,
                created_at=row.get("created_at"),
            )
        elif ct == MATCH_TYPE:
            return MatchResponse(
                id=row["id"],
                topic=row["title"] or "Untitled",
                pairs=content.get("pairs", []),
                cached=True,
                created_at=row.get("created_at"),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item is not a quiz or match set (type: {ct})"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get learning set: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get learning set: {str(e)}"
        )


@router.delete("/{item_id}", response_model=MessageResponse)
async def delete_learning_set(
    item_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Delete a saved quiz or match set.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        # Only allow deleting quiz or match (qa) types via this router
        response = (
            supabase_admin_client
            .table("generated_content")
            .select("id, content_type")
            .eq("id", str(item_id))
            .eq("user_id", current_user.user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learning set not found"
            )

        ct = response.data[0]["content_type"]
        if ct not in (QUIZ_TYPE, MATCH_TYPE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This item is not a quiz or match set"
            )

        supabase_admin_client.table("generated_content").delete().eq(
            "id", str(item_id)
        ).eq("user_id", current_user.user_id).execute()

        label = "Quiz" if ct == QUIZ_TYPE else "Match set"
        return MessageResponse(message=f"{label} deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete learning set: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete learning set: {str(e)}"
        )
