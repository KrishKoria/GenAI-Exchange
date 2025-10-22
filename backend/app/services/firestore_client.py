"""
Firestore integration service for document and clause storage
"""
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import GoogleAPIError, NotFound

from app.core.config import get_settings
from app.core.logging import get_logger, LogContext, log_execution_time
from app.models.document import DocumentStatus, RiskLevel

logger = get_logger(__name__)


class FirestoreError(Exception):
    """Custom exception for Firestore operations."""
    pass


class FirestoreClient:
    """Service for managing document and clause data in Firestore."""
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[firestore.Client] = None
        self._db: Optional[firestore.Client] = None
        self._initialized = False
    
    @property
    def db(self) -> firestore.Client:
        """Lazy initialization of Firestore client with connection pooling."""
        if self._db is None or not self._initialized:
            try:
                # Configure client with connection pooling for better performance
                self._client = firestore.Client(
                    project=self.settings.PROJECT_ID,
                    database=self.settings.FIRESTORE_DATABASE
                )
                self._db = self._client
                self._initialized = True
                logger.info("Firestore client initialized with connection pooling")
            except Exception as e:
                logger.error(f"Failed to initialize Firestore client: {e}")
                raise FirestoreError(f"Firestore initialization failed: {e}")
        
        return self._db
    
    def close(self):
        """Close the Firestore client connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._initialized = False
            logger.info("Firestore client connection closed")
    
    # Document Operations
    
    async def create_document(
        self,
        doc_id: str,
        filename: str,
        file_size: int,
        page_count: int,
        session_id: Optional[str] = None,
        language: Optional[str] = "en"
    ) -> Dict[str, Any]:
        """
        Create a new document record.
        
        Args:
            doc_id: Unique document identifier
            filename: Original filename
            file_size: File size in bytes
            page_count: Number of pages
            session_id: Optional session identifier
            
        Returns:
            Created document data
        """
        with LogContext(logger, doc_id=doc_id, filename=filename):
            logger.info("Creating document record")
            
            document_data = {
                "doc_id": doc_id,
                "filename": filename,
                "file_size": file_size,
                "page_count": page_count,
                "status": DocumentStatus.PROCESSING.value,
                "language": language,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "processed_at": None,
                "masked": False,
                "session_id": session_id,
                "clause_count": 0,
                "processing_metadata": {}
            }
            
            try:
                doc_ref = self.db.collection("documents").document(doc_id)
                doc_ref.set(document_data)
                
                logger.info(f"Document record created: {doc_id}")
                return document_data
                
            except GoogleAPIError as e:
                logger.error(f"Failed to create document: {e}")
                raise FirestoreError(f"Failed to create document: {e}")
    
    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get document by ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Document data or None if not found
        """
        try:
            doc_ref = self.db.collection("documents").document(doc_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return None
                
        except GoogleAPIError as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            raise FirestoreError(f"Failed to get document: {e}")
    
    async def update_document_status(
        self, 
        doc_id: str, 
        status: DocumentStatus,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update document processing status.
        
        Args:
            doc_id: Document identifier
            status: New status
            metadata: Optional metadata to update
            
        Returns:
            True if update successful
        """
        with LogContext(logger, doc_id=doc_id, status=status.value):
            try:
                doc_ref = self.db.collection("documents").document(doc_id)
                
                # First check if document exists
                doc = doc_ref.get()
                if not doc.exists:
                    logger.error(f"Document {doc_id} does not exist for status update")
                    raise FirestoreError(f"Document {doc_id} not found for status update")
                
                update_data = {
                    "status": status.value,
                    "updated_at": firestore.SERVER_TIMESTAMP
                }
                
                if status == DocumentStatus.COMPLETED:
                    update_data["processed_at"] = firestore.SERVER_TIMESTAMP
                
                if metadata:
                    update_data.update(metadata)
                
                doc_ref.update(update_data)
                
                logger.info(f"Document status updated: {doc_id} -> {status.value}")
                return True
                
            except NotFound as e:
                logger.error(f"Document {doc_id} not found for status update: {e}")
                raise FirestoreError(f"Document {doc_id} not found for status update")
            except GoogleAPIError as e:
                logger.error(f"Failed to update document status: {e}")
                raise FirestoreError(f"Failed to update document status: {e}")
    
    # Clause Operations
    
    async def create_clauses(
        self, 
        doc_id: str, 
        clauses_data: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Create multiple clause records for a document.
        
        Args:
            doc_id: Parent document identifier
            clauses_data: List of clause data dictionaries
            
        Returns:
            List of created clause IDs
        """
        with LogContext(logger, doc_id=doc_id, clause_count=len(clauses_data)):
            logger.info("Creating clause records")
            
            batch = self.db.batch()
            clause_ids = []
            
            try:
                # Get document reference for the subcollection
                doc_ref = self.db.collection("documents").document(doc_id)
                clauses_collection = doc_ref.collection("clauses")
                
                for i, clause_data in enumerate(clauses_data):
                    clause_id = clause_data.get("clause_id", f"{doc_id}_clause_{i}")
                    clause_ref = clauses_collection.document(clause_id)
                    
                    # Prepare clause data with timestamps
                    firestore_clause_data = {
                        "clause_id": clause_id,
                        "doc_id": doc_id,
                        "order": clause_data.get("order", i + 1),
                        "original_text": clause_data.get("original_text", ""),
                        "summary": clause_data.get("summary", ""),
                        "category": clause_data.get("category", "Other"),
                        "risk_level": clause_data.get("risk_level", "moderate"),
                        "needs_review": clause_data.get("needs_review", False),
                        "readability_metrics": clause_data.get("readability_metrics", {}),
                        "negotiation_tip": clause_data.get("negotiation_tip"),
                        "language": clause_data.get("language", "en"),
                        "confidence": clause_data.get("confidence", 0.5),
                        "processing_method": clause_data.get("processing_method", "unknown"),
                        "created_at": firestore.SERVER_TIMESTAMP,
                        "updated_at": firestore.SERVER_TIMESTAMP,
                        "embedding": clause_data.get("embedding"),  # Vector embedding (optional)
                        "metadata": clause_data.get("metadata", {})
                    }
                    
                    batch.set(clause_ref, firestore_clause_data)
                    clause_ids.append(clause_id)
                
                # Commit the batch
                batch.commit()
                
                # Update document clause count
                await self._update_clause_count(doc_id, len(clause_ids))
                
                logger.info(f"Created {len(clause_ids)} clause records")
                return clause_ids
                
            except GoogleAPIError as e:
                logger.error(f"Failed to create clauses: {e}")
                raise FirestoreError(f"Failed to create clauses: {e}")
    
    async def get_document_clauses(
        self, 
        doc_id: str, 
        order_by: str = "order"
    ) -> List[Dict[str, Any]]:
        """
        Get all clauses for a document.
        
        Args:
            doc_id: Document identifier
            order_by: Field to order by (default: "order")
            
        Returns:
            List of clause data dictionaries
        """
        try:
            doc_ref = self.db.collection("documents").document(doc_id)
            clauses_collection = doc_ref.collection("clauses")
            
            # Query clauses ordered by the specified field
            query = clauses_collection.order_by(order_by)
            clauses = query.stream()
            
            clause_list = []
            for clause in clauses:
                clause_data = clause.to_dict()
                clause_list.append(clause_data)
            
            logger.info(f"Retrieved {len(clause_list)} clauses for document {doc_id}")
            return clause_list
            
        except GoogleAPIError as e:
            logger.error(f"Failed to get clauses for document {doc_id}: {e}")
            raise FirestoreError(f"Failed to get clauses: {e}")
    
    async def get_clause(self, doc_id: str, clause_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific clause by ID.
        
        Args:
            doc_id: Document identifier
            clause_id: Clause identifier
            
        Returns:
            Clause data or None if not found
        """
        try:
            doc_ref = self.db.collection("documents").document(doc_id)
            clause_ref = doc_ref.collection("clauses").document(clause_id)
            
            clause = clause_ref.get()
            
            if clause.exists:
                return clause.to_dict()
            else:
                return None
                
        except GoogleAPIError as e:
            logger.error(f"Failed to get clause {clause_id}: {e}")
            raise FirestoreError(f"Failed to get clause: {e}")
    
    async def update_clause_embeddings(
        self, 
        doc_id: str, 
        embeddings_data: Dict[str, List[float]]
    ) -> bool:
        """
        Update embeddings for multiple clauses with automatic batching.
        
        Firestore limits:
        - Maximum 500 writes per transaction/batch
        - Maximum 10 MiB request size
        
        This method automatically chunks updates to respect these limits.
        Uses a conservative batch size to account for embedding vector size
        and Firestore overhead.
        
        Args:
            doc_id: Document identifier
            embeddings_data: Dict mapping clause_id to embedding vector
            
        Returns:
            True if all updates successful
            
        Raises:
            FirestoreError: If any batch fails to commit
        """
        MAX_WRITES_PER_BATCH = 50
        
        with LogContext(logger, doc_id=doc_id, embedding_count=len(embeddings_data)):
            logger.info("Updating clause embeddings")
            
            # Log embedding dimensions for debugging
            if embeddings_data:
                sample_embedding = next(iter(embeddings_data.values()))
                embedding_dim = len(sample_embedding) if sample_embedding else 0
                logger.info(f"Embedding dimensions: {embedding_dim}")
            
            try:
                doc_ref = self.db.collection("documents").document(doc_id)
                clauses_collection = doc_ref.collection("clauses")
                
                # Convert dict to list of items for chunking
                embedding_items = list(embeddings_data.items())
                total_items = len(embedding_items)
                
                # Calculate number of batches needed
                num_batches = (total_items + MAX_WRITES_PER_BATCH - 1) // MAX_WRITES_PER_BATCH
                
                if num_batches > 1:
                    logger.info(f"Splitting {total_items} updates into {num_batches} batches "
                              f"(max {MAX_WRITES_PER_BATCH} per batch)")
                
                # Process in chunks
                successful_batches = 0
                failed_batches = []
                
                for batch_num in range(num_batches):
                    start_idx = batch_num * MAX_WRITES_PER_BATCH
                    end_idx = min(start_idx + MAX_WRITES_PER_BATCH, total_items)
                    chunk = embedding_items[start_idx:end_idx]
                    
                    logger.debug(f"Processing batch {batch_num + 1}/{num_batches} "
                               f"({len(chunk)} items, indices {start_idx}-{end_idx-1})")
                    
                    # Create a new batch for this chunk
                    batch = self.db.batch()
                    
                    for clause_id, embedding in chunk:
                        clause_ref = clauses_collection.document(clause_id)
                        batch.update(clause_ref, {
                            "embedding": embedding,
                            "updated_at": firestore.SERVER_TIMESTAMP
                        })
                    
                    # Commit this batch
                    try:
                        batch.commit()
                        successful_batches += 1
                        logger.debug(f"Successfully committed batch {batch_num + 1}/{num_batches}")
                    except GoogleAPIError as batch_error:
                        failed_batches.append({
                            "batch_num": batch_num + 1,
                            "start_idx": start_idx,
                            "end_idx": end_idx,
                            "chunk_size": len(chunk),
                            "error": str(batch_error)
                        })
                        logger.error(f"Failed to commit batch {batch_num + 1}/{num_batches} "
                                   f"with {len(chunk)} items: {batch_error}")
                        # If we're still hitting the size limit, we need to reduce batch size further
                        if "too big" in str(batch_error).lower():
                            logger.warning(f"Batch size of {len(chunk)} still too large. "
                                         f"Consider reducing MAX_WRITES_PER_BATCH further.")
                
                # Report results
                if failed_batches:
                    error_msg = (f"Failed to update some embeddings: {successful_batches}/{num_batches} "
                               f"batches succeeded. Failed batches: {failed_batches}")
                    logger.error(error_msg)
                    raise FirestoreError(error_msg)
                
                logger.info(f"Successfully updated embeddings for {len(embeddings_data)} clauses "
                          f"in {num_batches} batch(es)")
                return True
                
            except FirestoreError:
                # Re-raise FirestoreError as-is
                raise
            except GoogleAPIError as e:
                logger.error(f"Failed to update embeddings: {e}")
                raise FirestoreError(f"Failed to update embeddings: {e}")
            except Exception as e:
                logger.error(f"Unexpected error updating embeddings: {e}")
                raise FirestoreError(f"Unexpected error updating embeddings: {e}")
    
    # Query Operations
    
    async def get_clauses_by_risk_level(
        self, 
        doc_id: str, 
        risk_level: RiskLevel
    ) -> List[Dict[str, Any]]:
        """
        Get clauses filtered by risk level.
        
        Args:
            doc_id: Document identifier
            risk_level: Risk level to filter by
            
        Returns:
            List of clauses with specified risk level
        """
        try:
            doc_ref = self.db.collection("documents").document(doc_id)
            clauses_collection = doc_ref.collection("clauses")
            
            query = clauses_collection.where(
                filter=FieldFilter("risk_level", "==", risk_level.value)
            ).order_by("order")
            
            clauses = query.stream()
            
            clause_list = []
            for clause in clauses:
                clause_data = clause.to_dict()
                clause_list.append(clause_data)
            
            return clause_list
            
        except GoogleAPIError as e:
            logger.error(f"Failed to get clauses by risk level: {e}")
            raise FirestoreError(f"Failed to get clauses by risk level: {e}")
    
    async def get_clauses_needing_review(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Get clauses that need manual review.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            List of clauses needing review
        """
        try:
            doc_ref = self.db.collection("documents").document(doc_id)
            clauses_collection = doc_ref.collection("clauses")
            
            query = clauses_collection.where(
                filter=FieldFilter("needs_review", "==", True)
            ).order_by("order")
            
            clauses = query.stream()
            
            clause_list = []
            for clause in clauses:
                clause_data = clause.to_dict()
                clause_list.append(clause_data)
            
            return clause_list
            
        except GoogleAPIError as e:
            logger.error(f"Failed to get clauses needing review: {e}")
            raise FirestoreError(f"Failed to get clauses needing review: {e}")
    
    # Analytics and Aggregation
    
    async def get_document_statistics(self, doc_id: str) -> Dict[str, Any]:
        """
        Get aggregated statistics for a document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Document statistics
        """
        try:
            # Get document info
            document = await self.get_document(doc_id)
            if not document:
                raise FirestoreError(f"Document {doc_id} not found")
            
            # Get all clauses
            clauses = await self.get_document_clauses(doc_id)
            
            # Calculate statistics
            risk_distribution = {"low": 0, "moderate": 0, "attention": 0}
            category_distribution = {}
            needs_review_count = 0
            total_confidence = 0
            readability_improvements = []
            
            for clause in clauses:
                # Risk distribution
                risk_level = clause.get("risk_level", "moderate")
                if risk_level in risk_distribution:
                    risk_distribution[risk_level] += 1
                
                # Category distribution
                category = clause.get("category", "Other")
                category_distribution[category] = category_distribution.get(category, 0) + 1
                
                # Review flags
                if clause.get("needs_review", False):
                    needs_review_count += 1
                
                # Confidence
                total_confidence += clause.get("confidence", 0.5)
                
                # Readability improvements
                readability = clause.get("readability_metrics", {})
                if "delta" in readability:
                    readability_improvements.append(readability["delta"])
            
            stats = {
                "doc_id": doc_id,
                "total_clauses": len(clauses),
                "risk_distribution": risk_distribution,
                "category_distribution": category_distribution,
                "needs_review_count": needs_review_count,
                "avg_confidence": total_confidence / len(clauses) if clauses else 0,
                "avg_readability_improvement": (
                    sum(readability_improvements) / len(readability_improvements) 
                    if readability_improvements else 0
                ),
                "document_status": document.get("status"),
                "processing_completed": document.get("processed_at") is not None,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get document statistics: {e}")
            raise FirestoreError(f"Failed to get document statistics: {e}")
    
    # Session Operations
    
    async def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new session record.
        
        Args:
            session_id: Optional session ID (generates UUID if not provided)
            
        Returns:
            Session ID
        """
        if session_id is None:
            session_id = str(uuid4())
        
        try:
            session_data = {
                "session_id": session_id,
                "created_at": firestore.SERVER_TIMESTAMP,
                "last_activity": firestore.SERVER_TIMESTAMP,
                "locale": "en",  # Default locale
                "document_count": 0,
                "qa_count": 0
            }
            
            session_ref = self.db.collection("sessions").document(session_id)
            session_ref.set(session_data)
            
            logger.info(f"Session created: {session_id}")
            return session_id
            
        except GoogleAPIError as e:
            logger.error(f"Failed to create session: {e}")
            raise FirestoreError(f"Failed to create session: {e}")
    
    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update session last activity timestamp.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if update successful
        """
        try:
            session_ref = self.db.collection("sessions").document(session_id)
            session_ref.update({
                "last_activity": firestore.SERVER_TIMESTAMP
            })
            
            return True
            
        except GoogleAPIError as e:
            logger.error(f"Failed to update session activity: {e}")
            return False
    
    # Private helper methods
    
    async def _update_clause_count(self, doc_id: str, count: int) -> bool:
        """Update the clause count in the document record."""
        try:
            doc_ref = self.db.collection("documents").document(doc_id)
            doc_ref.update({
                "clause_count": count,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            return True
        except Exception as e:
            logger.warning(f"Failed to update clause count: {e}")
            return False
    
    # Negotiation Operations
    
    async def save_negotiation_history(
        self,
        negotiation_id: str,
        history_data: Dict[str, Any]
    ) -> bool:
        """
        Save negotiation history to Firestore.
        
        Args:
            negotiation_id: Unique negotiation identifier
            history_data: Negotiation history data
            
        Returns:
            True if successful
        """
        with LogContext(logger, negotiation_id=negotiation_id):
            logger.info("Saving negotiation history")
            
            try:
                # Add timestamps
                history_data["created_at"] = history_data.get("created_at", firestore.SERVER_TIMESTAMP)
                history_data["updated_at"] = firestore.SERVER_TIMESTAMP
                
                # Save to negotiations collection
                self.db.collection("negotiations").document(negotiation_id).set(
                    history_data,
                    merge=True
                )
                
                logger.info("Negotiation history saved successfully")
                return True
                
            except GoogleAPIError as e:
                logger.error(f"Google API error saving negotiation: {e}", exc_info=True)
                raise FirestoreError(f"Failed to save negotiation: {e}")
            except Exception as e:
                logger.error(f"Failed to save negotiation history: {e}", exc_info=True)
                raise FirestoreError(f"Failed to save negotiation: {e}")
    
    async def get_negotiation_history(
        self,
        doc_id: str,
        clause_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve negotiation history for a document or clause.
        
        Args:
            doc_id: Document identifier
            clause_id: Optional clause identifier to filter by
            
        Returns:
            List of negotiation history entries
        """
        with LogContext(logger, doc_id=doc_id, clause_id=clause_id):
            logger.info("Retrieving negotiation history")
            
            try:
                # Build query - simplified to avoid composite index requirement
                query = self.db.collection("negotiations").where(
                    filter=FieldFilter("doc_id", "==", doc_id)
                )
                
                # Filter by clause if specified
                if clause_id:
                    query = query.where(
                        filter=FieldFilter("clause_id", "==", clause_id)
                    )
                
                # Execute query (no order_by to avoid composite index)
                docs = query.stream()
                
                # Convert to list
                history = []
                for doc in docs:
                    data = doc.to_dict()
                    data["negotiation_id"] = doc.id
                    history.append(data)
                
                # Sort in-memory by created_at (descending - newest first)
                history.sort(key=lambda x: x.get("created_at", 0), reverse=True)
                
                logger.info(f"Retrieved {len(history)} negotiation entries")
                return history
                
            except GoogleAPIError as e:
                logger.error(f"Google API error retrieving negotiations: {e}", exc_info=True)
                raise FirestoreError(f"Failed to retrieve negotiations: {e}")
            except Exception as e:
                logger.error(f"Failed to retrieve negotiation history: {e}", exc_info=True)
                raise FirestoreError(f"Failed to retrieve negotiations: {e}")
    
    # Health check
    
    async def health_check(self) -> bool:
        """
        Check if Firestore is accessible.
        
        Returns:
            True if Firestore is healthy
        """
        try:
            # Simple read operation to test connectivity
            collections = self.db.collections()
            list(collections)  # Force evaluation
            return True
        except Exception as e:
            logger.error(f"Firestore health check failed: {e}")
            return False