"""
Document processing orchestrator that coordinates all services
"""
import asyncio
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from app.core.logging import get_logger, LogContext, log_execution_time
from app.models.document import DocumentStatus, RiskLevel, SupportedLanguage
from app.services.document_processor_grpc import DocumentProcessorGRPC, DocumentProcessingError
from app.services.document_processor_http import DocumentProcessor as DocumentProcessorHTTP
from app.services.clause_segmenter import ClauseSegmenter, ClauseCandidate
from app.services.gemini_client import GeminiClient, GeminiError
from app.services.firestore_client import FirestoreClient, FirestoreError
from app.services.privacy_service import PrivacyService
from app.services.risk_analyzer import RiskAnalyzer, RiskAssessment
from app.services.readability_service import ReadabilityService
from app.services.embeddings_service import EmbeddingsService, EmbeddingsError
from app.services.language_detection_service import LanguageDetectionService

logger = get_logger(__name__)


class DocumentOrchestrator:
    """Orchestrates the complete document processing pipeline."""
    
    def __init__(self):
        self.document_processor = DocumentProcessorGRPC()
        self.document_processor_http = DocumentProcessorHTTP()
        self.clause_segmenter = ClauseSegmenter()
        self.gemini_client = GeminiClient()
        self.firestore_client = FirestoreClient()
        self.privacy_service = PrivacyService()
        self.risk_analyzer = RiskAnalyzer()
        self.readability_service = ReadabilityService()
        self.embeddings_service = EmbeddingsService()
        self.language_detection_service = LanguageDetectionService()
    
    async def process_document_complete(
        self,
        doc_id: str,
        file_content: bytes,
        filename: str,
        mime_type: str,
        session_id: Optional[str] = None,
        language: SupportedLanguage = SupportedLanguage.ENGLISH
    ) -> Dict[str, Any]:
        """
        Complete document processing pipeline.
        
        Args:
            doc_id: Document identifier
            file_content: Raw file bytes
            filename: Original filename  
            mime_type: File MIME type
            session_id: Optional session ID
            
        Returns:
            Processing result summary
        """
        start_time = asyncio.get_event_loop().time()
        
        with LogContext(logger, doc_id=doc_id, filename=filename, session_id=session_id):
            logger.info("Starting complete document processing pipeline")
            
            processing_result = {
                "doc_id": doc_id,
                "filename": filename,
                "status": "processing",
                "stages_completed": [],
                "errors": [],
                "statistics": {}
            }
            
            try:
                # Stage 1: Document Processing (Text Extraction)
                logger.info("Stage 1: Document text extraction")
                document_data = await self.document_processor.process_document(
                    file_content, filename, use_fallback=False
                )
                processing_result["stages_completed"].append("text_extraction")
                
                # Update document with actual page count (document already created in API endpoint)
                await self.firestore_client.update_document_status(
                    doc_id, DocumentStatus.PROCESSING, 
                    {"page_count": document_data["page_count"]}
                )
                
                # Stage 1.5: Language Detection (if not provided by user)
                detected_language = language
                logger.info(f"Initial language parameter: {language.value}")
                
                if language == SupportedLanguage.ENGLISH:
                    # Auto-detect language from document text
                    logger.info("Stage 1.5: Auto-detecting document language (default was English)")
                    try:
                        # Take first 2000 characters for language detection
                        sample_text = document_data["text"][:2000]
                        logger.info(f"Sample text for detection (first 100 chars): {sample_text[:100]}")
                        
                        detection_result = await self.language_detection_service.detect_language_advanced(
                            sample_text
                        )
                        detected_language = detection_result.language
                        logger.info(f"✓ DETECTED LANGUAGE: {detected_language.value} (confidence: {detection_result.confidence:.2f}, method: {detection_result.method})")
                        
                        # Update document with detected language
                        await self.firestore_client.update_document_status(
                            doc_id, DocumentStatus.PROCESSING, 
                            {
                                "language": detected_language.value,
                                "language_detection_confidence": detection_result.confidence,
                                "language_detection_method": detection_result.method.value
                            }
                        )
                    except Exception as e:
                        logger.error(f"Language detection failed, defaulting to English: {e}", exc_info=True)
                        detected_language = SupportedLanguage.ENGLISH
                else:
                    logger.info(f"Using user-provided language: {language.value}")
                
                # Use detected language for all subsequent processing
                language = detected_language
                logger.info(f"★ FINAL LANGUAGE FOR PROCESSING: {language.value} ★")
                processing_result["stages_completed"].append("language_detection")
                
                # Stage 2: Privacy Analysis and PII Masking
                logger.info("Stage 2: Privacy analysis and PII masking") 
                masked_text, pii_matches = await self.privacy_service.detect_and_mask_pii(
                    document_data["text"]
                )
                
                privacy_summary = await self.privacy_service.get_pii_summary(pii_matches)
                processing_result["stages_completed"].append("privacy_masking")
                
                # Update document with masking info
                await self.firestore_client.update_document_status(
                    doc_id, DocumentStatus.PROCESSING, 
                    {"masked": len(pii_matches) > 0, "pii_summary": privacy_summary}
                )
                
                # Stage 3: Clause Segmentation
                logger.info("Stage 3: Clause segmentation")
                
                # Use masked text for segmentation to protect privacy
                document_data_masked = document_data.copy()
                document_data_masked["text"] = masked_text
                
                clause_candidates = await self.clause_segmenter.segment_document(document_data_masked)
                
                # Identify clause types
                clause_candidates = await self.clause_segmenter.identify_clause_types(clause_candidates)
                processing_result["stages_completed"].append("clause_segmentation")
                
                if not clause_candidates:
                    raise Exception("No clauses could be extracted from document")
                
                # Stage 4: Gemini Summarization
                logger.info(f"Stage 4: AI summarization (language: {language.value})")
                summarization_results = await self.gemini_client.batch_summarize_clauses(
                    clause_candidates, include_negotiation_tips=True, language=language
                )
                processing_result["stages_completed"].append("ai_summarization")
                
                if len(summarization_results) != len(clause_candidates):
                    logger.warning(f"Summarization count mismatch: {len(summarization_results)} vs {len(clause_candidates)}")
                
                # Stages 5 & 6: Risk Analysis and Readability Comparison (Concurrent)
                logger.info("Stages 5 & 6: Risk analysis and readability analysis (concurrent)")
                
                # Create parallel tasks for risk analysis
                risk_tasks = []
                for i, (clause, summary_result) in enumerate(zip(clause_candidates, summarization_results)):
                    task = self.risk_analyzer.analyze_clause_risk(
                        clause.text,
                        summary_result.get("summary"),
                        summary_result.get("risk_level"),
                        summary_result.get("category")
                    )
                    risk_tasks.append(task)
                
                # Create parallel tasks for readability analysis
                readability_tasks = []
                for clause, summary_result in zip(clause_candidates, summarization_results):
                    task = self.readability_service.compare_readability(
                        clause.text, summary_result.get("summary", "")
                    )
                    readability_tasks.append(task)
                
                # Execute both risk and readability analyses concurrently
                risk_assessments, readability_comparisons = await asyncio.gather(
                    asyncio.gather(*risk_tasks),
                    asyncio.gather(*readability_tasks)
                )
                
                processing_result["stages_completed"].extend(["risk_analysis", "readability_analysis"])
                
                # Stage 7: Data Assembly and Storage
                logger.info(f"Stage 7: Assembling and storing clause data (language: {language.value})")
                
                clauses_data = []
                for i, (clause, summary_result, risk_assessment, readability_comp) in enumerate(
                    zip(clause_candidates, summarization_results, risk_assessments, readability_comparisons)
                ):
                    clause_data = {
                        "clause_id": f"{doc_id}_clause_{i}",
                        "order": i + 1,
                        "original_text": clause.text,  # This is already masked
                        "summary": summary_result.get("summary", ""),
                        "category": summary_result.get("category", "Other"),
                        "language": language.value,
                        "risk_level": risk_assessment.risk_level.value,
                        "needs_review": risk_assessment.needs_review,
                        "readability_metrics": {
                            "original_grade": readability_comp["original"]["flesch_kincaid_grade"],
                            "summary_grade": readability_comp["simplified"]["flesch_kincaid_grade"],
                            "delta": readability_comp["improvements"]["grade_level_delta"],
                            "flesch_score": readability_comp["simplified"]["flesch_reading_ease"]
                        },
                        "negotiation_tip": summary_result.get("negotiation_tip"),
                        "confidence": risk_assessment.confidence,
                        "processing_method": summary_result.get("processing_method", "gemini"),
                        "risk_factors": risk_assessment.risk_factors,
                        "metadata": {
                            "risk_score": risk_assessment.risk_score,
                            "detected_keywords": risk_assessment.detected_keywords,
                            "readability_improvement": readability_comp["improvements"]["overall_improvement_score"]
                        }
                    }
                    clauses_data.append(clause_data)
                
                # Store clauses in Firestore
                clause_ids = await self.firestore_client.create_clauses(doc_id, clauses_data)
                logger.info(f"✓ Stored {len(clause_ids)} clauses with language: {language.value}")
                processing_result["stages_completed"].append("data_storage")
                
                # Stage 7.5: Generate Embeddings for Clauses (Background Processing)
                logger.info("Stage 7.5: Starting background embeddings generation")
                
                # Start embeddings generation as a fire-and-forget background task
                embeddings_task = asyncio.create_task(
                    self._generate_clause_embeddings_background(doc_id, clauses_data)
                )
                
                # Don't await the task - let it run in the background
                processing_result["stages_completed"].append("embeddings_background_started")
                logger.info(f"Background embeddings generation started for {len(clauses_data)} clauses")
                
                # Stage 8: Generate Document-Level Analytics
                logger.info("Stage 8: Document-level analytics")
                
                document_risk_profile = await self.risk_analyzer.analyze_document_risk_profile(risk_assessments)
                document_readability_analysis = await self.readability_service.analyze_document_readability(readability_comparisons)
                
                # Stage 9: Final Status Update
                logger.info("Stage 9: Final status update")
                
                final_metadata = {
                    "document_risk_profile": document_risk_profile,
                    "document_readability_analysis": document_readability_analysis,
                    "processing_statistics": {
                        "total_clauses": len(clauses_data),
                        "pii_detected": len(pii_matches),
                        "high_risk_clauses": document_risk_profile["risk_distribution"]["attention"],
                        "avg_readability_improvement": document_readability_analysis["avg_grade_level_reduction"],
                        "embeddings_started": "embeddings_background_started" in processing_result["stages_completed"],
                        "embeddings_background": True,
                        "embeddings_count": 0 
                    }
                }
                
                await self.firestore_client.update_document_status(
                    doc_id, DocumentStatus.COMPLETED, final_metadata
                )
                
                processing_result["status"] = "completed"
                processing_result["statistics"] = final_metadata["processing_statistics"]
                
                # Log completion
                total_time = (asyncio.get_event_loop().time() - start_time) * 1000
                log_execution_time(logger, "complete_document_processing", total_time)
                
                logger.info(f"Document processing completed successfully: {len(clause_ids)} clauses processed")
                
                return processing_result
                
            except Exception as e:
                logger.error(f"Document processing failed at stage {len(processing_result['stages_completed'])}: {e}")
                
                processing_result["status"] = "failed"
                processing_result["errors"].append(str(e))
                
                # Update document status to failed
                try:
                    await self.firestore_client.update_document_status(
                        doc_id, DocumentStatus.FAILED, 
                        {"error": str(e), "failed_at_stage": len(processing_result["stages_completed"])}
                    )
                except Exception as update_error:
                    logger.error(f"Failed to update document status: {update_error}")
                
                # Re-raise the original exception
                raise Exception(f"Document processing failed: {e}")
    
    async def get_processing_status(self, doc_id: str) -> Dict[str, Any]:
        """
        Get detailed processing status for a document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Detailed status information
        """
        try:
            document = await self.firestore_client.get_document(doc_id)
            
            if not document:
                return {"status": "not_found", "message": "Document not found"}
            
            clauses = await self.firestore_client.get_document_clauses(doc_id)
            
            status_info = {
                "doc_id": doc_id,
                "status": document.get("status", "unknown"),
                "filename": document.get("filename", ""),
                "created_at": document.get("created_at"),
                "processed_at": document.get("processed_at"),
                "clause_count": len(clauses),
                "page_count": document.get("page_count", 0),
                "masked": document.get("masked", False),
                "pii_summary": document.get("pii_summary", {}),
                "processing_statistics": document.get("processing_statistics", {})
            }
            
            # Add progress information for processing documents
            if document.get("status") == "processing":
                status_info["progress"] = min(0.9, len(clauses) / 10 * 0.8)  # Estimate progress
                status_info["message"] = "Document is being processed"
            elif document.get("status") == "completed":
                status_info["progress"] = 1.0
                status_info["message"] = "Document processing completed successfully"
            elif document.get("status") == "failed":
                status_info["progress"] = 0.0
                status_info["message"] = "Document processing failed"
                status_info["error"] = document.get("error", "Unknown error")
            
            return status_info
            
        except Exception as e:
            logger.error(f"Failed to get processing status: {e}")
            return {"status": "error", "message": str(e)}
    
    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all integrated services.
        
        Returns:
            Service health status
        """
        health_status = {}
        
        try:
            health_status["firestore"] = await self.firestore_client.health_check()
        except Exception:
            health_status["firestore"] = False
        
        try:
            health_status["privacy_service"] = await self.privacy_service.health_check()
        except Exception:
            health_status["privacy_service"] = False
        
        health_status["document_ai"] = True  # Could implement actual health check
        health_status["gemini"] = True      # Could implement actual health check
        
        return health_status
    
    async def _generate_clause_embeddings(
        self, 
        doc_id: str, 
        clauses_data: List[Dict[str, Any]]
    ) -> int:
        """
        Generate and store embeddings for all clauses in the document.
        
        This method creates embeddings for clause summaries to enable fast similarity
        search during Q&A operations, eliminating the need to generate embeddings
        on-demand when users ask questions.
        
        Args:
            doc_id: Document identifier
            clauses_data: List of clause data dictionaries containing summaries
            
        Returns:
            Number of embeddings successfully generated and stored
            
        Raises:
            EmbeddingsError: If embeddings generation fails
        """
        with LogContext(logger, doc_id=doc_id, clause_count=len(clauses_data)):
            logger.info("Starting background embeddings generation")
            
            # Initialize timing variable for error handling
            embeddings_start_time = 0.0
            
            # Prepare texts for embedding (use summary, fallback to original text)
            texts = []
            clause_ids = []
            
            for clause_data in clauses_data:
                # Prefer summary over original text for embeddings
                text = clause_data.get("summary") or clause_data.get("original_text", "")
                if text.strip():
                    texts.append(text)
                    clause_ids.append(clause_data.get("clause_id"))
            
            if not texts:
                logger.warning("No valid text found in clauses for embedding generation")
                return 0
            
            # Generate embeddings using the batch service
            logger.info(f"Generating embeddings for {len(texts)} clause texts")
            embeddings = await self.embeddings_service.generate_embeddings_batch(texts)
            
            # Prepare embeddings data for storage
            embeddings_data = {}
            for clause_id, embedding in zip(clause_ids, embeddings):
                if embedding:  # Only store non-empty embeddings
                    embeddings_data[clause_id] = embedding
            
            if embeddings_data:
                # Store embeddings in Firestore
                await self.firestore_client.update_clause_embeddings(doc_id, embeddings_data)
                logger.info(f"Successfully stored embeddings for {len(embeddings_data)} clauses")
                return len(embeddings_data)
            else:
                raise EmbeddingsError("No valid embeddings were generated")
    
    async def _generate_clause_embeddings_background(
        self, 
        doc_id: str, 
        clauses_data: List[Dict[str, Any]]
    ) -> None:
        """
        Generate and store embeddings for all clauses in the document as a background task.
        
        This method runs in the background and updates the document status when complete.
        It handles errors gracefully without affecting the main pipeline.
        
        Args:
            doc_id: Document identifier
            clauses_data: List of clause data dictionaries containing summaries
        """
        # Initialize timing variable before try block for error handling visibility
        embeddings_start_time = 0.0
        
        try:
            with LogContext(logger, doc_id=doc_id, clause_count=len(clauses_data)):
                logger.info("Starting background embeddings generation")
                
                # Track start time for performance metrics
                embeddings_start_time = asyncio.get_event_loop().time()
                
                # Call the original embeddings method
                embeddings_count = await self._generate_clause_embeddings(doc_id, clauses_data)
                
                # Calculate processing time
                embeddings_duration = (asyncio.get_event_loop().time() - embeddings_start_time) * 1000
                
                # Calculate success/failure rates
                total_clauses = len(clauses_data)
                success_rate = (embeddings_count / total_clauses) * 100 if total_clauses > 0 else 0
                
                # Update document with successful embeddings completion (metadata only)
                await self._update_document_metadata(doc_id, {
                    "processing_statistics.embeddings_completed": True,
                    "processing_statistics.embeddings_count": embeddings_count,
                    "processing_statistics.embeddings_total_clauses": total_clauses,
                    "processing_statistics.embeddings_success_rate": success_rate,
                    "processing_statistics.embeddings_failed_count": total_clauses - embeddings_count,
                    "processing_statistics.embeddings_duration_ms": embeddings_duration,
                    "processing_statistics.embeddings_generated_at": asyncio.get_event_loop().time()
                })
                
                logger.info(f"Background embeddings generation completed: {embeddings_count}/{total_clauses} embeddings generated (Success rate: {success_rate:.1f}%)")
                
        except Exception as e:
            # Log error but don't crash - embeddings can be regenerated later
            logger.error(f"Background embeddings generation failed for document {doc_id}: {e}")
            
            try:
                # Calculate timing info even for failures
                embeddings_duration = (asyncio.get_event_loop().time() - embeddings_start_time) * 1000
                
                # Update document with failure status (metadata only)
                await self._update_document_metadata(doc_id, {
                    "processing_statistics.embeddings_completed": False,
                    "processing_statistics.embeddings_count": 0,
                    "processing_statistics.embeddings_total_clauses": len(clauses_data),
                    "processing_statistics.embeddings_success_rate": 0,
                    "processing_statistics.embeddings_failed_count": len(clauses_data),
                    "processing_statistics.embeddings_duration_ms": embeddings_duration,
                    "processing_statistics.embeddings_error": str(e),
                    "processing_statistics.embeddings_failed_at": asyncio.get_event_loop().time()
                })
            except Exception as update_error:
                logger.error(f"Failed to update embeddings failure status: {update_error}")
    
    async def _update_document_metadata(
        self, 
        doc_id: str, 
        metadata_updates: Dict[str, Any]
    ) -> bool:
        """
        Update document metadata without changing status.
        
        This is a helper method for background tasks that need to update
        document metadata without affecting the main document status.
        
        Args:
            doc_id: Document identifier
            metadata_updates: Dictionary of metadata fields to update
            
        Returns:
            True if update successful
        """
        try:
            # Use Firestore's direct update method to update only metadata
            doc_ref = self.firestore_client.db.collection("documents").document(doc_id)
            
            # Add updated timestamp - import firestore at the top if not already
            from google.cloud import firestore
            update_data = metadata_updates.copy()
            update_data["updated_at"] = firestore.SERVER_TIMESTAMP
            
            # Use Firestore's update method directly
            doc_ref.update(update_data)
            
            logger.debug(f"Updated document metadata for {doc_id}: {list(metadata_updates.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update document metadata for {doc_id}: {e}")
            return False