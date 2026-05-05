"""
Chat Router
Handles chat session and message endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
import asyncio
import logging
from typing import List, Dict
from uuid import UUID

from app.auth import get_current_user, AuthenticatedUser
from schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionWithMessages,
    ChatRequest,
    ChatResponse,
    ChatMessageResponse
)
from services.chat_service import chat_service
from utils.supabase_client import supabase_admin_client
from schemas.user import MessageResponse

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"]
)

# Track active chat tasks for cancellation
active_chat_tasks: Dict[str, asyncio.Task] = {}


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Create a new chat session
    
    **Requires authentication**: Bearer token in Authorization header
    
    Creates a new chat session for the authenticated user.
    Each session can contain multiple messages and maintains conversation context.
    
    Args:
        session_data: Session creation data (title, model_name)
        
    Returns:
        ChatSessionResponse: The created session
    """
    try:
        response = supabase_admin_client.table("chat_sessions").insert({
            "user_id": current_user.user_id,
            "title": session_data.title,
            "model_name": session_data.model_name
        }).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create chat session"
            )
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating session: {str(e)}"
        )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_user_sessions(
    current_user: AuthenticatedUser = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0
):
    """
    Get all chat sessions for the current user
    
    **Requires authentication**: Bearer token in Authorization header
    
    Retrieves a paginated list of chat sessions for the authenticated user,
    ordered by most recently updated.
    
    Args:
        limit: Maximum number of sessions to return (default: 50)
        offset: Number of sessions to skip (default: 0)
        
    Returns:
        List[ChatSessionResponse]: List of chat sessions
    """
    try:
        response = supabase_admin_client.table("chat_sessions")\
            .select("*")\
            .eq("user_id", current_user.user_id)\
            .order("updated_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        return response.data if response.data else []
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessages)
async def get_chat_session(
    session_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get a specific chat session with all messages
    
    **Requires authentication**: Bearer token in Authorization header
    
    Retrieves a chat session and all its messages in chronological order.
    Users can only access their own sessions.
    
    Args:
        session_id: The UUID of the chat session
        
    Returns:
        ChatSessionWithMessages: Session with all messages
    """
    try:
        # Get session
        session_response = supabase_admin_client.table("chat_sessions")\
            .select("*")\
            .eq("id", str(session_id))\
            .eq("user_id", current_user.user_id)\
            .execute()
        
        if not session_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Get messages for this session
        messages_response = supabase_admin_client.table("chat_messages")\
            .select("*")\
            .eq("session_id", str(session_id))\
            .order("created_at")\
            .execute()
        
        session = session_response.data[0]
        session["messages"] = messages_response.data if messages_response.data else []
        
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching session: {str(e)}"
        )


@router.post("/message", response_model=ChatResponse)
async def send_message(
    chat_request: ChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Send a message and get AI response with KG-RAG context
    
    **Requires authentication**: Bearer token in Authorization header
    
    Sends a message in a chat session and gets an AI-generated response.
    The system automatically fetches relevant context from the Knowledge Graph
    and syllabus embeddings to provide accurate, syllabus-based answers.
    
    Args:
        chat_request: Message content and optional session_id
        
    Returns:
        ChatResponse: User message and AI assistant response
    """
    user_id = current_user.user_id
    task = asyncio.current_task()
    active_chat_tasks[user_id] = task
    
    try:
        # Create session if needed
        if not chat_request.session_id:
            session_response = supabase_admin_client.table("chat_sessions").insert({
                "user_id": current_user.user_id,
                "title": chat_request.message[:50]  # First 50 chars as title
            }).execute()
            
            if not session_response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create chat session"
                )
            
            session_id = session_response.data[0]["id"]
        else:
            session_id = str(chat_request.session_id)
            
            # Verify session belongs to user
            verify_response = supabase_admin_client.table("chat_sessions")\
                .select("id")\
                .eq("id", session_id)\
                .eq("user_id", current_user.user_id)\
                .execute()
            
            if not verify_response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )
        
        # Save user message
        user_message_response = supabase_admin_client.table("chat_messages").insert({
            "session_id": session_id,
            "role": "user",
            "content": chat_request.message
        }).execute()
        
        if not user_message_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save user message"
            )
        
        # Get conversation history for context (exclude current message)
        history_response = supabase_admin_client.table("chat_messages")\
            .select("role, content")\
            .eq("session_id", session_id)\
            .order("created_at")\
            .execute()
        
        # Build conversation history (exclude the just-saved user message)
        conversation_history = []
        if history_response.data:
            # Take all but the last message (which is the current query)
            for msg in history_response.data[:-1]:
                conversation_history.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Generate AI response using KG-RAG
        try:
            ai_response = await chat_service.generate_rag_response(
                query=chat_request.message,
                conversation_history=conversation_history,
                stream=False
            )
        except Exception as e:
            # If AI generation fails, still return the user message
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"AI service unavailable: {str(e)}"
            )
        
        # Save assistant message
        assistant_message_response = supabase_admin_client.table("chat_messages").insert({
            "session_id": session_id,
            "role": "assistant",
            "content": ai_response
        }).execute()
        
        if not assistant_message_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save assistant message"
            )
        
        # Update session timestamp
        supabase_admin_client.table("chat_sessions")\
            .update({"updated_at": "now()"})\
            .eq("id", session_id)\
            .execute()
        
        return {
            "session_id": session_id,
            "message": user_message_response.data[0],
            "assistant_message": assistant_message_response.data[0]
        }
        
    except HTTPException:
        raise
    except asyncio.CancelledError:
        logger.info(f"Chat generation cancelled for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Generation cancelled by user"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )
    finally:
        # Remove task from tracking if it's still there
        if active_chat_tasks.get(user_id) == task:
            del active_chat_tasks[user_id]


