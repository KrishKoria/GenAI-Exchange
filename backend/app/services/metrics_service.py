"""
Metrics Service for querying analytics data from BigQuery.

Provides methods to fetch summary metrics, trends, and detailed breakdowns
from the BigQuery events table for the analytics dashboard.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from google.cloud import bigquery
from google.cloud.bigquery import QueryJob

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.metrics import (
    MetricsSummary,
    MetricsTrends,
    MetricsDetails,
    TrendDataPoint,
    EventTypeTrend,
    RiskDistribution,
    CategoryBreakdown
)

logger = get_logger(__name__)


class MetricsService:
    """
    Service for retrieving analytics metrics from BigQuery.
    
    Executes SQL queries against the BigQuery events table and transforms
    results into Pydantic models for API responses.
    """
    
    def __init__(self):
        """Initialize BigQuery client and table references."""
        settings = get_settings()
        
        self.client = bigquery.Client(project=settings.PROJECT_ID)
        self.dataset_id = settings.BIGQUERY_DATASET
        self.table_id = settings.BIGQUERY_TABLE
        self.table_path = f"{settings.PROJECT_ID}.{self.dataset_id}.{self.table_id}"
        
        logger.info(f"MetricsService initialized with table: {self.table_path}")
    
    async def get_summary_metrics(
        self,
        hours: int = 24
    ) -> MetricsSummary:
        """
        Get summary metrics for the specified time period.
        
        Args:
            hours: Number of hours to look back (default: 24)
            
        Returns:
            MetricsSummary with aggregated counts and averages
        """
        period_start = datetime.utcnow() - timedelta(hours=hours)
        period_end = datetime.utcnow()
        
        query = f"""
        SELECT
            COUNTIF(event_type = 'document_uploaded') as total_documents,
            COUNTIF(event_type = 'clause_analyzed') as total_clauses,
            COUNTIF(event_type = 'question_asked') as total_questions,
            COUNTIF(event_type = 'risk_detected') as total_risks,
            
            AVG(IF(event_type = 'document_uploaded', 
                CAST(JSON_VALUE(event_data, '$.processing_time_ms') AS INT64), 
                NULL)) as avg_processing_time_ms,
            
            AVG(IF(event_type = 'question_asked', 
                CAST(JSON_VALUE(event_data, '$.response_time_ms') AS INT64), 
                NULL)) as avg_response_time_ms,
            
            AVG(IF(event_type = 'question_asked', 
                CAST(JSON_VALUE(event_data, '$.answer_confidence') AS FLOAT64), 
                NULL)) as avg_confidence,
            
            SAFE_DIVIDE(
                COUNTIF(event_type = 'risk_detected'),
                COUNTIF(event_type = 'clause_analyzed')
            ) * 100 as high_risk_percentage
            
        FROM `{self.table_path}`
        WHERE timestamp >= TIMESTAMP(@period_start)
          AND timestamp < TIMESTAMP(@period_end)
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("period_start", "TIMESTAMP", period_start),
                bigquery.ScalarQueryParameter("period_end", "TIMESTAMP", period_end),
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if not results:
            # Return empty metrics if no data
            return MetricsSummary(
                total_documents=0,
                total_clauses=0,
                total_questions=0,
                total_risks=0,
                avg_processing_time_ms=0.0,
                avg_response_time_ms=0.0,
                avg_confidence=0.0,
                high_risk_percentage=0.0,
                period_start=period_start,
                period_end=period_end
            )
        
        row = results[0]
        
        return MetricsSummary(
            total_documents=row.total_documents or 0,
            total_clauses=row.total_clauses or 0,
            total_questions=row.total_questions or 0,
            total_risks=row.total_risks or 0,
            avg_processing_time_ms=row.avg_processing_time_ms or 0.0,
            avg_response_time_ms=row.avg_response_time_ms or 0.0,
            avg_confidence=row.avg_confidence or 0.0,
            high_risk_percentage=row.high_risk_percentage or 0.0,
            period_start=period_start,
            period_end=period_end
        )
    
    async def get_trends(
        self,
        hours: int = 24,
        granularity: str = "hourly"
    ) -> MetricsTrends:
        """
        Get time series trends for visualization.
        
        Args:
            hours: Number of hours to look back
            granularity: 'hourly' or 'daily' time buckets
            
        Returns:
            MetricsTrends with time series data
        """
        period_start = datetime.utcnow() - timedelta(hours=hours)
        period_end = datetime.utcnow()
        
        # Determine time bucket format
        if granularity == "hourly":
            time_bucket = "TIMESTAMP_TRUNC(timestamp, HOUR)"
            format_string = "%Y-%m-%d %H:00"
        else:
            time_bucket = "TIMESTAMP_TRUNC(timestamp, DAY)"
            format_string = "%Y-%m-%d"
        
        # Query for event trends
        events_query = f"""
        SELECT
            event_type,
            {time_bucket} as time_bucket,
            COUNT(*) as event_count
        FROM `{self.table_path}`
        WHERE timestamp >= TIMESTAMP(@period_start)
          AND timestamp < TIMESTAMP(@period_end)
        GROUP BY event_type, time_bucket
        ORDER BY event_type, time_bucket
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("period_start", "TIMESTAMP", period_start),
                bigquery.ScalarQueryParameter("period_end", "TIMESTAMP", period_end),
            ]
        )
        
        query_job = self.client.query(events_query, job_config=job_config)
        events_results = list(query_job.result())
        
        # Group by event type
        event_trends_dict: Dict[str, List[TrendDataPoint]] = {}
        event_totals: Dict[str, int] = {}
        
        for row in events_results:
            event_type = row.event_type
            if event_type not in event_trends_dict:
                event_trends_dict[event_type] = []
                event_totals[event_type] = 0
            
            event_trends_dict[event_type].append(
                TrendDataPoint(
                    timestamp=row.time_bucket,
                    value=float(row.event_count),
                    label=row.time_bucket.strftime(format_string)
                )
            )
            event_totals[event_type] += row.event_count
        
        event_trends = [
            EventTypeTrend(
                event_type=event_type,
                data_points=data_points,
                total_count=event_totals[event_type]
            )
            for event_type, data_points in event_trends_dict.items()
        ]
        
        # Query for risk and category distributions
        dist_query = f"""
        SELECT
            JSON_VALUE(event_data, '$.risk_level') as risk_level,
            JSON_VALUE(event_data, '$.category') as category,
            COUNT(*) as count
        FROM `{self.table_path}`
        WHERE timestamp >= TIMESTAMP(@period_start)
          AND timestamp < TIMESTAMP(@period_end)
          AND event_type = 'clause_analyzed'
        GROUP BY risk_level, category
        """
        
        dist_job = self.client.query(dist_query, job_config=job_config)
        dist_results = list(dist_job.result())
        
        risk_distribution: Dict[str, int] = {"low": 0, "moderate": 0, "attention": 0}
        category_distribution: Dict[str, int] = {}
        
        for row in dist_results:
            if row.risk_level:
                risk_distribution[row.risk_level] = risk_distribution.get(row.risk_level, 0) + row.count
            if row.category:
                category_distribution[row.category] = category_distribution.get(row.category, 0) + row.count
        
        return MetricsTrends(
            event_trends=event_trends,
            processing_time_trend=[],  # Simplified for MVP
            response_time_trend=[],
            confidence_trend=[],
            risk_distribution=risk_distribution,
            category_distribution=category_distribution,
            period_start=period_start,
            period_end=period_end,
            granularity=granularity
        )
    
    async def get_detailed_metrics(
        self,
        hours: int = 24
    ) -> MetricsDetails:
        """
        Get detailed metrics with breakdowns and recent events.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            MetricsDetails with comprehensive analytics
        """
        summary = await self.get_summary_metrics(hours)
        
        period_start = datetime.utcnow() - timedelta(hours=hours)
        period_end = datetime.utcnow()
        
        # Risk distribution query
        risk_query = f"""
        SELECT
            JSON_VALUE(event_data, '$.risk_level') as risk_level,
            COUNT(*) as count
        FROM `{self.table_path}`
        WHERE timestamp >= TIMESTAMP(@period_start)
          AND timestamp < TIMESTAMP(@period_end)
          AND event_type = 'clause_analyzed'
        GROUP BY risk_level
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("period_start", "TIMESTAMP", period_start),
                bigquery.ScalarQueryParameter("period_end", "TIMESTAMP", period_end),
            ]
        )
        
        risk_job = self.client.query(risk_query, job_config=job_config)
        risk_results = list(risk_job.result())
        
        risk_counts = {"low": 0, "moderate": 0, "attention": 0}
        for row in risk_results:
            if row.risk_level in risk_counts:
                risk_counts[row.risk_level] = row.count
        
        total_clauses = sum(risk_counts.values())
        
        risk_distribution = RiskDistribution(
            low=risk_counts["low"],
            moderate=risk_counts["moderate"],
            attention=risk_counts["attention"],
            total=total_clauses
        )
        
        # Category breakdown query
        category_query = f"""
        SELECT
            JSON_VALUE(event_data, '$.category') as category,
            COUNT(*) as count,
            AVG(CAST(JSON_VALUE(event_data, '$.risk_score') AS FLOAT64)) as avg_risk_score,
            COUNTIF(CAST(JSON_VALUE(event_data, '$.risk_score') AS FLOAT64) >= 0.7) as high_risk_count
        FROM `{self.table_path}`
        WHERE timestamp >= TIMESTAMP(@period_start)
          AND timestamp < TIMESTAMP(@period_end)
          AND event_type = 'clause_analyzed'
        GROUP BY category
        ORDER BY count DESC
        LIMIT 10
        """
        
        cat_job = self.client.query(category_query, job_config=job_config)
        cat_results = list(cat_job.result())
        
        top_categories = [
            CategoryBreakdown(
                category=row.category or "Unknown",
                count=row.count,
                avg_risk_score=row.avg_risk_score or 0.0,
                high_risk_count=row.high_risk_count or 0
            )
            for row in cat_results
        ]
        
        return MetricsDetails(
            summary=summary,
            risk_distribution=risk_distribution,
            top_categories=top_categories,
            recent_documents=[],  # Simplified for MVP
            recent_high_risks=[]
        )


# Singleton instance
_metrics_service: Optional[MetricsService] = None


def get_metrics_service() -> MetricsService:
    """Get or create the singleton MetricsService instance."""
    global _metrics_service
    
    if _metrics_service is None:
        _metrics_service = MetricsService()
    
    return _metrics_service
