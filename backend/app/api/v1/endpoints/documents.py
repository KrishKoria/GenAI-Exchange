"""
Document processing endpoints
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.document import (
    DocumentUploadResponse,
    DocumentStatus,
    ClauseSummary,
    ClauseDetail,
    RiskLevel,
    ReadabilityMetrics
)
from app.services.document_orchestrator import DocumentOrchestrator

router = APIRouter()
logger = get_logger(__name__)

# Initialize orchestrator
orchestrator = DocumentOrchestrator()


async def process_document_background(
    doc_id: str,
    file_content: bytes,
    filename: str,
    mime_type: str,
    session_id: Optional[str] = None
):
    """Background task to process document."""
    try:
        logger.info(f"Starting background processing for document {doc_id}")
        result = await orchestrator.process_document_complete(
            doc_id, file_content, filename, mime_type, session_id
        )
        logger.info(f"Background processing completed successfully for {doc_id}")
        return result
    except Exception as e:
        logger.error(f"Background document processing failed for {doc_id}: {e}")
        # Ensure document status is updated to failed
        try:
            await orchestrator.firestore_client.update_document_status(
                doc_id, 
                DocumentStatus.FAILED, 
                {"error": str(e), "failed_at": "background_processing"}
            )
        except Exception as update_error:
            logger.error(f"Failed to update document status after error: {update_error}")
        raise


@router.post("/ingest", response_model=DocumentUploadResponse)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    settings: Settings = Depends(get_settings)
) -> DocumentUploadResponse:
    """
    Ingest a legal document for processing.
    
    Args:
        background_tasks: FastAPI background tasks
        file: PDF or DOCX file to process
        session_id: Optional session ID for tracking
        
    Returns:
        Document ID and processing status
        
    Raises:
        HTTPException: If file validation fails
    """
    logger.info(f"Document ingestion started: {file.filename}")
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Check file size
    file_content = await file.read()
    if len(file_content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
        )
    
    # Check file type
    allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported"
        )
    
    # Generate document ID
    doc_id = str(uuid4())
    
    try:
        # Create document record immediately to avoid race conditions
        await orchestrator.firestore_client.create_document(
            doc_id, file.filename, len(file_content), 0, session_id  # page_count will be updated later
        )
        
        # Start background processing
        background_tasks.add_task(
            process_document_background,
            doc_id,
            file_content,
            file.filename,
            file.content_type,
            session_id
        )
        
        logger.info(f"Document ingestion queued: {doc_id}")
        
        return DocumentUploadResponse(
            doc_id=doc_id,
            filename=file.filename,
            status=DocumentStatus.PROCESSING,
            message="Document uploaded and queued for processing"
        )
        
    except Exception as e:
        logger.error(f"Failed to create document record: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create document record: {str(e)}"
        )


@router.get("/status/{doc_id}")
async def get_document_status(
    doc_id: str,
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """
    Get document processing status.
    
    Args:
        doc_id: Document ID
        
    Returns:
        Document status and metadata
    """
    try:
        status_info = await orchestrator.get_processing_status(doc_id)
        return status_info
    except Exception as e:
        logger.error(f"Failed to get document status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document status: {str(e)}"
        )


@router.get("/clauses", response_model=List[ClauseSummary])
async def get_document_clauses(
    doc_id: str,
    settings: Settings = Depends(get_settings)
) -> List[ClauseSummary]:
    """
    Get clause summaries for a document.
    
    Args:
        doc_id: Document ID
        
    Returns:
        List of clause summaries with metadata
        
    Raises:
        HTTPException: If document not found
    """
    try:
        # Get clauses from Firestore
        clauses_data = await orchestrator.firestore_client.get_document_clauses(doc_id)
        
        if not clauses_data:
            # Check if document exists
            document = await orchestrator.firestore_client.get_document(doc_id)
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Document exists but no clauses yet (still processing?)
            return []
        
        # Convert to ClauseSummary models
        clause_summaries = []
        for clause_data in clauses_data:
            readability_metrics = clause_data.get("readability_metrics", {})
            
            summary = ClauseSummary(
                clause_id=clause_data.get("clause_id", ""),
                order=clause_data.get("order", 0),
                category=clause_data.get("category", "Other"),
                risk_level=clause_data.get("risk_level", "moderate"),
                summary=clause_data.get("summary", ""),
                readability_delta=readability_metrics.get("delta", 0.0),
                needs_review=clause_data.get("needs_review", False)
            )
            clause_summaries.append(summary)
        
        return clause_summaries
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document clauses: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve document clauses: {str(e)}"
        )


@router.get("/clause/{clause_id}", response_model=ClauseDetail)
async def get_clause_detail(
    clause_id: str,
    doc_id: str,
    settings: Settings = Depends(get_settings)
) -> ClauseDetail:
    """
    Get detailed information about a specific clause.
    
    Args:
        clause_id: Clause ID
        doc_id: Document ID (for validation)
        
    Returns:
        Detailed clause information
        
    Raises:
        HTTPException: If clause not found
    """
    try:
        # Get clause from Firestore
        clause_data = await orchestrator.firestore_client.get_clause(doc_id, clause_id)
        
        if not clause_data:
            raise HTTPException(status_code=404, detail="Clause not found")
        
        # Extract readability metrics
        readability_metrics_data = clause_data.get("readability_metrics", {})
        
        # Convert to ClauseDetail model
        clause_detail = ClauseDetail(
            clause_id=clause_data.get("clause_id", clause_id),
            doc_id=clause_data.get("doc_id", doc_id),
            order=clause_data.get("order", 0),
            category=clause_data.get("category", "Other"),
            risk_level=clause_data.get("risk_level", "moderate"),
            original_text=clause_data.get("original_text", ""),
            summary=clause_data.get("summary", ""),
            readability_metrics=ReadabilityMetrics(
                original_grade=readability_metrics_data.get("original_grade", 0.0),
                summary_grade=readability_metrics_data.get("summary_grade", 0.0),
                delta=readability_metrics_data.get("delta", 0.0),
                flesch_score=readability_metrics_data.get("flesch_score", 0.0)
            ),
            needs_review=clause_data.get("needs_review", False),
            negotiation_tip=clause_data.get("negotiation_tip")
        )
        
        return clause_detail
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get clause detail: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve clause detail: {str(e)}"
        )