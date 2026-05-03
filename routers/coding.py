"""
Coding Router
Proxies code execution requests to Judge0 CE API.

The frontend has a built-in fallback to the free Judge0 CE public API,
so this endpoint is best-effort. If JUDGE0_API_URL is not configured,
the endpoint returns a clear error so the frontend can fall back.

Environment variables (optional):
  JUDGE0_API_URL   — Base URL of Judge0 CE instance (default: https://judge0-ce.p.rapidapi.com)
  JUDGE0_API_KEY   — API key / RapidAPI key (required for hosted APIs)
  JUDGE0_API_HOST  — RapidAPI host header (only needed for RapidAPI)
"""
import base64
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user, AuthenticatedUser
from schemas.coding import CodeExecuteRequest, CodeExecuteResponse, ExecutionStatus

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/coding",
    tags=["Coding"]
)

# ─── Judge0 language ID mapping ──────────────────────────────────────────────
LANGUAGE_IDS = {
    "python": 71,   # Python 3
    "c": 50,        # C (GCC)
    "cpp": 54,      # C++ (GCC)
    "java": 62,     # Java (OpenJDK)
}

# Judge0 status codes we care about
STATUS_QUEUED = 1
STATUS_PROCESSING = 2
STATUS_ACCEPTED = 3      # success
STATUS_WRONG_ANSWER = 4
STATUS_TLE = 5
STATUS_COMPILATION_ERROR = 6
STATUS_RUNTIME_ERROR_SIGSEGV = 7
STATUS_RUNTIME_ERROR_SIGXFSZ = 8
STATUS_RUNTIME_ERROR_SIGFPE = 9
STATUS_RUNTIME_ERROR_SIGABRT = 10
STATUS_RUNTIME_ERROR_NZEC = 11
STATUS_RUNTIME_ERROR_OTHER = 12
STATUS_INTERNAL_ERROR = 13
STATUS_EXEC_FORMAT_ERROR = 14


def _get_judge0_config() -> tuple[str, dict]:
    """Return (base_url, headers) for Judge0 CE API."""
    base_url = os.getenv("JUDGE0_API_URL", "").rstrip("/")
    api_key = os.getenv("JUDGE0_API_KEY", "")
    api_host = os.getenv("JUDGE0_API_HOST", "")

    if not base_url:
        # Default to RapidAPI hosted Judge0 CE
        base_url = "https://judge0-ce.p.rapidapi.com"

    headers: dict[str, str] = {"Content-Type": "application/json"}

    if api_host:
        # RapidAPI style
        headers["X-RapidAPI-Key"] = api_key
        headers["X-RapidAPI-Host"] = api_host
    elif api_key:
        # Self-hosted with auth token
        headers["X-Auth-Token"] = api_key

    return base_url, headers


def _decode_b64(val: Optional[str]) -> Optional[str]:
    """Decode a base64-encoded string (Judge0 returns b64 by default)."""
    if not val:
        return None
    try:
        return base64.b64decode(val).decode("utf-8", errors="replace")
    except Exception:
        return val  # already plain text


# ─── POST /execute ────────────────────────────────────────────────────────────

@router.post("/execute", response_model=CodeExecuteResponse)
async def execute_code(
    request: CodeExecuteRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Execute source code via Judge0 CE.

    Supported languages: `python`, `c`, `cpp`, `java`.

    The backend proxies the request to a Judge0 CE instance. If the backend
    is not configured with a Judge0 API, it returns an error and the frontend
    falls back to its own public Judge0 CE integration.

    **Requires authentication**: Bearer token in Authorization header
    """
    language_id = LANGUAGE_IDS.get(request.language)
    if language_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language: {request.language}. Supported: {list(LANGUAGE_IDS.keys())}"
        )

    base_url, headers = _get_judge0_config()

    # Build Judge0 submission payload
    payload = {
        "source_code": base64.b64encode(request.source_code.encode()).decode(),
        "language_id": language_id,
        "stdin": base64.b64encode(request.stdin.encode()).decode() if request.stdin else "",
        "base64_encoded": True,
        "wait": True,  # synchronous — wait for result
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Submit and wait (Judge0 CE supports ?wait=true for synchronous results)
            resp = await client.post(
                f"{base_url}/submissions?base64_encoded=true&wait=true",
                json=payload,
                headers=headers,
            )

            if resp.status_code == 401 or resp.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Judge0 API authentication failed. Check JUDGE0_API_KEY."
                )

            if resp.status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Judge0 API rate limit exceeded. Try again later."
                )

            if resp.status_code not in (200, 201):
                logger.error(f"Judge0 error {resp.status_code}: {resp.text[:500]}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Judge0 API returned status {resp.status_code}"
                )

            data = resp.json()

            # Decode base64 fields
            return CodeExecuteResponse(
                stdout=_decode_b64(data.get("stdout")),
                stderr=_decode_b64(data.get("stderr")),
                compile_output=_decode_b64(data.get("compile_output")),
                status=ExecutionStatus(
                    id=data.get("status", {}).get("id", 0),
                    description=data.get("status", {}).get("description", "Unknown"),
                ),
                time=data.get("time"),
                memory=data.get("memory"),
            )

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Code execution timed out (Judge0 did not respond in 30s)"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to Judge0 API. Service may be unavailable."
        )
    except Exception as e:
        logger.error(f"Code execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code execution failed: {str(e)}"
        )
