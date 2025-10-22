"""
Chat-related Pydantic schemas
Defines data models for chat API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ChatMessageBase(BaseModel):
    """Base schema for chat messages"""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class ChatMessageCreate(ChatMessageBase):
    """Schema for creating a new message"""
    pass


class ChatMessageResponse(ChatMessageBase):
    """Schema for message response"""
    id: UUID
    session_id: UUID
    tokens_used: int = 0
    created_at: datetime
    metadata: dict = {}
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "session_id": "123e4567-e89b-12d3-a456-426614174001",
                "role": "assistant",
                "content": "Hello! How can I help you today?",
                "tokens_used": 15,
                "created_at": "2025-10-22T10:30:00Z",
                "metadata": {}
            }
        }


class ChatSessionCreate(BaseModel):
    """Schema for creating a new chat session"""
    title: Optional[str] = Field("New Chat", description="Session title")
    model_name: Optional[str] = Field("llama3", description="Model to use")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Study Session - Algorithms",
                "model_name": "llama3"
            }
        }


class ChatSessionResponse(BaseModel):
    """Schema for chat session response"""
    id: UUID
    user_id: UUID
    title: str
    model_name: str
    created_at: datetime
    updated_at: datetime
    metadata: dict = {}
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Study Session - Algorithms",
                "model_name": "llama3",
                "created_at": "2025-10-22T10:30:00Z",
                "updated_at": "2025-10-22T10:30:00Z",
                "metadata": {}
            }
        }


class ChatSessionWithMessages(ChatSessionResponse):
    """Schema for chat session with all messages"""
    messages: List[ChatMessageResponse] = []
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Study Session - Algorithms",
                "model_name": "llama3",
                "created_at": "2025-10-22T10:30:00Z",
                "updated_at": "2025-10-22T10:30:00Z",
                "metadata": {},
                "messages": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174002",
                        "session_id": "123e4567-e89b-12d3-a456-426614174001",
                        "role": "user",
                        "content": "Explain binary search",
                        "tokens_used": 5,
                        "created_at": "2025-10-22T10:30:00Z",
                        "metadata": {}
                    }
                ]
            }
        }


class ChatRequest(BaseModel):
    """Schema for sending a chat message"""
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    session_id: Optional[UUID] = Field(None, description="Session ID (creates new if not provided)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Can you explain recursion in Python?",
                "session_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class ChatResponse(BaseModel):
    """Schema for chat response"""
    session_id: UUID
    message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174001",
                "message": {
                    "id": "123e4567-e89b-12d3-a456-426614174002",
                    "session_id": "123e4567-e89b-12d3-a456-426614174001",
                    "role": "user",
                    "content": "Explain recursion",
                    "tokens_used": 3,
                    "created_at": "2025-10-22T10:30:00Z",
                    "metadata": {}
                },
                "assistant_message": {
                    "id": "123e4567-e89b-12d3-a456-426614174003",
                    "session_id": "123e4567-e89b-12d3-a456-426614174001",
                    "role": "assistant",
                    "content": "Recursion is a programming technique...",
                    "tokens_used": 50,
                    "created_at": "2025-10-22T10:30:05Z",
                    "metadata": {}
                }
            }
        }
