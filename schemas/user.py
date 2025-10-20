"""
User-related Pydantic schemas
Defines data models for API requests and responses
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: EmailStr
    

class UserResponse(UserBase):
    """
    User response schema
    Returned when fetching user information
    """
    user_id: str = Field(..., description="Unique user identifier from Supabase")
    email: EmailStr
    role: str = Field(default="authenticated", description="User role")
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "student@ktu.edu.in",
                "role": "authenticated",
                "created_at": "2025-10-20T10:30:00Z"
            }
        }


class UserProfile(UserResponse):
    """
    Extended user profile with metadata
    """
    metadata: dict = Field(default_factory=dict, description="User metadata from Supabase")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "student@ktu.edu.in",
                "role": "authenticated",
                "metadata": {
                    "full_name": "John Doe",
                    "semester": 4,
                    "branch": "CSE"
                },
                "created_at": "2025-10-20T10:30:00Z"
            }
        }


class TokenVerifyRequest(BaseModel):
    """
    Request schema for token verification
    """
    token: str = Field(..., description="JWT token to verify")
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class TokenVerifyResponse(BaseModel):
    """
    Response schema for token verification
    """
    valid: bool = Field(..., description="Whether the token is valid")
    user_id: Optional[str] = Field(None, description="User ID if token is valid")
    email: Optional[str] = Field(None, description="User email if token is valid")
    message: Optional[str] = Field(None, description="Additional information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "valid": True,
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "student@ktu.edu.in",
                "message": "Token is valid"
            }
        }


class AuthStatusResponse(BaseModel):
    """
    Response schema for authentication status
    """
    authenticated: bool
    user: Optional[UserResponse] = None
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "authenticated": True,
                "user": {
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "student@ktu.edu.in",
                    "role": "authenticated"
                },
                "message": "User is authenticated"
            }
        }
