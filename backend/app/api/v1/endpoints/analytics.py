"""
Analytics testing endpoints for event publishing verification.

Development-only endpoints to manually publish sample events to Pub/Sub
for testing the analytics pipeline (Pub/Sub → BigQuery → Dashboard).
"""

import logging
from typing import Literal
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.models.analytics import (
    DocumentUploadedEvent,
    ClauseAnalyzedEvent,
    QuestionAskedEvent,
    RiskDetectedEvent
)
from app.services.analytics_service import get_analytics_service

router = APIRouter()
logger = logging.getLogger(__name__)


class PublishEventRequest(BaseModel):
    """Request to publish a sample analytics event."""
    event_type: Literal["document_uploaded", "clause_analyzed", "question_asked", "risk_detected"]
    doc_id: str = Field(default="test_doc_123", description="Test document ID")
    session_id: str = Field(default="test_session_456", description="Test session ID")


class PublishEventResponse(BaseModel):
    """Response from event publishing."""
    success: bool
    event_id: str
    event_type: str
    message: str
    published_at: datetime = Field(default_factory=datetime.utcnow)


@router.post("/events", response_model=PublishEventResponse)
async def publish_test_event(
    request: PublishEventRequest,
    settings: Settings = Depends(get_settings)
) -> PublishEventResponse:
    """
    Publish a sample analytics event to Pub/Sub for testing.
    
    **Development Only**: This endpoint should be disabled in production
    via environment variable or removed before deployment.
    
    Args:
        request: Event type and test data
        
    Returns:
        Event publication confirmation with event_id
        
    Raises:
        HTTPException: If event publishing fails or disabled in production
        
    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/analytics/events \\
          -H "Content-Type: application/json" \\
          -d '{"event_type": "document_uploaded", "doc_id": "test_doc_123"}'
        ```
    """
    # Safety check: Disable in production
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=403,
            detail="Analytics testing endpoint disabled in production"
        )
    
    try:
        analytics_service = get_analytics_service()
        
        # Create sample event based on type
        if request.event_type == "document_uploaded":
            event = DocumentUploadedEvent(
                doc_id=request.doc_id,
                filename_hash="test_file_hash_abc123",
                page_count=5,
                language="en",
                processing_time_ms=1200,
                status="success",
                session_id=request.session_id
            )
        
        elif request.event_type == "clause_analyzed":
            event = ClauseAnalyzedEvent(
                clause_id=f"{request.doc_id}_clause_0",
                doc_id=request.doc_id,
                category="liability",
                risk_level="moderate",
                risk_score=0.65,
                confidence=0.85,
                readability_delta=-2.5,
                session_id=request.session_id
            )
        
        elif request.event_type == "question_asked":
            event = QuestionAskedEvent(
                question_hash="test_question_hash_def456",
                answer_confidence=0.92,
                citation_count=3,
                response_time_ms=850,
                session_id=request.session_id
            )
        
        elif request.event_type == "risk_detected":
            event = RiskDetectedEvent(
                clause_id=f"{request.doc_id}_clause_2",
                doc_id=request.doc_id,
                risk_level="attention",
                risk_score=0.82,
                risk_factors=["unlimited_liability", "indemnification"],
                category="indemnity",
                session_id=request.session_id
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported event type: {request.event_type}"
            )
        
        # Publish event (returns Future)
        future = analytics_service.publish_event(event)
        
        # Wait for message_id (blocks until published)
        message_id = future.result(timeout=10.0)
        
        logger.info(f"Published test event {request.event_type} (ID: {event.event_id}, Message: {message_id})")
        
        return PublishEventResponse(
            success=True,
            event_id=event.event_id,
            event_type=request.event_type,
            message=f"Successfully published {request.event_type} event to Pub/Sub (message_id: {message_id})"
        )
    
    except Exception as e:
        logger.error(f"Failed to publish test event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Event publishing failed: {str(e)}"
        )


@router.get("/events/status")
async def get_analytics_status(
    settings: Settings = Depends(get_settings)
) -> dict:
    """
    Get analytics service status and configuration.
    
    Returns:
        Service configuration and connection status
    """
    analytics_service = get_analytics_service()
    
    return {
        "status": "connected",
        "environment": settings.ENVIRONMENT,
        "project_id": settings.PROJECT_ID,
        "pubsub_topic": settings.PUBSUB_TOPIC,
        "bigquery_dataset": settings.BIGQUERY_DATASET,
        "bigquery_table": settings.BIGQUERY_TABLE,
        "topic_path": analytics_service.topic_path,
        "testing_enabled": settings.ENVIRONMENT != "production"
    }
