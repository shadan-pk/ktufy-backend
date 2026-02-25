"""
Authentication module
Handles JWT token validation and user authentication
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional
import httpx

from app.config import settings
from utils.supabase_client import supabase_admin_client


# Security scheme for Bearer token
security = HTTPBearer()


class AuthenticatedUser:
    """
    Represents an authenticated user
    """
    def __init__(self, user_id: str, email: str, role: str = "authenticated", metadata: dict = None):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.metadata = metadata or {}
    
    def __repr__(self):
        return f"AuthenticatedUser(user_id={self.user_id}, email={self.email})"


async def verify_supabase_token(token: str) -> dict:
    """
    Verify a Supabase JWT token by calling Supabase auth API
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        dict: User data from Supabase
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Verify token with Supabase
        response = supabase_admin_client.auth.get_user(token)
        
        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {
            "user_id": response.user.id,
            "email": response.user.email,
            "role": response.user.role,
            "metadata": response.user.user_metadata
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthenticatedUser:
    """
    FastAPI dependency that validates the JWT token and returns the authenticated user
    
    Usage in routes:
        @app.get("/protected")
        async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
            return {"message": f"Hello {user.email}"}
    
    Args:
        credentials: Authorization header with Bearer token
        
    Returns:
        AuthenticatedUser: The authenticated user object
        
    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    token = credentials.credentials
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token with Supabase
    user_data = await verify_supabase_token(token)
    
    # Create and return authenticated user
    user = AuthenticatedUser(
        user_id=user_data["user_id"],
        email=user_data["email"],
        role=user_data.get("role", "authenticated"),
        metadata=user_data.get("metadata", {})
    )

    try:
        from services.active_users import active_user_tracker
        await active_user_tracker.record(
            user_id=user.user_id,
            email=user.email,
            role=user.role,
        )
    except Exception:
        # Never fail auth due to telemetry/tracking issues
        pass

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency for optional authentication
    Returns user if token is provided and valid, None otherwise
    
    Usage in routes:
        @app.get("/optional-auth")
        async def optional_auth_route(user: Optional[AuthenticatedUser] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello guest"}
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def require_role(required_role: str):
    """
    Dependency factory for role-based access control
    
    Usage:
        @app.get("/admin-only")
        async def admin_route(user: AuthenticatedUser = Depends(require_role("admin"))):
            return {"message": "Admin access granted"}
    """
    async def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_role}. Your role: {user.role}"
            )
        return user
    
    return role_checker
