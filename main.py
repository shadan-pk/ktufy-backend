"""
KTUfy Backend API
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from dotenv import load_dotenv
import os

# Import routers
from routers import auth as auth_router
from routers import chat as chat_router
from routers import admin as admin_router

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title=os.getenv("APP_NAME", "KTUfy Backend API"),
    version=os.getenv("APP_VERSION", "2.0.0"),
    description="AI-powered study assistant for KTU students with KG-RAG",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(admin_router.router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Admin Dashboard Route
@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_dashboard():
    """
    Serve the Admin Dashboard HTML page
    """
    return FileResponse("templates/admin.html")



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
    # Check Neo4j connection
    try:
        from services.neo4j_service import neo4j_service
        neo4j_status = "operational" if neo4j_service.is_connected() else "not_connected"
    except:
        neo4j_status = "not_configured"
    
    # Check embedding service
    try:
        from services.embedding_service import embedding_service
        embedding_status = "operational" if embedding_service.is_ready() else "not_ready"
    except:
        embedding_status = "not_configured"
    
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "services": {
            "api": "operational",
            "authentication": "operational",
            "database": "operational",
            "neo4j_kg": neo4j_status,
            "embeddings": embedding_status,
            "storage": "operational"
        }
    }


# API status
@app.get("/api/status")
async def api_status():
    """
    API status - KG-RAG implementation
    """
    return {
        "status": "active",
        "description": "KG-RAG implementation with proper ontology",
        "features": {
            "authentication": "operational",
            "kg_rag": "operational",
            "verbatim_extraction": "operational",
            "atomic_concepts": "operational",
            "semantic_relationships": "operational",
            "query_routing": "operational",
            "chunk_based_embeddings": "operational",
            "admin_dashboard": "operational"
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
