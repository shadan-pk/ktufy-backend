"""
KTUfy Backend API
Main application entry point
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from dotenv import load_dotenv
import os

# Load environment variables BEFORE importing routers/services
# (services like Neo4j read env vars at import time)
load_dotenv()

# Import routers
from routers import auth as auth_router
from routers import chat as chat_router
from routers import admin as admin_router
from routers import admin_v2 as admin_v2_router  # V2 KG-RAG corrected router
from routers import flashcards as flashcards_router
from routers import syllabus as syllabus_router
from routers import learning as learning_router
from routers import coding as coding_router
from routers import media as media_router
from app.admin.router import router as admin_panel_router

# Import auth dependencies for the users route alias
from app.auth import get_current_user, AuthenticatedUser
from app.admin.dependencies import require_admin
from schemas.user import MessageResponse
from utils.supabase_client import supabase_admin_client

# Initialize FastAPI app
app = FastAPI(
    title=os.getenv("APP_NAME", "KTUfy Backend API"),
    version=os.getenv("APP_VERSION", "1.0.0"),
    description="AI-powered study assistant for KTU students",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(admin_router.router)
app.include_router(admin_v2_router.router)  # V2 endpoints at /api/v2/admin
app.include_router(flashcards_router.router)
app.include_router(syllabus_router.router)
app.include_router(learning_router.router)
app.include_router(coding_router.router)
app.include_router(media_router.router)
app.include_router(admin_panel_router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





@app.get("/openapi.json", include_in_schema=False)
async def admin_openapi(admin_user: dict = Depends(require_admin)):
    return app.openapi()


@app.get("/docs", include_in_schema=False)
async def admin_docs(admin_user: dict = Depends(require_admin)):
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(openapi_url="/openapi.json", title=app.title)


@app.get("/redoc", include_in_schema=False)
async def admin_redoc(admin_user: dict = Depends(require_admin)):
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(openapi_url="/openapi.json", title=app.title)


# Admin Dashboard Route
@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_dashboard(admin_user: dict = Depends(require_admin)):
    """
    Serve the Admin Dashboard HTML page
    """
    return FileResponse("templates/admin.html")


# DELETE /api/v1/users/{user_id} — route alias expected by frontend
# (Backend also has this at DELETE /api/v1/auth/users/{user_id})
@app.delete("/api/v1/users/{user_id}", response_model=MessageResponse, tags=["Authentication"])
async def delete_user_account_alias(
    user_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Delete a user account permanently.

    Users can only delete their own account unless they have admin privileges.
    """
    if current_user.user_id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own account"
        )
    try:
        supabase_admin_client.auth.admin.delete_user(user_id)
        return MessageResponse(message="Account deleted successfully.", success=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user account: {str(e)}"
        )



# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - API health check
    """
    return {
        "message": "Welcome to KTUfy Backend API",
        "status": "running",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "docs": "/docs"
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Detailed health check endpoint
    """
    # Check Neo4j connection (V2)
    try:
        from services.neo4j_service_v2 import neo4j_service
        neo4j_status = "operational" if neo4j_service.is_connected() else "not_connected"
    except:
        neo4j_status = "not_configured"
    
    # Check embedding service (V2)
    try:
        from services.embedding_service_v2 import embedding_service
        embedding_status = "operational" if embedding_service.is_ready() else "not_ready"
    except:
        embedding_status = "not_configured"
    
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "api_version": "v2",
        "services": {
            "api": "operational",
            "authentication": "operational",
            "database": "operational",
            "neo4j_kg": neo4j_status,
            "embeddings": embedding_status,
            "storage": "operational"
        }
    }


# API version info
@app.get("/api/v1/status")
async def api_status():
    """
    API version and status information
    """
    return {
        "api_version": "v1",
        "status": "active",
        "features": {
            "authentication": "operational",
            "notes_upload": "pending",
            "kg_rag": "operational",
            "content_generation": "pending",
            "progress_tracking": "pending",
            "admin_dashboard": "operational"
        }
    }


# V2 API status
@app.get("/api/v2/status")
async def api_v2_status():
    """
    V2 API status - KG-RAG corrected implementation
    """
    return {
        "api_version": "v2",
        "status": "active",
        "description": "KG-RAG corrected implementation with proper ontology",
        "features": {
            "authentication": "operational",
            "kg_rag_v2": "operational",
            "verbatim_extraction": "operational",
            "atomic_concepts": "operational",
            "semantic_relationships": "operational",
            "query_routing": "operational",
            "chunk_based_embeddings": "operational",
            "admin_dashboard_v2": "operational"
        },
        "relationship_types": ["IS_A", "PART_OF", "PREREQUISITE_OF", "USES", "IMPLEMENTS", "RELATED_TO"],
        "chunk_types": ["syllabus_content", "topic_list", "topic_detail", "course_outcomes", "references"]
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,  # Auto-reload on code changes (development only)
        log_level="info"
    )
