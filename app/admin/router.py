import json
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import settings
from .dependencies import require_admin

router = APIRouter(prefix="/admin-panel", tags=["admin"])


@router.get("/login", response_class=HTMLResponse)
async def admin_login() -> str:
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <title>Admin Login - KTUfy</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #0f0f0f; color: #fff;
           display: flex; align-items: center; justify-content: center; height: 100vh; }}
    .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px;
             padding: 2rem; width: 100%; max-width: 380px; }}
    h1 {{ font-size: 1.25rem; margin-bottom: 1.5rem; color: #e5e5e5; }}
    input {{ width: 100%; padding: 0.65rem 0.85rem; margin-bottom: 1rem;
             background: #0f0f0f; border: 1px solid #333; border-radius: 8px;
             color: #fff; font-size: 0.95rem; outline: none; }}
    button {{ width: 100%; padding: 0.7rem; background: #4f46e5; border: none;
              border-radius: 8px; color: #fff; font-size: 1rem; cursor: pointer; }}
    button:hover {{ background: #4338ca; }}
    .error {{ color: #f87171; font-size: 0.85rem; margin-top: 0.75rem; min-height: 1.2rem; }}
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>KTUfy Admin</h1>
    <input type=\"email\" id=\"email\" placeholder=\"Admin email\" />
    <input type=\"password\" id=\"password\" placeholder=\"Password\" />
    <button onclick=\"adminLogin()\">Sign In</button>
    <p class=\"error\" id=\"err\"></p>
  </div>

  <script src=\"https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2\"></script>
  <script>
    const sb = window.supabase.createClient(
      '{settings.supabase_url}',
      '{settings.supabase_anon_key}'
    )

    window.adminLogin = async function adminLogin() {{
      const email = document.getElementById('email').value
      const password = document.getElementById('password').value
      document.getElementById('err').textContent = ''

      const {{ data, error }} = await sb.auth.signInWithPassword({{ email, password }})
      if (error) return (document.getElementById('err').textContent = error.message)

      if (data.user?.app_metadata?.role !== 'admin') {{
        await sb.auth.signOut()
        document.getElementById('err').textContent = 'This account does not have admin access.'
        return
      }}

      const res = await fetch('/admin-panel/auth/session', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ access_token: data.session.access_token }})
      }})

      if (res.ok) window.location.href = '/admin-panel/dashboard'
      else document.getElementById('err').textContent = 'Session error, try again.'
    }}
  </script>
</body>
</html>"""


@router.post("/auth/session")
async def admin_set_session(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        token = body.get("access_token")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not token:
        return JSONResponse({"error": "Missing token"}, status_code=400)

    response = JSONResponse({"ok": True})
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=3600,
    )
    return response


@router.get("/auth/logout")
async def admin_logout() -> RedirectResponse:
    response = RedirectResponse(url="/admin-panel/login", status_code=302)
    response.delete_cookie("admin_token")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(admin_user: dict = Depends(require_admin)) -> str:
    email = admin_user.get("email", "")
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>Admin Dashboard - KTUfy</title>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: system-ui, sans-serif; background: #0f0f0f; color: #fff;
               display: flex; align-items: center; justify-content: center; height: 100vh; }}
        .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px;
                 padding: 2rem; width: 100%; max-width: 420px; text-align: center; }}
        h1 {{ font-size: 1.35rem; margin-bottom: 1.25rem; color: #e5e5e5; }}
        .btn {{ display: inline-block; padding: 0.65rem 1rem; background: #4f46e5; border: none;
                border-radius: 8px; color: #fff; font-size: 0.95rem; text-decoration: none; }}
        .btn:hover {{ background: #4338ca; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Welcome, {email}</h1>
        <a class="btn" href="/admin-panel/auth/logout">Logout</a>
      </div>
    </body>
    </html>
    """
