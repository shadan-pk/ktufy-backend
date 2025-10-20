"""
KTUfy Backend API
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Import routers
from routers import auth as auth_router

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title=os.getenv("APP_NAME", "KTUfy Backend API"),
    version=os.getenv("APP_VERSION", "1.0.0"),
    description="AI-powered study assistant for KTU students",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include routers
app.include_router(auth_router.router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "services": {
            "api": "operational",
            "authentication": "operational",  # Phase 2 complete!
            "database": "not_configured",     # Will update in Phase 3
            "vector_db": "not_configured",    # Will update in Phase 5
            "storage": "not_configured"       # Will update in Phase 3
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
            "authentication": "operational",      # ✅ Phase 2 complete
            "notes_upload": "pending",
            "kg_rag": "pending",
            "content_generation": "pending",
            "progress_tracking": "pending"
        }
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
