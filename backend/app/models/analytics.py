"""
Analytics event models for Pub/Sub event publishing.

These models define the structure of analytics events published to Google Cloud Pub/Sub
for tracking platform usage, document processing, risk detection, and Q&A interactions.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field


EventType = Literal[
    "document_uploaded",
    "clause_analyzed",
    "question_asked",
    "risk_detected"
]


class AnalyticsEvent(BaseModel):
    """
    Base class for all analytics events.
    
    All analytics events inherit from this base model and must provide:
    - event_id: Unique identifier for deduplication
    - event_type: Type of event (document_uploaded, clause_analyzed, etc.)
    - timestamp: When the event occurred (UTC)
    - processing_timestamp: When the event was published to Pub/Sub (set at publish time)
    - event_data: Type-specific event payload
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event identifier (UUID)")
    event_type: EventType = Field(description="Type of analytics event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp (UTC)")
    processing_timestamp: Optional[datetime] = Field(default=None, description="Pub/Sub publish timestamp (set at publish time)")
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data payload")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DocumentUploadedEvent(AnalyticsEvent):
    """
    Event published when a document is successfully uploaded and processed.
    
    Tracks document processing metrics including file size, page count, language,
    and processing time for performance monitoring.
    """
    
    def __init__(
        self,
        doc_id: str,
        filename_hash: str,
        page_count: int,
        language: str,
        processing_time_ms: int,
        status: str = "success",
        session_id: Optional[str] = None,
        **kwargs
    ):
        event_data = {
            "doc_id": doc_id,
            "filename_hash": filename_hash,
            "page_count": page_count,
            "language": language,
            "processing_time_ms": processing_time_ms,
            "status": status,
            "session_id": session_id
        }
        super().__init__(event_type="document_uploaded", event_data=event_data, **kwargs)



class ClauseAnalyzedEvent(AnalyticsEvent):
    """
    Event published when a clause is analyzed for risk and readability.
    
    Tracks clause-level metrics including risk scoring, confidence levels,
    and readability improvements for analytics aggregation.
    """
    
    def __init__(
        self,
        clause_id: str,
        doc_id: str,
        category: str,
        risk_level: str,
        risk_score: float,
        confidence: float,
        readability_delta: Optional[float] = None,
        session_id: Optional[str] = None,
        **kwargs
    ):
        event_data = {
            "clause_id": clause_id,
            "doc_id": doc_id,
            "category": category,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "confidence": confidence,
            "readability_delta": readability_delta,
            "session_id": session_id
        }
        super().__init__(event_type="clause_analyzed", event_data=event_data, **kwargs)



class QuestionAskedEvent(AnalyticsEvent):
    """
    Event published when a user asks a question via the Q&A system.
    
    Tracks Q&A interactions with anonymized question hashes (no PII),
    answer confidence, citation count, and response time for quality metrics.
    """
    
    def __init__(
        self,
        question_hash: str,  # SHA256 hash for anonymization
        answer_confidence: float,
        citation_count: int,
        response_time_ms: int,
        session_id: Optional[str] = None,
        **kwargs
    ):
        event_data = {
            "question_hash": question_hash,
            "answer_confidence": answer_confidence,
            "citation_count": citation_count,
            "response_time_ms": response_time_ms,
            "session_id": session_id
        }
        super().__init__(event_type="question_asked", event_data=event_data, **kwargs)



class RiskDetectedEvent(AnalyticsEvent):
    """
    Event published when high-risk clauses are detected (risk_score >= 0.7).
    
    Tracks significant risk findings with clause identifiers, risk categories,
    and detected risk factors for compliance monitoring.
    """
    
    def __init__(
        self,
        clause_id: str,
        doc_id: str,
        risk_level: str,
        risk_score: float,
        risk_factors: list,
        category: str,
        session_id: Optional[str] = None,
        **kwargs
    ):
        event_data = {
            "clause_id": clause_id,
            "doc_id": doc_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "category": category,
            "session_id": session_id
        }
        super().__init__(event_type="risk_detected", event_data=event_data, **kwargs)

