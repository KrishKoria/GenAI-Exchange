"""
Document processing orchestrator that coordinates all services
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from app.core.logging import get_logger, LogContext, log_execution_time
from app.models.document import DocumentStatus, RiskLevel
from app.services.document_processor_http import DocumentProcessor, DocumentProcessingError
from app.services.clause_segmenter import ClauseSegmenter, ClauseCandidate
from app.services.gemini_client import GeminiClient, GeminiError
from app.services.firestore_client import FirestoreClient, FirestoreError
from app.services.privacy_service import PrivacyService
from app.services.risk_analyzer import RiskAnalyzer, RiskAssessment
from app.services.readability_service import ReadabilityService

logger = get_logger(__name__)


class DocumentOrchestrator:
    """Orchestrates the complete document processing pipeline."""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.clause_segmenter = ClauseSegmenter()
        self.gemini_client = GeminiClient()
        self.firestore_client = FirestoreClient()
        self.privacy_service = PrivacyService()
        self.risk_analyzer = RiskAnalyzer()
        self.readability_service = ReadabilityService()
    
    async def process_document_complete(
        self, 
        doc_id: str,
        file_content: bytes,
        filename: str,
        mime_type: str,
        session_id: Optional[str] = None
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
                    file_content, filename, mime_type
                )
                processing_result["stages_completed"].append("text_extraction")
                
                # Update document with actual page count (document already created in API endpoint)
                await self.firestore_client.update_document_status(
                    doc_id, DocumentStatus.PROCESSING, 
                    {"page_count": document_data["page_count"]}
                )
                
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
                
                # Stage 4: Baseline Readability Analysis
                logger.info("Stage 4: Baseline readability analysis")
                baseline_readability = await self.readability_service.analyze_text_readability(masked_text)
                
                await self.firestore_client.update_document_readability(
                    doc_id, self.readability_service._metrics_to_dict(baseline_readability)
                )
                processing_result["stages_completed"].append("baseline_readability")
                
                # Stage 5: Gemini Summarization
                logger.info("Stage 5: AI summarization")
                summarization_results = await self.gemini_client.batch_summarize_clauses(
                    clause_candidates, include_negotiation_tips=True
                )
                processing_result["stages_completed"].append("ai_summarization")
                
                if len(summarization_results) != len(clause_candidates):
                    logger.warning(f"Summarization count mismatch: {len(summarization_results)} vs {len(clause_candidates)}")
                
                # Stage 6: Risk Analysis
                logger.info("Stage 6: Risk analysis")
                risk_assessments = []
                
                for i, (clause, summary_result) in enumerate(zip(clause_candidates, summarization_results)):
                    risk_assessment = await self.risk_analyzer.analyze_clause_risk(
                        clause.text,
                        summary_result.get("summary"),
                        summary_result.get("risk_level"),
                        summary_result.get("category")
                    )
                    risk_assessments.append(risk_assessment)
                
                processing_result["stages_completed"].append("risk_analysis")
                
                # Stage 7: Readability Comparison
                logger.info("Stage 7: Readability improvement analysis")
                readability_comparisons = []
                
                for clause, summary_result in zip(clause_candidates, summarization_results):
                    comparison = await self.readability_service.compare_readability(
                        clause.text, summary_result.get("summary", "")
                    )
                    readability_comparisons.append(comparison)
                
                processing_result["stages_completed"].append("readability_analysis")
                
                # Stage 8: Data Assembly and Storage
                logger.info("Stage 8: Assembling and storing clause data")
                
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
                processing_result["stages_completed"].append("data_storage")
                
                # Stage 9: Generate Document-Level Analytics
                logger.info("Stage 9: Document-level analytics")
                
                document_risk_profile = await self.risk_analyzer.analyze_document_risk_profile(risk_assessments)
                document_readability_analysis = await self.readability_service.analyze_document_readability(readability_comparisons)
                
                # Stage 10: Final Status Update
                logger.info("Stage 10: Final status update")
                
                final_metadata = {
                    "document_risk_profile": document_risk_profile,
                    "document_readability_analysis": document_readability_analysis,
                    "processing_statistics": {
                        "total_clauses": len(clauses_data),
                        "pii_detected": len(pii_matches),
                        "high_risk_clauses": document_risk_profile["risk_distribution"]["attention"],
                        "avg_readability_improvement": document_readability_analysis["avg_grade_level_reduction"]
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
        
        # Document AI and Gemini health checks would require test requests
        # For now, assume they're healthy if no initialization errors
        health_status["document_ai"] = True  # Could implement actual health check
        health_status["gemini"] = True      # Could implement actual health check
        
        return health_status