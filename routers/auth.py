"""
Authentication router
Handles authentication-related endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from pydantic import EmailStr

from app.auth import get_current_user, get_optional_user, AuthenticatedUser, verify_supabase_token
from schemas.user import (
    UserResponse, 
    UserProfile, 
    TokenVerifyRequest, 
    TokenVerifyResponse,
    AuthStatusResponse,
    UserUpdateRequest,
    MessageResponse
)
from utils.supabase_client import supabase_admin_client

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
    
    Fetches user data from both auth.users and public.users tables.
    
    Returns:
        UserProfile: The authenticated user's profile information
    """
    try:
        # Fetch user data from public.users table
        response = supabase_admin_client.table("users").select("*").eq("id", current_user.user_id).execute()
        
        if response.data and len(response.data) > 0:
            user_data = response.data[0]
            # Merge with auth user data
            return UserProfile(
                user_id=current_user.user_id,
                email=current_user.email,
                role=current_user.role,
                metadata=user_data  # Include all fields from public.users
            )
        
        # Fallback if no record in public.users
        return UserProfile(
            user_id=current_user.user_id,
            email=current_user.email,
            role=current_user.role,
            metadata=current_user.metadata
        )
    except Exception as e:
        # Fallback to auth data only
        return UserProfile(
            user_id=current_user.user_id,
            email=current_user.email,
            role=current_user.role,
            metadata=current_user.metadata
        )


@router.put("/me", response_model=UserProfile)
async def update_user_profile(
    update_data: UserUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Update the current authenticated user's profile
    
    **Requires authentication**: Bearer token in Authorization header
    
    Updates both auth.users (email) and public.users (profile data) tables.
    
    Args:
        update_data: User update data (email and/or profile fields)
        
    Returns:
        UserProfile: The updated user profile
    """
    try:
        # Prepare data for public.users table
        users_table_data = {}
        
        if update_data.name is not None:
            users_table_data["name"] = update_data.name
        if update_data.registration_number is not None:
            users_table_data["registration_number"] = update_data.registration_number
        if update_data.college is not None:
            users_table_data["college"] = update_data.college
        if update_data.branch is not None:
            users_table_data["branch"] = update_data.branch
        if update_data.year_joined is not None:
            users_table_data["year_joined"] = update_data.year_joined
        if update_data.year_ending is not None:
            users_table_data["year_ending"] = update_data.year_ending
        if update_data.roll_number is not None:
            users_table_data["roll_number"] = update_data.roll_number
        if update_data.metadata is not None:
            users_table_data["metadata"] = update_data.metadata
        
        # Update email in auth.users if provided
        if update_data.email is not None:
            users_table_data["email"] = update_data.email
            # Update email in auth.users using admin client
            supabase_admin_client.auth.admin.update_user_by_id(
                uid=current_user.user_id,
                attributes={"email": update_data.email}
            )
        
        if not users_table_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )
        
        # Use UPSERT to handle both update and insert cases
        # Include user ID and email in the data
        upsert_data = {
            "id": current_user.user_id,
            "email": users_table_data.get("email", current_user.email),
            **users_table_data
        }
        
        # Upsert into public.users table (creates if doesn't exist, updates if exists)
        response = supabase_admin_client.table("users").upsert(
            upsert_data,
            on_conflict="id"
        ).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user profile"
            )
        
        # Get updated user data from auth
        auth_response = supabase_admin_client.auth.admin.get_user_by_id(current_user.user_id)
        
        # Return updated profile
        return UserProfile(
            user_id=current_user.user_id,
            email=auth_response.user.email if auth_response and auth_response.user else current_user.email,
            role=current_user.role,
            metadata=response.data[0] if response.data else {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating profile: {str(e)}"
        )
    
@router.post("/request-password-reset", response_model=MessageResponse)
async def request_password_reset(
    email: EmailStr
):
    """
    Request a password reset email (public endpoint)
    
    **No authentication required**
    
    Sends a password reset link to the user's email via Supabase.
    Use this instead of a custom change-password endpoint.
    
    Args:
        email: Email address to send reset link to
        
    Returns:
        MessageResponse: Success message (always returns success for security)
    """
    try:
        # Use Supabase password reset functionality
        supabase_admin_client.auth.reset_password_email(email)
        
        # Always return success (don't reveal if email exists)
        return MessageResponse(
            message="If the email exists, a password reset link has been sent",
            success=True
        )
        
    except Exception as e:
        # Still return success for security (don't reveal if email exists)
        return MessageResponse(
            message="If the email exists, a password reset link has been sent",
            success=True
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


@router.post("/verify-email", response_model=MessageResponse)
async def send_verification_email(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Send email verification to the current user
    
    **Requires authentication**: Bearer token in Authorization header
    
    Returns:
        MessageResponse: Success message
    """
    try:
        # Check if email is already verified
        user_response = supabase_admin_client.auth.admin.get_user_by_id(current_user.user_id)
        
        if user_response and user_response.user:
            if user_response.user.email_confirmed_at:
                return MessageResponse(
                    message="Email is already verified",
                    success=True
                )
        
        # Resend verification email using Supabase
        # Note: Supabase will send the verification email automatically
        # We can use the resend method or regenerate the confirmation
        response = supabase_admin_client.auth.admin.generate_link(
            type="signup",
            email=current_user.email,
            options={"redirect_to": "your-app-redirect-url"}  # Configure this based on your needs
        )
        
        return MessageResponse(
            message="Verification email sent successfully",
            success=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending verification email: {str(e)}"
        )


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user_account(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Delete a user account
    
    **Requires authentication**: Bearer token in Authorization header
    
    Users can only delete their own account unless they have admin privileges.
    
    Args:
        user_id: The ID of the user to delete
        
    Returns:
        MessageResponse: Success message
    """
    try:
        # Check if user is trying to delete their own account
        if current_user.user_id != user_id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own account"
            )
        
        # Delete user using admin client
        supabase_admin_client.auth.admin.delete_user(user_id)
        
        return MessageResponse(
            message="User account deleted successfully",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user account: {str(e)}"
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
