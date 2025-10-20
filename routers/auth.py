"""
Authentication router
Handles authentication-related endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from app.auth import get_current_user, get_optional_user, AuthenticatedUser, verify_supabase_token
from schemas.user import (
    UserResponse, 
    UserProfile, 
    TokenVerifyRequest, 
    TokenVerifyResponse,
    AuthStatusResponse
)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get the current authenticated user's profile
    
    **Requires authentication**: Bearer token in Authorization header
    
    Returns:
        UserProfile: The authenticated user's profile information
    """
    return UserProfile(
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role,
        metadata=current_user.metadata
    )


@router.get("/status", response_model=AuthStatusResponse)
async def check_auth_status(
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user)
):
    """
    Check authentication status
    
    **Optional authentication**: Works with or without Bearer token
    
    Returns:
        AuthStatusResponse: Authentication status and user info if authenticated
    """
    if current_user:
        return AuthStatusResponse(
            authenticated=True,
            user=UserResponse(
                user_id=current_user.user_id,
                email=current_user.email,
                role=current_user.role
            ),
            message="User is authenticated"
        )
    
    return AuthStatusResponse(
        authenticated=False,
        user=None,
        message="No authentication token provided"
    )


@router.post("/verify-token", response_model=TokenVerifyResponse)
async def verify_token(request: TokenVerifyRequest):
    """
    Verify a JWT token without requiring it in the Authorization header
    
    **Public endpoint**: Does not require authentication
    
    This is useful for clients to check if a token is still valid
    before making authenticated requests.
    
    Args:
        request: Token verification request containing the JWT token
        
    Returns:
        TokenVerifyResponse: Token validity status and user info if valid
    """
    try:
        user_data = await verify_supabase_token(request.token)
        
        return TokenVerifyResponse(
            valid=True,
            user_id=user_data["user_id"],
            email=user_data["email"],
            message="Token is valid"
        )
    except HTTPException as e:
        return TokenVerifyResponse(
            valid=False,
            user_id=None,
            email=None,
            message=e.detail
        )


@router.get("/protected-example")
async def protected_example(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Example protected endpoint
    
    **Requires authentication**: Bearer token in Authorization header
    
    This demonstrates how to create a protected route that requires authentication.
    
    Returns:
        dict: A personalized message for the authenticated user
    """
    return {
        "message": f"Hello, {current_user.email}!",
        "user_id": current_user.user_id,
        "role": current_user.role,
        "info": "This endpoint is protected and requires authentication"
    }


@router.get("/public-example")
async def public_example():
    """
    Example public endpoint
    
    **No authentication required**
    
    This demonstrates a public endpoint that anyone can access.
    
    Returns:
        dict: A welcome message
    """
    return {
        "message": "This is a public endpoint",
        "info": "No authentication required to access this endpoint"
    }
