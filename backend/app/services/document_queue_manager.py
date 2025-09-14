"""
Document queue manager for handling concurrent document processing
"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import time
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.models.document import DocumentStatus

logger = get_logger(__name__)


class QueueItemStatus(str, Enum):
    """Queue item status enumeration."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueueItem:
    """Represents a document in the processing queue."""
    doc_id: str
    filename: str
    file_size: int
    mime_type: str
    session_id: Optional[str] = None
    status: QueueItemStatus = QueueItemStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    
    @property
    def processing_time(self) -> Optional[float]:
        """Calculate processing time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None
    
    @property
    def wait_time(self) -> float:
        """Calculate wait time in queue in seconds."""
        start_time = self.started_at or datetime.utcnow()
        return (start_time - self.created_at).total_seconds()


@dataclass
class QueueStatus:
    """Overall queue status information."""
    total_items: int
    queued_items: int
    processing_items: int
    completed_items: int
    failed_items: int
    max_concurrent: int
    avg_processing_time: Optional[float] = None
    estimated_wait_time: Optional[float] = None


class DocumentQueueManager:
    """Manages document processing queue with concurrency control."""
    
    def __init__(self, max_concurrent: int = 3):
        """
        Initialize the document queue manager.
        
        Args:
            max_concurrent: Maximum number of documents to process concurrently
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue_items: Dict[str, QueueItem] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        
        logger.info(f"DocumentQueueManager initialized with max_concurrent={max_concurrent}")
    
    async def add_to_queue(
        self,
        doc_id: str,
        filename: str,
        file_size: int,
        mime_type: str,
        session_id: Optional[str] = None
    ) -> QueueItem:
        """
        Add a document to the processing queue.
        
        Args:
            doc_id: Document identifier
            filename: Original filename
            file_size: File size in bytes
            mime_type: File MIME type
            session_id: Optional session ID
            
        Returns:
            Created queue item
        """
        async with self._lock:
            queue_item = QueueItem(
                doc_id=doc_id,
                filename=filename,
                file_size=file_size,
                mime_type=mime_type,
                session_id=session_id
            )
            
            self.queue_items[doc_id] = queue_item
            
            logger.info(f"Added document to queue: {doc_id} ({filename})")
            return queue_item
    
    async def start_processing(
        self,
        doc_id: str,
        processing_function,
        *args,
        **kwargs
    ) -> asyncio.Task:
        """
        Start processing a document with concurrency control.
        
        Args:
            doc_id: Document identifier
            processing_function: Async function to process the document
            *args: Arguments for processing function
            **kwargs: Keyword arguments for processing function
            
        Returns:
            Processing task
        """
        async def _process_with_queue_management():
            """Internal wrapper for processing with queue management."""
            async with self.semaphore:
                try:
                    # Update status to processing
                    await self._update_item_status(doc_id, QueueItemStatus.PROCESSING)
                    
                    # Execute the processing function
                    result = await processing_function(*args, **kwargs)
                    
                    # Update status to completed
                    await self._update_item_status(doc_id, QueueItemStatus.COMPLETED)
                    
                    return result
                    
                except Exception as e:
                    # Update status to failed
                    await self._update_item_status(
                        doc_id, 
                        QueueItemStatus.FAILED, 
                        error_message=str(e)
                    )
                    raise
                finally:
                    # Clean up the processing task reference
                    async with self._lock:
                        self.processing_tasks.pop(doc_id, None)
        
        # Create and store the processing task
        task = asyncio.create_task(_process_with_queue_management())
        
        async with self._lock:
            self.processing_tasks[doc_id] = task
        
        logger.info(f"Started processing document: {doc_id}")
        return task
    
    async def _update_item_status(
        self,
        doc_id: str,
        status: QueueItemStatus,
        error_message: Optional[str] = None,
        progress: Optional[float] = None
    ):
        """Update queue item status."""
        async with self._lock:
            if doc_id not in self.queue_items:
                return
            
            item = self.queue_items[doc_id]
            item.status = status
            
            now = datetime.utcnow()
            
            if status == QueueItemStatus.PROCESSING and not item.started_at:
                item.started_at = now
            elif status in [QueueItemStatus.COMPLETED, QueueItemStatus.FAILED]:
                item.completed_at = now
            
            if error_message:
                item.error_message = error_message
            
            if progress is not None:
                item.progress = progress
    
    async def get_queue_status(self) -> QueueStatus:
        """Get overall queue status."""
        async with self._lock:
            items = list(self.queue_items.values())
        
        total_items = len(items)
        queued_items = sum(1 for item in items if item.status == QueueItemStatus.QUEUED)
        processing_items = sum(1 for item in items if item.status == QueueItemStatus.PROCESSING)
        completed_items = sum(1 for item in items if item.status == QueueItemStatus.COMPLETED)
        failed_items = sum(1 for item in items if item.status == QueueItemStatus.FAILED)
        
        # Calculate average processing time for completed items
        completed_times = [
            item.processing_time for item in items 
            if item.status == QueueItemStatus.COMPLETED and item.processing_time
        ]
        avg_processing_time = sum(completed_times) / len(completed_times) if completed_times else None
        
        # Estimate wait time for queued items
        estimated_wait_time = None
        if queued_items > 0 and avg_processing_time:
            # Simple estimation: (queue position / max_concurrent) * avg_processing_time
            estimated_wait_time = (queued_items / self.max_concurrent) * avg_processing_time
        
        return QueueStatus(
            total_items=total_items,
            queued_items=queued_items,
            processing_items=processing_items,
            completed_items=completed_items,
            failed_items=failed_items,
            max_concurrent=self.max_concurrent,
            avg_processing_time=avg_processing_time,
            estimated_wait_time=estimated_wait_time
        )
    
    async def get_queue_items(self) -> List[QueueItem]:
        """Get all queue items."""
        async with self._lock:
            return list(self.queue_items.values())
    
    async def get_queue_item(self, doc_id: str) -> Optional[QueueItem]:
        """Get specific queue item."""
        async with self._lock:
            return self.queue_items.get(doc_id)
    
    async def remove_completed_items(self, older_than_hours: int = 24):
        """Remove completed items older than specified hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        
        async with self._lock:
            items_to_remove = [
                doc_id for doc_id, item in self.queue_items.items()
                if item.status in [QueueItemStatus.COMPLETED, QueueItemStatus.FAILED]
                and item.completed_at and item.completed_at < cutoff_time
            ]
            
            for doc_id in items_to_remove:
                del self.queue_items[doc_id]
        
        if items_to_remove:
            logger.info(f"Removed {len(items_to_remove)} old completed items from queue")
    
    async def cancel_processing(self, doc_id: str) -> bool:
        """Cancel processing for a specific document."""
        async with self._lock:
            task = self.processing_tasks.get(doc_id)
            if task and not task.done():
                task.cancel()
                await self._update_item_status(doc_id, QueueItemStatus.FAILED, error_message="Cancelled by user")
                return True
            return False
    
    async def update_concurrency(self, new_max_concurrent: int):
        """Update maximum concurrent processing limit."""
        if new_max_concurrent <= 0:
            raise ValueError("max_concurrent must be positive")
        
        async with self._lock:
            old_value = self.max_concurrent
            self.max_concurrent = new_max_concurrent
            # Create new semaphore with updated value
            self.semaphore = asyncio.Semaphore(new_max_concurrent)
        
        logger.info(f"Updated max_concurrent from {old_value} to {new_max_concurrent}")


# Global queue manager instance
_queue_manager: Optional[DocumentQueueManager] = None


def get_queue_manager() -> DocumentQueueManager:
    """Get or create the global queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = DocumentQueueManager()
    return _queue_manager