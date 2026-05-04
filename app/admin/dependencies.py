import httpx
from fastapi import Request, HTTPException

from app.config import settings


async def require_admin(request: Request) -> dict:
    """
    FastAPI dependency that validates a Supabase JWT and checks admin role.
    Checks httpOnly cookie first, then Authorization header.
    """
    token = (
        request.cookies.get("admin_token")
        or request.headers.get("Authorization", "").replace("Bearer ", "")
    )

    if not token:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(status_code=307, headers={"Location": "/admin-panel/login"})
        raise HTTPException(status_code=401, detail="No token provided")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_service_key,
                },
                timeout=5.0,
            )
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Auth service unreachable")

    if response.status_code != 200:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(status_code=307, headers={"Location": "/admin-panel/login"})
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = response.json()
    role = user.get("app_metadata", {}).get("role")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")

    return user
