"""
Ticklist Router
Handles AI generation of syllabus topics for subjects with missing data.
"""
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user, AuthenticatedUser
from schemas.syllabus import TicklistRequest
from services.chat_service import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/ticklist",
    tags=["Ticklist"]
)

TICKLIST_SYSTEM_PROMPT = """You are an academic expert specializing in university-level course syllabi.
Your task is to generate a detailed list of core topics for a specific module of a university subject.

When given a subject name and a module number, provide a comprehensive but concise list of topics that would typically be covered in that module.
The topics should be suitable for a student's study checklist.

IMPORTANT: You MUST respond with ONLY a JSON array of strings. Each string should be a topic name.
No extra text, no markdown code blocks, no preamble.

Example Response:
["Topic 1", "Topic 2", "Topic 3"]
"""

@router.post("/generate", response_model=List[str])
async def generate_ticklist(
    request: TicklistRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generate a list of topics for a specific module of a subject using AI.
    This is used as a fallback when the standard syllabus retrieval fails.
    """
    try:
        messages = [
            {"role": "system", "content": TICKLIST_SYSTEM_PROMPT},
            {
                "role": "user", 
                "content": f"Generate a checklist of topics for Module {request.module_number} of the subject '{request.subject_name}' (Subject Code: {request.subject_code})."
            }
        ]

        # Generate response from AI
        raw_response = await chat_service.generate_response(messages, stream=False)
        
        # Parse JSON array
        try:
            # Clean response in case LLM added markdown or extra text
            text = raw_response.strip()
            if text.startswith("```"):
                # Handle ```json or just ```
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    text = "\n".join(lines[1:])
                if text.endswith("```"):
                    text = text[:-3].rstrip()
            
            # Find start and end of array
            start = text.find("[")
            end = text.rfind("]") + 1
            
            if start == -1 or end == 0:
                # If it's not a JSON array, maybe it's a list of strings?
                # Let's try to extract lines if it's not JSON
                lines = [line.strip().lstrip("-*•").strip() for line in raw_response.split('\n') if line.strip()]
                # Filter out obvious non-topics
                lines = [l for l in lines if len(l) > 3 and not l.lower().startswith("here are")]
                if len(lines) >= 2:
                    return lines
                raise ValueError("Response is not a valid JSON array")
                
            topics = json.loads(text[start:end])
            
            if not isinstance(topics, list):
                raise ValueError("Parsed result is not a list")
                
            return [str(t) for t in topics]
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI ticklist response: {e}. Raw: {raw_response}")
            # Fallback: maybe just return lines if it's formatted as a list
            lines = [line.strip().lstrip("-*•").strip() for line in raw_response.split('\n') if line.strip()]
            lines = [l for l in lines if len(l) > 3 and not l.lower().startswith("here are")]
            if lines:
                return lines
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to parse topics from AI response"
            )

    except Exception as e:
        logger.error(f"Ticklist generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate ticklist: {str(e)}"
        )
