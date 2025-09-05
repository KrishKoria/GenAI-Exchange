"""
Application configuration using Pydantic Settings
"""
import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Basic server settings
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    WORKERS: int = Field(default=1, description="Number of worker processes")
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment name")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    
    # API settings
    API_V1_STR: str = Field(default="/api/v1", description="API v1 prefix")
    SECRET_KEY: str = Field(description="Secret key for JWT tokens")
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins"
    )
    ALLOWED_HOSTS: List[str] = Field(
        default=["localhost", "127.0.0.1"],
        description="Allowed hosts for production"
    )
    
    # GCP settings
    PROJECT_ID: str = Field(description="Google Cloud Project ID")
    PROJECT_NUMBER: Optional[str] = Field(default=None, description="Google Cloud Project Number (for Document AI)")
    LOCATION: str = Field(default="us-central1", description="GCP region/location")
    
    # Document AI settings
    DOC_AI_PROCESSOR_ID: str = Field(description="Document AI processor ID")
    DOC_AI_LOCATION: str = Field(default="us", description="Document AI location")
    
    # Vertex AI settings
    GEMINI_MODEL_NAME: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model name"
    )
    VERTEX_AI_LOCATION: str = Field(default="us-central1", description="Vertex AI location")
    
    # Firestore settings
    FIRESTORE_DATABASE: str = Field(default="(default)", description="Firestore database ID")
    
    # DLP settings
    DLP_ENABLED: bool = Field(default=True, description="Enable DLP API for PII detection")
    
    # BigQuery settings
    BIGQUERY_DATASET: str = Field(default="clausecompass", description="BigQuery dataset")
    BIGQUERY_TABLE: str = Field(default="events", description="BigQuery events table")
    
    # Pub/Sub settings
    PUBSUB_TOPIC: str = Field(default="clausecompass-events", description="Pub/Sub topic")
    
    # Application limits
    MAX_FILE_SIZE_MB: int = Field(default=10, description="Maximum file size in MB")
    MAX_PAGES: int = Field(default=10, description="Maximum document pages")
    MAX_CLAUSES_PER_BATCH: int = Field(default=10, description="Max clauses per batch")
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Rate limit per minute")
    
    # Token limits
    MAX_PROMPT_TOKENS: int = Field(default=30000, description="Maximum prompt tokens")
    MAX_OUTPUT_TOKENS: int = Field(default=8000, description="Maximum output tokens")
    
    # Service account key path (optional for local development)
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = Field(
        default=None,
        description="Path to GCP service account key file"
    )
    
    @validator("SECRET_KEY")
    def secret_key_required(cls, v):
        if not v:
            raise ValueError("SECRET_KEY is required")
        return v
    
    @validator("PROJECT_ID")
    def project_id_required(cls, v):
        if not v:
            raise ValueError("PROJECT_ID is required")
        return v
    
    @validator("DOC_AI_PROCESSOR_ID")
    def doc_ai_processor_id_required(cls, v):
        if not v:
            raise ValueError("DOC_AI_PROCESSOR_ID is required")
        return v
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @property
    def max_file_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()