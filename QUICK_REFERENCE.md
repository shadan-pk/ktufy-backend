# KTUfy Backend - Quick Reference Guide

## 🚀 Quick Start Commands

### Start Server
```powershell
cd e:\KTUfy_Project\ktufy-backend
E:/KTUfy_Project/ktufy-backend/venv/Scripts/python.exe main.py
```

### Test Authentication
```powershell
E:/KTUfy_Project/ktufy-backend/venv/Scripts/python.exe test_auth.py
```

### Install Dependencies
```powershell
E:/KTUfy_Project/ktufy-backend/venv/Scripts/python.exe -m pip install -r requirements.txt
```

---

## 📍 API Endpoints

### Base URL
`http://localhost:8000`

### Documentation
- Interactive: `http://localhost:8000/docs`
- Alternative: `http://localhost:8000/redoc`

### Endpoints

#### **General**
- `GET /` - Welcome message
- `GET /health` - Health check
- `GET /api/v1/status` - API status

#### **Authentication** 🔒
- `GET /api/v1/auth/me` - Get user profile (Protected)
- `GET /api/v1/auth/status` - Check auth status
- `POST /api/v1/auth/verify-token` - Verify JWT token
- `GET /api/v1/auth/protected-example` - Protected demo
- `GET /api/v1/auth/public-example` - Public demo

🔒 = Requires: `Authorization: Bearer YOUR_TOKEN`

---

## 🔑 Authentication Headers

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 📦 Project Status

✅ **Phase 1**: Environment Setup - COMPLETE
✅ **Phase 2**: Authentication Integration - COMPLETE
⏳ **Phase 3**: Database Schema Design - TODO
⏳ **Phase 4**: Basic API Structure - TODO
⏳ **Phase 5**: AI/ML Foundation - TODO
⏳ **Phase 6**: KG-RAG Implementation - TODO
⏳ **Phase 7**: Content Generation - TODO
⏳ **Phase 8**: Async Processing - TODO
⏳ **Phase 9**: Progress Tracking - TODO
⏳ **Phase 10**: Study Packs - TODO
⏳ **Phase 11**: Search & Recommendations - TODO
⏳ **Phase 12**: Deployment - TODO

---

## 🔧 Common Tasks

### Get User in Protected Route
```python
from fastapi import Depends
from app.auth import get_current_user, AuthenticatedUser

@router.get("/protected")
async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
    return {"user_id": user.user_id, "email": user.email}
```

### Optional Authentication
```python
from typing import Optional
from app.auth import get_optional_user

@router.get("/optional")
async def optional_route(user: Optional[AuthenticatedUser] = Depends(get_optional_user)):
    if user:
        return {"message": f"Hello {user.email}"}
    return {"message": "Hello guest"}
```

### Role-Based Access
```python
from app.auth import require_role

@router.get("/admin")
async def admin_route(user: AuthenticatedUser = Depends(require_role("admin"))):
    return {"message": "Admin access"}
```

---

## 📂 Important Files

- `main.py` - Application entry point
- `app/config.py` - Configuration
- `app/auth.py` - Authentication logic
- `routers/auth.py` - Auth endpoints
- `utils/supabase_client.py` - Supabase connection
- `.env` - Environment variables (DO NOT COMMIT!)
- `requirements.txt` - Python dependencies

---

## 🐛 Troubleshooting

### Server won't start
1. Check if port 8000 is free
2. Verify `.env` file exists
3. Check for syntax errors in recent changes

### Authentication fails
1. Verify token format: `Bearer TOKEN`
2. Check token hasn't expired
3. Confirm Supabase credentials in `.env`

### Import errors
```powershell
E:/KTUfy_Project/ktufy-backend/venv/Scripts/python.exe -m pip install -r requirements.txt
```

---

## 📞 Need Help?

1. Check `PHASE_2_COMPLETE.md` for detailed documentation
2. Visit API docs at `http://localhost:8000/docs`
3. Review error messages in terminal
4. Check `test_auth.py` output

---

**Current Version**: Phase 2 Complete
**Last Updated**: October 20, 2025
