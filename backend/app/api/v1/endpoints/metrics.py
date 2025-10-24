"""
Metrics and analytics endpoints
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.models.metrics import MetricsSummary, MetricsTrends, MetricsDetails
from app.services.metrics_service import get_metrics_service, MetricsService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    hours: int = Query(default=24, ge=1, le=168, description="Number of hours to analyze (max 7 days)"),
    settings: Settings = Depends(get_settings),
    metrics_service: MetricsService = Depends(get_metrics_service)
) -> MetricsSummary:
    """
    Get aggregated metrics summary for the analytics dashboard.
    
    Retrieves real-time metrics from BigQuery including:
    - Total counts for documents, clauses, questions, risks
    - Average processing times and confidence scores
    - High-risk percentage
    
    Args:
        hours: Number of hours to analyze (1-168, default: 24)
        
    Returns:
        MetricsSummary: Aggregated KPIs and statistics
    """
    logger.info(f"Fetching metrics summary for last {hours} hours")
    
    try:
        summary = await metrics_service.get_summary_metrics(hours=hours)
        logger.info(f"Retrieved summary: {summary.total_documents} docs, {summary.total_clauses} clauses")
        return summary
    except Exception as e:
        logger.error(f"Failed to fetch metrics summary: {e}", exc_info=True)
        # Return empty metrics on error
        return MetricsSummary(
            total_documents=0,
            total_clauses=0,
            total_questions=0,
            total_risks=0,
            avg_processing_time_ms=0.0,
            avg_response_time_ms=0.0,
            avg_confidence=0.0,
            high_risk_percentage=0.0,
            period_start=datetime.utcnow() - timedelta(hours=hours),
            period_end=datetime.utcnow()
        )


@router.get("/trends", response_model=MetricsTrends)
async def get_metrics_trends(
    hours: int = Query(default=24, ge=1, le=168, description="Number of hours to analyze"),
    granularity: str = Query(default="hourly", regex="^(hourly|daily)$", description="Time bucket granularity"),
    metrics_service: MetricsService = Depends(get_metrics_service)
) -> MetricsTrends:
    """
    Get time series trends for analytics visualization.
    
    Provides hourly or daily aggregated data for charts:
    - Event count trends by type
    - Processing/response time trends
    - Confidence score trends
    - Risk and category distributions
    
    Args:
        hours: Number of hours to analyze (1-168)
        granularity: Time bucket size - 'hourly' or 'daily'
        
    Returns:
        MetricsTrends: Time series data for visualization
    """
    logger.info(f"Fetching metrics trends: {hours}h, {granularity}")
    
    try:
        trends = await metrics_service.get_trends(hours=hours, granularity=granularity)
        return trends
    except Exception as e:
        logger.error(f"Failed to fetch metrics trends: {e}", exc_info=True)
        # Return empty trends on error
        return MetricsTrends(
            event_trends=[],
            processing_time_trend=[],
            response_time_trend=[],
            confidence_trend=[],
            risk_distribution={},
            category_distribution={},
            period_start=datetime.utcnow() - timedelta(hours=hours),
            period_end=datetime.utcnow(),
            granularity=granularity
        )


@router.get("/details", response_model=MetricsDetails)
async def get_metrics_details(
    hours: int = Query(default=24, ge=1, le=168, description="Number of hours to analyze"),
    metrics_service: MetricsService = Depends(get_metrics_service)
) -> MetricsDetails:
    """
    Get detailed metrics with breakdowns and distributions.
    
    Provides comprehensive analytics including:
    - Summary metrics
    - Risk level distribution
    - Top 10 clause categories
    - Recent documents and high-risk detections
    
    Args:
        hours: Number of hours to analyze (1-168)
        
    Returns:
        MetricsDetails: Comprehensive analytics data
    """
    logger.info(f"Fetching detailed metrics for last {hours} hours")
    
    try:
        details = await metrics_service.get_detailed_metrics(hours=hours)
        return details
    except Exception as e:
        logger.error(f"Failed to fetch detailed metrics: {e}", exc_info=True)
        raise


@router.get("/processing-stats")
async def get_processing_stats(
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """
    Get detailed processing statistics.
    
    Returns:
        Detailed processing performance metrics
    """
    # TODO: Query BigQuery events table for real stats
    
    return {
        "model_performance": {
            "gemini_model": settings.GEMINI_MODEL_NAME,
            "avg_tokens_prompt": 2840,
            "avg_tokens_output": 1650,
            "avg_latency_ms": 2100,
            "cost_per_document": 0.15
        },
        "service_health": {
            "document_ai_uptime": 0.99,
            "vertex_ai_uptime": 0.98,
            "firestore_uptime": 1.0,
            "dlp_api_uptime": 0.97
        },
        "error_rates": {
            "document_parsing_errors": 0.04,
            "clause_segmentation_errors": 0.02,
            "summarization_errors": 0.01,
            "embedding_errors": 0.005
        }
    }


@router.get("/risk-patterns")
async def get_risk_patterns(
    category: str = Query(None, description="Filter by risk category"),
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """
    Get anonymized risk pattern insights.
    
    Args:
        category: Optional category filter
        
    Returns:
        Aggregated risk pattern analysis
    """
    # TODO: Query BigQuery for aggregated risk patterns
    
    return {
        "category_filter": category,
        "risk_patterns": [
            {
                "pattern": "unlimited liability",
                "frequency": 23,
                "avg_risk_score": 0.89,
                "common_contexts": ["indemnification", "damages", "breach"]
            },
            {
                "pattern": "automatic renewal", 
                "frequency": 18,
                "avg_risk_score": 0.74,
                "common_contexts": ["term", "notice", "cancellation"]
            },
            {
                "pattern": "exclusive jurisdiction",
                "frequency": 15,
                "avg_risk_score": 0.68,
                "common_contexts": ["disputes", "courts", "venue"]
            }
        ],
        "recommendations": [
            "Consider flagging 'unlimited' clauses for higher review priority",
            "Auto-renewal clauses often lack clear notice requirements", 
            "Jurisdiction clauses may favor the service provider"
        ]
    }


@router.get("/user-comprehension")
async def get_comprehension_metrics(
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """
    Get user comprehension improvement metrics (stretch feature).
    
    Returns:
        Comprehension quiz and feedback metrics
    """
    # TODO: Implement comprehension tracking
    
    return {
        "feature_status": "not_implemented",
        "planned_metrics": [
            "quiz_score_improvement",
            "reading_time_reduction", 
            "confidence_rating_increase",
            "follow_up_questions_decrease"
        ]
    }