@router.post("/stop", response_model=MessageResponse)
async def stop_generation(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Stop any ongoing AI generation for the current user
    """
    user_id = current_user.user_id
    if user_id in active_chat_tasks:
        active_chat_tasks[user_id].cancel()
        return MessageResponse(message="Generation stopped", success=True)
    
    return MessageResponse(message="No active generation found", success=True)


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(
    session_id: UUID,
    session_data: ChatSessionCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Update a chat session (e.g., change title)
    
    **Requires authentication**: Bearer token in Authorization header
    
    Args:
        session_id: The UUID of the chat session
        session_data: Updated session data
        
    Returns:
        ChatSessionResponse: Updated session
    """
    try:
        response = supabase_admin_client.table("chat_sessions")\
            .update({
                "title": session_data.title,
                "model_name": session_data.model_name
            })\
            .eq("id", str(session_id))\
            .eq("user_id", current_user.user_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating session: {str(e)}"
        )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Delete a chat session and all its messages
    
    **Requires authentication**: Bearer token in Authorization header
    
    Permanently deletes a chat session. All messages in the session
    are also deleted (CASCADE).
    
    Args:
        session_id: The UUID of the chat session
        
    Returns:
        MessageResponse: Success confirmation
    """
    try:
        response = supabase_admin_client.table("chat_sessions")\
            .delete()\
            .eq("id", str(session_id))\
            .eq("user_id", current_user.user_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return MessageResponse(
            message="Chat session deleted successfully",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting session: {str(e)}"
        )


@router.get("/info")
async def get_chat_info(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get information about the chat service
    
    **Requires authentication**: Bearer token in Authorization header
    
    Returns information about the AI provider being used (OpenAI or Ollama).
    
    Returns:
        dict: Chat service information
    """
    return {
        "service": "KTUfy Chat",
        "provider": chat_service.get_provider_info(),
        "features": [
            "Context-aware conversations",
            "Study assistance",
            "Educational content generation",
            "Multi-session support"
        ]
    }
