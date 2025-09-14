"""
Document-related Pydantic models
"""
from typing import Dict, Optional, Any, List
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field


class SupportedLanguage(str, Enum):
    """Supported languages for document analysis."""
    ENGLISH = "en"
    HINDI = "hi"
    BENGALI = "bn"
    TAMIL = "ta"
    TELUGU = "te"
    MARATHI = "mr"
    GUJARATI = "gu"
    KANNADA = "kn"
    MALAYALAM = "ml"
    PUNJABI = "pa"
    URDU = "ur"


class DocumentStatus(str, Enum):
    """Document processing status enumeration."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(str, Enum):
    """Risk level enumeration for clauses."""
    LOW = "low"
    MODERATE = "moderate"
    ATTENTION = "attention"


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    doc_id: str = Field(description="Unique document identifier")
    status: DocumentStatus = Field(description="Processing status")
    filename: str = Field(description="Original filename")
    message: str = Field(description="Status message")
    language: SupportedLanguage = Field(default=SupportedLanguage.ENGLISH, description="Document language")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClauseSummary(BaseModel):
    """Summary model for individual clauses."""
    clause_id: str = Field(description="Unique clause identifier")
    order: int = Field(description="Clause order in document", ge=1)
    category: str = Field(description="Clause category/type")
    risk_level: RiskLevel = Field(description="Risk assessment level")
    summary: str = Field(description="Plain-language summary")
    language: SupportedLanguage = Field(default=SupportedLanguage.ENGLISH, description="Summary language")
    readability_metrics: 'ReadabilityMetrics' = Field(description="Readability analysis metrics")
    needs_review: bool = Field(description="Flagged for manual review")


class ReadabilityMetrics(BaseModel):
    """Readability metrics for clauses."""
    original_grade: float = Field(description="Original grade level")
    summary_grade: float = Field(description="Summary grade level") 
    delta: float = Field(description="Grade level improvement")
    flesch_score: float = Field(description="Flesch Reading Ease score")


class ClauseDetail(BaseModel):
    """Detailed model for individual clauses."""
    clause_id: str = Field(description="Unique clause identifier")
    doc_id: str = Field(description="Parent document identifier")
    order: int = Field(description="Clause order in document", ge=1)
    category: str = Field(description="Clause category/type")
    risk_level: RiskLevel = Field(description="Risk assessment level")
    original_text: str = Field(description="Original clause text (potentially masked)")
    summary: str = Field(description="Plain-language summary")
    language: SupportedLanguage = Field(default=SupportedLanguage.ENGLISH, description="Summary and content language")
    readability_metrics: ReadabilityMetrics = Field(description="Readability analysis")
    needs_review: bool = Field(description="Flagged for manual review")
    negotiation_tip: Optional[str] = Field(description="Optional negotiation suggestion")


class DocumentMetadata(BaseModel):
    """Document metadata model."""
    doc_id: str = Field(description="Unique document identifier")
    filename: str = Field(description="Original filename")
    file_size: int = Field(description="File size in bytes")
    page_count: int = Field(description="Number of pages")
    status: DocumentStatus = Field(description="Processing status")
    language: SupportedLanguage = Field(default=SupportedLanguage.ENGLISH, description="Document analysis language")
    created_at: datetime = Field(description="Upload timestamp")
    processed_at: Optional[datetime] = Field(description="Processing completion timestamp")
    masked: bool = Field(description="Whether PII was detected and masked")
    session_id: Optional[str] = Field(description="Session identifier")


class ProcessingProgress(BaseModel):
    """Model for tracking document processing progress."""
    doc_id: str = Field(description="Document identifier")
    stage: str = Field(description="Current processing stage")
    progress: float = Field(description="Progress percentage", ge=0, le=1)
    message: str = Field(description="Progress message")
    estimated_completion: Optional[datetime] = Field(description="Estimated completion time")
    error_message: Optional[str] = Field(description="Error message if failed")


class BatchUploadResponse(BaseModel):
    """Response model for batch document upload."""
    uploads: List[DocumentUploadResponse] = Field(description="List of upload responses")
    successful_count: int = Field(description="Number of successful uploads")
    failed_count: int = Field(description="Number of failed uploads")
    total_count: int = Field(description="Total number of files processed")