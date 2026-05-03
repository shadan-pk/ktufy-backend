"""
Learning-related Pydantic schemas
Defines data models for quiz and match-pair generation APIs
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from uuid import UUID


# ─── Quiz Schemas ─────────────────────────────────────────────────────────────

class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question"""
    question: str = Field(..., description="The question text")
    options: List[str] = Field(..., description="List of answer choices (4 options)")
    correctAnswer: int = Field(..., description="0-based index of the correct option")
    explanation: str = Field(..., description="Brief explanation of the correct answer")


class QuizRequest(BaseModel):
    """Schema for quiz generation request"""
    topic: str = Field(..., description="Topic to generate quiz for", min_length=1)
    count: int = Field(default=5, description="Number of questions to generate", ge=1, le=20)
    difficulty: Literal["easy", "medium", "hard"] = Field(
        default="medium", description="Difficulty level of the questions"
    )
    force_regenerate: bool = Field(
        default=False,
        description="If true, bypass cache and generate a fresh quiz"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Binary Search Trees",
                "count": 5,
                "difficulty": "medium",
                "force_regenerate": False
            }
        }


class QuizResponse(BaseModel):
    """Schema for quiz generation response"""
    id: Optional[UUID] = Field(None, description="Database ID of the saved quiz")
    topic: str = Field(..., description="The topic the quiz was generated for")
    difficulty: str = Field(default="medium", description="Difficulty level")
    questions: List[QuizQuestion] = Field(..., description="Generated quiz questions")
    cached: bool = Field(default=False, description="Whether this was returned from cache")
    created_at: Optional[datetime] = Field(None, description="When the quiz was created")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "topic": "Binary Search Trees",
                "difficulty": "medium",
                "questions": [
                    {
                        "question": "What is the time complexity of searching in a balanced BST?",
                        "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
                        "correctAnswer": 1,
                        "explanation": "In a balanced BST, each comparison eliminates half the remaining nodes, giving O(log n)."
                    }
                ],
                "cached": False,
                "created_at": "2025-01-01T00:00:00Z"
            }
        }


# ─── Match Pair Schemas ──────────────────────────────────────────────────────

class MatchPair(BaseModel):
    """A single term-definition pair for matching exercises"""
    term: str = Field(..., description="The term or concept")
    definition: str = Field(..., description="The matching definition or explanation")


class MatchRequest(BaseModel):
    """Schema for match-pair generation request"""
    topic: str = Field(..., description="Topic to generate match pairs for", min_length=1)
    count: int = Field(default=6, description="Number of pairs to generate", ge=2, le=15)
    force_regenerate: bool = Field(
        default=False,
        description="If true, bypass cache and generate fresh match pairs"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Database Normalization",
                "count": 6,
                "force_regenerate": False
            }
        }


class MatchResponse(BaseModel):
    """Schema for match-pair generation response"""
    id: Optional[UUID] = Field(None, description="Database ID of the saved match set")
    topic: str = Field(..., description="The topic match pairs were generated for")
    pairs: List[MatchPair] = Field(..., description="Generated term-definition pairs")
    cached: bool = Field(default=False, description="Whether this was returned from cache")
    created_at: Optional[datetime] = Field(None, description="When the match set was created")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "topic": "Database Normalization",
                "pairs": [
                    {
                        "term": "1NF",
                        "definition": "All attributes contain only atomic (indivisible) values"
                    },
                    {
                        "term": "2NF",
                        "definition": "Meets 1NF and every non-key attribute is fully functionally dependent on the primary key"
                    }
                ],
                "cached": False,
                "created_at": "2025-01-01T00:00:00Z"
            }
        }


# ─── Shared listing schema ───────────────────────────────────────────────────

class LearningSetSummary(BaseModel):
    """Summary view used when listing saved quizzes or match sets"""
    id: UUID = Field(..., description="Database ID")
    topic: str = Field(..., description="Topic name")
    type: Literal["quiz", "match"] = Field(..., description="Content type")
    item_count: int = Field(..., description="Number of questions or pairs")
    difficulty: Optional[str] = Field(None, description="Difficulty level (quizzes only)")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")

    class Config:
        from_attributes = True
