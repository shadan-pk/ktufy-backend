"""
Flashcard-related Pydantic schemas
Defines data models for flashcard generation API
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class FlashcardItem(BaseModel):
    """A single flashcard with front and back"""
    front: str = Field(..., description="Question or term on the front of the card")
    back: str = Field(..., description="Answer or definition on the back of the card")


class FlashcardRequest(BaseModel):
    """Schema for flashcard generation request"""
    topic: str = Field(..., description="Topic to generate flashcards for", min_length=1)
    count: int = Field(default=10, description="Number of flashcards to generate", ge=1, le=30)
    force_regenerate: bool = Field(default=False, description="If true, bypass cache and generate fresh flashcards")

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Binary Search Trees",
                "count": 10,
                "force_regenerate": False
            }
        }


class FlashcardResponse(BaseModel):
    """Schema for flashcard generation response"""
    id: Optional[UUID] = Field(None, description="Database ID of the saved flashcard set")
    topic: str = Field(..., description="The topic flashcards were generated for")
    flashcards: List[FlashcardItem] = Field(..., description="Generated flashcards")
    cached: bool = Field(default=False, description="Whether this was returned from cache")
    created_at: Optional[datetime] = Field(None, description="When the flashcard set was created")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "topic": "Binary Search Trees",
                "flashcards": [
                    {
                        "front": "What is a Binary Search Tree?",
                        "back": "A binary tree where for each node, all values in the left subtree are smaller and all values in the right subtree are larger."
                    },
                    {
                        "front": "What is the average time complexity of search in a BST?",
                        "back": "O(log n)"
                    }
                ],
                "cached": False,
                "created_at": "2026-03-01T10:30:00Z"
            }
        }


class FlashcardSetSummary(BaseModel):
    """Summary of a saved flashcard set (for listing)"""
    id: UUID
    topic: str
    card_count: int
    created_at: datetime

    class Config:
        from_attributes = True
