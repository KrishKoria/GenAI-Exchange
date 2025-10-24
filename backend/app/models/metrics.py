"""
Pydantic models for analytics metrics responses.

These models define the structure for metrics data retrieved from BigQuery
and served via the /api/v1/metrics endpoints.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MetricsSummary(BaseModel):
    """
    Summary metrics for the analytics dashboard.
    
    Provides real-time counts and statistics for the last 24 hours.
    """
    total_documents: int = Field(description="Total documents uploaded in period")
    total_clauses: int = Field(description="Total clauses analyzed in period")
    total_questions: int = Field(description="Total questions asked in period")
    total_risks: int = Field(description="Total high-risk clauses detected in period")
    
    avg_processing_time_ms: float = Field(description="Average document processing time (milliseconds)")
    avg_response_time_ms: float = Field(description="Average Q&A response time (milliseconds)")
    avg_confidence: float = Field(description="Average answer confidence score (0.0-1.0)")
    
    high_risk_percentage: float = Field(description="Percentage of clauses flagged as high-risk")
    
    period_start: datetime = Field(description="Start of metrics period")
    period_end: datetime = Field(description="End of metrics period")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of last update")


class TrendDataPoint(BaseModel):
    """Single data point in a time series trend."""
    timestamp: datetime = Field(description="Time bucket timestamp")
    value: float = Field(description="Metric value for this time bucket")
    label: str = Field(description="Human-readable label (e.g., '10:00 AM', 'Mon')")


class EventTypeTrend(BaseModel):
    """Trend data for a specific event type."""
    event_type: str = Field(description="Event type identifier")
    data_points: List[TrendDataPoint] = Field(description="Time series data points")
    total_count: int = Field(description="Total events in period")


class MetricsTrends(BaseModel):
    """
    Time series trends for analytics metrics.
    
    Provides hourly/daily aggregated data for visualization.
    """
    event_trends: List[EventTypeTrend] = Field(description="Event count trends by type")
    
    processing_time_trend: List[TrendDataPoint] = Field(description="Document processing time trend")
    response_time_trend: List[TrendDataPoint] = Field(description="Q&A response time trend")
    confidence_trend: List[TrendDataPoint] = Field(description="Average confidence score trend")
    
    risk_distribution: Dict[str, int] = Field(description="Risk level distribution (low/moderate/attention)")
    category_distribution: Dict[str, int] = Field(description="Clause category distribution")
    
    period_start: datetime = Field(description="Start of trend period")
    period_end: datetime = Field(description="End of trend period")
    granularity: str = Field(description="Time bucket granularity (hourly/daily)")


class RiskDistribution(BaseModel):
    """Distribution of risk levels across analyzed clauses."""
    low: int = Field(description="Count of low-risk clauses")
    moderate: int = Field(description="Count of moderate-risk clauses")
    attention: int = Field(description="Count of high-risk (attention) clauses")
    total: int = Field(description="Total clauses analyzed")


class CategoryBreakdown(BaseModel):
    """Breakdown of clauses by category."""
    category: str = Field(description="Clause category name")
    count: int = Field(description="Number of clauses in this category")
    avg_risk_score: float = Field(description="Average risk score for this category")
    high_risk_count: int = Field(description="Number of high-risk clauses in this category")


class MetricsDetails(BaseModel):
    """
    Detailed metrics with breakdowns and distributions.
    
    Provides deeper insights for analytics drill-down.
    """
    summary: MetricsSummary = Field(description="Summary metrics")
    risk_distribution: RiskDistribution = Field(description="Risk level breakdown")
    top_categories: List[CategoryBreakdown] = Field(description="Top 10 clause categories by count")
    
    recent_documents: List[Dict] = Field(description="Recent document uploads (last 10)")
    recent_high_risks: List[Dict] = Field(description="Recent high-risk detections (last 10)")
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)
