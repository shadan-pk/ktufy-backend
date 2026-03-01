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
    Extended user profile with metadata (legacy — kept for internal use)
    """
    metadata: dict = Field(default_factory=dict, description="User metadata from Supabase")
    
    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    """
    Flat user profile response matching frontend expectations.
    All public.users columns are top-level fields.
    """
    user_id: str = Field(..., description="Unique user identifier")
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    registration_number: Optional[str] = None
    college: Optional[str] = None
    branch: Optional[str] = None
    semester: Optional[str] = Field(None, description="Semester string e.g. S1-S8")
    year_joined: Optional[int] = None
    year_ending: Optional[int] = None
    roll_number: Optional[str] = None
    metadata: Optional[dict] = Field(default_factory=dict)
    role: str = Field(default="student", description="User role")
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "student@ktu.edu.in",
                "name": "John Doe",
                "registration_number": "KTU20CS001",
                "college": "College of Engineering",
                "branch": "CSE",
                "semester": "S6",
                "year_joined": 2020,
                "year_ending": 2024,
                "roll_number": "20CS001",
                "metadata": {},
                "role": "student",
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


class UserUpdateRequest(BaseModel):
    """
    Request schema for updating user profile
    All fields are optional - only provided fields will be updated
    """
    # Auth fields
    email: Optional[EmailStr] = Field(None, description="Email address")
    
    # Public users table fields
    name: Optional[str] = Field(None, description="Full name")
    registration_number: Optional[str] = Field(None, description="University registration number")
    college: Optional[str] = Field(None, description="College name")
    branch: Optional[str] = Field(None, description="Branch/Department")
    semester: Optional[str] = Field(None, description="Semester string e.g. S1-S8")
    year_joined: Optional[int] = Field(None, description="Year of joining", ge=2000, le=2100)
    year_ending: Optional[int] = Field(None, description="Year of completion", ge=2000, le=2100)
    roll_number: Optional[str] = Field(None, description="Roll number")
    metadata: Optional[dict] = Field(None, description="Additional metadata (JSONB)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@ktu.edu.in",
                "registration_number": "KTU123456",
                "college": "College of Engineering Trivandrum",
                "branch": "Computer Science",
                "year_joined": 2021,
                "year_ending": 2025,
                "roll_number": "CSE21001",
                "semester": "S5",
                "metadata": {
                    "phone": "+91-1234567890"
                }
            }
        }


class MessageResponse(BaseModel):
    """
    Generic message response
    """
    message: str
    success: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation completed successfully",
                "success": True
            }
        }
