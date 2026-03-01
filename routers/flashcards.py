"""
Flashcards Router
Handles flashcard generation using LLM with DB caching via generated_content table
"""
import json
import logging
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user, AuthenticatedUser
from schemas.flashcard import (
    FlashcardRequest,
    FlashcardResponse,
    FlashcardSetSummary,
)
from schemas.user import MessageResponse
from services.chat_service import chat_service
from utils.supabase_client import supabase_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/flashcards",
    tags=["Flashcards"]
)


FLASHCARD_SYSTEM_PROMPT = """You are a study assistant that generates flashcards for students.

When given a topic, create educational flashcards with a question or key term on the "front" and
the answer or definition on the "back". Each flashcard should be concise but informative.

IMPORTANT: You MUST respond with ONLY valid JSON, no extra text. Use this exact format:
{
  "flashcards": [
    {"front": "Question or term", "back": "Answer or definition"},
    {"front": "Question or term", "back": "Answer or definition"}
  ]
}

Rules:
- Cover different aspects of the topic
- Keep "front" short (a question, term, or concept)
- Keep "back" clear and concise (1-3 sentences max)
- Ensure accuracy of the content
- Do NOT include numbering in the front/back text
- Do NOT wrap the JSON in markdown code blocks
"""


# ─── Helper: look up cached flashcards ────────────────────────────────────────

def _find_cached(user_id: str, topic: str):
    """
    Check the generated_content table for an existing flashcard set
    matching this user + topic (case-insensitive).
    Returns the row dict or None.
    """
    try:
        response = (
            supabase_admin_client
            .table("generated_content")
            .select("*")
            .eq("user_id", user_id)
            .eq("content_type", "flashcard")
            .ilike("title", topic)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.warning(f"Cache lookup failed (non-fatal): {e}")
    return None


def _save_to_db(user_id: str, topic: str, flashcards: list[dict]) -> dict:
    """
    Save a generated flashcard set to the generated_content table.
    Returns the inserted row.
    """
    row = {
        "user_id": user_id,
        "content_type": "flashcard",
        "title": topic,
        "content": {"flashcards": flashcards},
    }
    response = (
        supabase_admin_client
        .table("generated_content")
        .insert(row)
        .execute()
    )
    if not response.data:
        raise RuntimeError("Insert into generated_content returned no data")
    return response.data[0]


# ─── POST /generate ───────────────────────────────────────────────────────────

@router.post("/generate", response_model=FlashcardResponse)
async def generate_flashcards(
    request: FlashcardRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Generate flashcards for a given topic using AI.

    - If flashcards for this topic already exist for the user, returns the cached version.
    - Pass `force_regenerate: true` to bypass the cache and get fresh flashcards.
    - Results are saved to the `generated_content` table for future lookups.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        # 1. Check cache (unless force_regenerate)
        if not request.force_regenerate:
            cached = _find_cached(current_user.user_id, request.topic)
            if cached:
                cards = cached["content"]
                if isinstance(cards, str):
                    cards = json.loads(cards)
                return FlashcardResponse(
                    id=cached["id"],
                    topic=cached["title"],
                    flashcards=cards.get("flashcards", []),
                    cached=True,
                    created_at=cached.get("created_at"),
                )

        # 2. Generate via LLM
        messages = [
            {"role": "system", "content": FLASHCARD_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Generate exactly {request.count} flashcards about: {request.topic}"
            }
        ]

        raw_response = await chat_service.generate_response(messages, stream=False)
        flashcards = _parse_flashcards(raw_response)

        # 3. Save to DB
        saved = _save_to_db(current_user.user_id, request.topic, flashcards)

        return FlashcardResponse(
            id=saved["id"],
            topic=request.topic,
            flashcards=flashcards,
            cached=False,
            created_at=saved.get("created_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Flashcard generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate flashcards: {str(e)}"
        )


# ─── GET / (list saved sets) ─────────────────────────────────────────────────

@router.get("", response_model=List[FlashcardSetSummary])
async def list_flashcard_sets(
    current_user: AuthenticatedUser = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    """
    List all saved flashcard sets for the current user.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        response = (
            supabase_admin_client
            .table("generated_content")
            .select("id, title, content, created_at")
            .eq("user_id", current_user.user_id)
            .eq("content_type", "flashcard")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        results = []
        for row in response.data or []:
            content = row.get("content", {})
            if isinstance(content, str):
                content = json.loads(content)
            card_count = len(content.get("flashcards", []))
            results.append(FlashcardSetSummary(
                id=row["id"],
                topic=row["title"] or "Untitled",
                card_count=card_count,
                created_at=row["created_at"],
            ))
        return results

    except Exception as e:
        logger.error(f"Failed to list flashcard sets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list flashcard sets: {str(e)}"
        )


# ─── GET /{id} (retrieve a single set) ───────────────────────────────────────

@router.get("/{flashcard_id}", response_model=FlashcardResponse)
async def get_flashcard_set(
    flashcard_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieve a specific saved flashcard set by ID.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        response = (
            supabase_admin_client
            .table("generated_content")
            .select("*")
            .eq("id", str(flashcard_id))
            .eq("user_id", current_user.user_id)
            .eq("content_type", "flashcard")
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flashcard set not found"
            )

        row = response.data[0]
        content = row.get("content", {})
        if isinstance(content, str):
            content = json.loads(content)

        return FlashcardResponse(
            id=row["id"],
            topic=row["title"] or "Untitled",
            flashcards=content.get("flashcards", []),
            cached=True,
            created_at=row.get("created_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get flashcard set: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get flashcard set: {str(e)}"
        )


# ─── DELETE /{id} ─────────────────────────────────────────────────────────────

@router.delete("/{flashcard_id}", response_model=MessageResponse)
async def delete_flashcard_set(
    flashcard_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Delete a saved flashcard set.

    **Requires authentication**: Bearer token in Authorization header
    """
    try:
        response = (
            supabase_admin_client
            .table("generated_content")
            .delete()
            .eq("id", str(flashcard_id))
            .eq("user_id", current_user.user_id)
            .eq("content_type", "flashcard")
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flashcard set not found"
            )

        return MessageResponse(message="Flashcard set deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete flashcard set: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete flashcard set: {str(e)}"
        )


# ─── LLM response parser ─────────────────────────────────────────────────────

def _parse_flashcards(raw: str) -> list[dict]:
    """
    Parse the LLM's raw text response into a list of flashcard dicts.
    Handles common LLM quirks (markdown fences, extra text around JSON).
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    # Try to find a JSON object in the text
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM did not return valid JSON for flashcards"
        )

    json_str = text[start:end]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw text: {raw[:500]}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse flashcard JSON from LLM response"
        )

    # Accept {"flashcards": [...]} or a bare list
    if isinstance(data, dict) and "flashcards" in data:
        cards = data["flashcards"]
    elif isinstance(data, list):
        cards = data
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected JSON structure from LLM"
        )

    # Validate each card has front and back
    validated = []
    for card in cards:
        if isinstance(card, dict) and "front" in card and "back" in card:
            validated.append({"front": str(card["front"]), "back": str(card["back"])})

    if not validated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM returned no valid flashcards"
        )

    return validated
