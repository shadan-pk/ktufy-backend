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
    AuthStatusResponse,
    UserUpdateRequest,
    ChangePasswordRequest,
    MessageResponse
)
from utils.supabase_client import supabase_client, supabase_admin_client

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


@router.put("/me", response_model=UserProfile)
async def update_user_profile(
    update_data: UserUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Update the current authenticated user's profile
    
    **Requires authentication**: Bearer token in Authorization header
    
    Args:
        update_data: User update data (email and/or metadata)
        
    Returns:
        UserProfile: The updated user profile
    """
    try:
        # Prepare update data for Supabase
        update_dict = {}
        
        if update_data.email is not None:
            update_dict["email"] = update_data.email
            
        if update_data.metadata is not None:
            update_dict["data"] = update_data.metadata
        
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )
        
        # Update user using admin client to bypass RLS
        response = supabase_admin_client.auth.admin.update_user_by_id(
            uid=current_user.user_id,
            attributes=update_dict
        )
        
        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user profile"
            )
        
        # Return updated profile
        return UserProfile(
            user_id=response.user.id,
            email=response.user.email,
            role=response.user.role or "authenticated",
            metadata=response.user.user_metadata or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating profile: {str(e)}"
        )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Change the current authenticated user's password
    
    **Requires authentication**: Bearer token in Authorization header
    
    Args:
        password_data: New password data
        
    Returns:
        MessageResponse: Success message
    """
    try:
        # Update user password using admin client
        response = supabase_admin_client.auth.admin.update_user_by_id(
            uid=current_user.user_id,
            attributes={"password": password_data.new_password}
        )
        
        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change password"
            )
        
        return MessageResponse(
            message="Password changed successfully",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error changing password: {str(e)}"
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
