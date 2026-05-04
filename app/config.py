"""
Configuration module for KTUfy Backend
Loads and validates environment variables using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    # Application Settings
    app_name: str = Field(default="KTUfy Backend API", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=True, alias="DEBUG")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    
    # Supabase Configuration
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_anon_key: str = Field(..., alias="SUPABASE_ANON_KEY")
    supabase_service_key: str = Field(..., alias="SUPABASE_SERVICE_KEY")
    
    # JWT Configuration
    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Database Configuration (Optional for now)
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    
    # Redis Configuration (for Phase 8)
    redis_url: Optional[str] = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    
    # Neo4j Configuration (Knowledge Graph)
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")
    
    # File Upload Settings
    max_upload_size: int = Field(default=10485760, alias="MAX_UPLOAD_SIZE")  # 10MB
    allowed_extensions: str = Field(default=".pdf,.jpg,.jpeg,.png", alias="ALLOWED_EXTENSIONS")
    upload_dir: str = Field(default="uploads/syllabus", alias="UPLOAD_DIR")
    
    # Embedding Model Settings
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2", 
        alias="EMBEDDING_MODEL"
    )
    
    # LLM Configuration
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: Optional[str] = Field(default="gemini-1.5-flash", alias="GEMINI_MODEL")
    ollama_base_url: Optional[str] = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: Optional[str] = Field(default="llama3.2", alias="OLLAMA_MODEL")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env
    
    @property
    def allowed_extensions_list(self) -> list[str]:
        """Convert comma-separated extensions to list"""
        return [ext.strip() for ext in self.allowed_extensions.split(",")]
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"


# Create a global settings instance
settings = Settings()


# Helper function to get settings
def get_settings() -> Settings:
    """
    Dependency function to get settings
    Can be used in FastAPI dependency injection
    """
    return settings
