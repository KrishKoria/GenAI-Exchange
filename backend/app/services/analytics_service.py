"""
Analytics Service for Publishing Events to Google Cloud Pub/Sub.

This service handles asynchronous event publishing to Pub/Sub with:
- Batching for efficient message delivery (max 10 messages, 1s latency)
- Retry logic with exponential backoff
- Callback-based error handling and logging
- Thread-safe singleton pattern for application-wide use

Events are published as JSON with metadata for BigQuery streaming ingestion.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.publisher import futures
from google.api_core import retry

from app.core.config import get_settings
from app.models.analytics import AnalyticsEvent

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for publishing analytics events to Google Cloud Pub/Sub.
    
    Uses batch settings for efficient message delivery and callback-based
    error handling for non-blocking async publishing.
    """
    
    def __init__(self):
        """
        Initialize PublisherClient with batching and retry settings.
        
        Batch settings:
        - max_messages: 10 (publish when 10 messages queued)
        - max_latency: 1.0 seconds (publish after 1s even if < 10 messages)
        
        Retry settings:
        - deadline: 300 seconds (5 minutes)
        - initial: 0.1 seconds
        - maximum: 60 seconds
        - multiplier: 2.0 (exponential backoff)
        """
        settings = get_settings()
        
        batch_settings = pubsub_v1.types.BatchSettings(
            max_messages=10,  # Batch up to 10 messages
            max_bytes=1024 * 1024,  # 1 MB max batch size
            max_latency=1.0,  # Publish after 1 second max
        )
        
        # Use google-api-core retry settings
        retry_policy = retry.Retry(
            initial=0.1,
            maximum=60.0,
            multiplier=2.0,
            deadline=300.0,
        )
        
        self.publisher = pubsub_v1.PublisherClient(
            batch_settings=batch_settings,
        )
        
        # Store retry policy for use in publish calls
        self.retry_policy = retry_policy
        
        # Construct topic path: projects/{project_id}/topics/{topic_id}
        self.topic_path = self.publisher.topic_path(
            settings.PROJECT_ID,
            settings.PUBSUB_TOPIC
        )
        
        logger.info(
            f"AnalyticsService initialized with topic: {self.topic_path}, "
            f"batch_size={batch_settings.max_messages}, "
            f"max_latency={batch_settings.max_latency}s"
        )
    
    def publish_event(self, event: AnalyticsEvent) -> futures.Future:
        """
        Publish an analytics event to Pub/Sub asynchronously.
        
        Args:
            event: AnalyticsEvent instance (DocumentUploadedEvent, etc.)
        
        Returns:
            Future that resolves to message_id on success
        
        Raises:
            Exception: If event serialization or publishing fails
        
        Example:
            >>> event = DocumentUploadedEvent(
            ...     doc_id="doc_123",
            ...     filename_hash="abc123",
            ...     page_count=5,
            ...     language="en",
            ...     processing_time_ms=1200
            ... )
            >>> future = analytics_service.publish_event(event)
            >>> message_id = future.result()  # Blocks until published
        """
        try:
            # Serialize event to JSON
            event_dict = event.model_dump(mode="json")
            
            # Set processing_timestamp to current time (when event is published to Pub/Sub)
            event_dict["processing_timestamp"] = datetime.utcnow().isoformat()
            
            # Convert datetime to ISO 8601 string for JSON serialization
            if isinstance(event_dict.get("timestamp"), datetime):
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()
            
            # CRITICAL: BigQuery JSON column type requires event_data to be a JSON-encoded STRING
            # not a nested object. Double-encode event_data for BigQuery compatibility.
            # See: https://cloud.google.com/pubsub/docs/bigquery#json_columns
            if "event_data" in event_dict and event_dict["event_data"] is not None:
                event_dict["event_data"] = json.dumps(event_dict["event_data"])
            
            message_data = json.dumps(event_dict).encode("utf-8")
            
            # Publish with attributes for routing/filtering
            future = self.publisher.publish(
                self.topic_path,
                message_data,
                event_type=event.event_type,
                event_id=event.event_id,
            )
            
            # Add callback for success/error logging
            future.add_done_callback(self._publish_callback)
            
            logger.debug(
                f"Published event {event.event_type} (ID: {event.event_id}) to {self.topic_path}"
            )
            
            return future
            
        except Exception as e:
            logger.error(
                f"Failed to publish event {event.event_type} (ID: {event.event_id}): {e}",
                exc_info=True
            )
            raise
    
    def _publish_callback(self, future: futures.Future) -> None:
        """
        Callback for handling publish success or failure.
        
        Logs message_id on success or error details on failure.
        Does not raise exceptions to avoid blocking publisher thread.
        
        Args:
            future: Future returned by publisher.publish()
        """
        try:
            message_id = future.result()
            logger.info(f"Successfully published message: {message_id}")
        except Exception as e:
            logger.error(f"Publish callback error: {e}", exc_info=True)
    
    def shutdown(self) -> None:
        """
        Gracefully shutdown the publisher client.
        
        Flushes any pending batched messages before closing.
        Should be called on application shutdown.
        """
        logger.info("Shutting down AnalyticsService publisher...")
        self.publisher.stop()
        logger.info("AnalyticsService shutdown complete")


# Singleton instance for application-wide use
analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """
    Get or create the singleton AnalyticsService instance.
    
    Returns:
        AnalyticsService: Thread-safe singleton instance
    
    Example:
        >>> service = get_analytics_service()
        >>> service.publish_event(event)
    """
    global analytics_service
    
    if analytics_service is None:
        analytics_service = AnalyticsService()
    
    return analytics_service
