"""
Document processing endpoints
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from uuid import uuid4
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from PyPDF2 import PdfReader

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.document import (
    DocumentUploadResponse,
    BatchUploadResponse,
    DocumentStatus,
    ClauseSummary,
    ClauseDetail,
    RiskLevel,
    ReadabilityMetrics,
    SupportedLanguage
)
from app.services.document_orchestrator import DocumentOrchestrator
from app.dependencies.services import get_document_orchestrator

router = APIRouter()
logger = get_logger(__name__)


def validate_pdf_page_count(file_content: bytes, filename: str, max_pages: int) -> int:
    """
    Validate PDF page count using PyPDF2.
    
    Args:
        file_content: PDF file content as bytes
        filename: Original filename for error messages
        max_pages: Maximum allowed pages
        
    Returns:
        Number of pages in the PDF
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Create a BytesIO object from file content
        pdf_stream = io.BytesIO(file_content)
        pdf_reader = PdfReader(pdf_stream)
        page_count = len(pdf_reader.pages)
        
        logger.info(f"PDF validation - {filename}: {page_count} pages (max: {max_pages})")
        
        if page_count > max_pages:
            raise HTTPException(
                status_code=422,
                detail=f"Document has {page_count} pages, but maximum allowed is {max_pages} pages. Please upload a shorter document."
            )
        
        return page_count
        
    except HTTPException:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Failed to validate PDF page count for {filename}: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid PDF file. Please ensure the file is a valid PDF document."
        )


async def process_document_background(
    doc_id: str,
    file_content: bytes,
    filename: str,
    mime_type: str,
    orchestrator: DocumentOrchestrator,
    language: SupportedLanguage = SupportedLanguage.ENGLISH,
    session_id: Optional[str] = None
):
    """Background task to process document."""
    try:
        logger.info(f"Starting background processing for document {doc_id}")
        result = await orchestrator.process_document_complete(
            doc_id, file_content, filename, mime_type, session_id, language
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
    language: SupportedLanguage = Form(SupportedLanguage.ENGLISH),
    session_id: Optional[str] = Form(None),
    settings: Settings = Depends(get_settings),
    orchestrator: DocumentOrchestrator = Depends(get_document_orchestrator)
) -> DocumentUploadResponse:
    """
    Ingest a legal document for processing.

    Args:
        background_tasks: FastAPI background tasks
        file: PDF or DOCX file to process
        language: Language for document analysis (default: English)
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
    
    # Validate page count for PDF files
    page_count = 0
    if file.content_type == "application/pdf":
        page_count = validate_pdf_page_count(file_content, file.filename, settings.MAX_PAGES)
    
    # Generate document ID
    doc_id = str(uuid4())
    
    try:
        # Create document record immediately to avoid race conditions
        await orchestrator.firestore_client.create_document(
            doc_id, file.filename, len(file_content), page_count, session_id, language
        )
        
        # Start background processing
        background_tasks.add_task(
            process_document_background,
            doc_id,
            file_content,
            file.filename,
            file.content_type,
            orchestrator,
            language,
            session_id
        )
        
        logger.info(f"Document ingestion queued: {doc_id}")
        
        return DocumentUploadResponse(
            doc_id=doc_id,
            filename=file.filename,
            status=DocumentStatus.PROCESSING,
            language=language,
            message="Document uploaded and queued for processing"
        )
        
    except Exception as e:
        logger.error(f"Failed to create document record: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create document record: {str(e)}"
        )


@router.post("/ingest/batch", response_model=BatchUploadResponse)
async def ingest_documents_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    language: SupportedLanguage = Form(SupportedLanguage.ENGLISH),
    session_id: Optional[str] = Form(None),
    max_concurrent: Optional[int] = Form(3),
    settings: Settings = Depends(get_settings),
    orchestrator: DocumentOrchestrator = Depends(get_document_orchestrator)
) -> BatchUploadResponse:
    """
    Ingest multiple legal documents for parallel processing.
    
    Args:
        background_tasks: FastAPI background tasks
        files: List of PDF or DOCX files to process
        session_id: Optional session ID for tracking
        max_concurrent: Maximum number of documents to process concurrently (default: 3)
        
    Returns:
        List of document IDs and processing statuses
        
    Raises:
        HTTPException: If file validation fails
    """
    from app.services.document_queue_manager import get_queue_manager
    
    logger.info(f"Batch document ingestion started: {len(files)} files")
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > settings.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum batch size: {settings.MAX_BATCH_SIZE}"
        )
    
    # Validate max_concurrent parameter
    if max_concurrent and (max_concurrent < 1 or max_concurrent > 10):
        raise HTTPException(
            status_code=400,
            detail="max_concurrent must be between 1 and 10"
        )
    
    # Get or update queue manager
    queue_manager = get_queue_manager()
    if max_concurrent:
        await queue_manager.update_concurrency(max_concurrent)
    
    responses = []
    
    for file in files:
        try:
            # Validate individual file
            if not file.filename:
                responses.append(DocumentUploadResponse(
                    doc_id="",
                    filename="unknown",
                    status=DocumentStatus.FAILED,
                    language=language,
                    message="No filename provided"
                ))
                continue
            
            # Check file size
            file_content = await file.read()
            if len(file_content) > settings.max_file_size_bytes:
                responses.append(DocumentUploadResponse(
                    doc_id="",
                    filename=file.filename,
                    status=DocumentStatus.FAILED,
                    language=language,
                    message=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
                ))
                continue
            
            # Check file type
            allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
            if file.content_type not in allowed_types:
                responses.append(DocumentUploadResponse(
                    doc_id="",
                    filename=file.filename,
                    status=DocumentStatus.FAILED,
                    language=language,
                    message="Only PDF and DOCX files are supported"
                ))
                continue
            
            # Validate page count for PDF files
            page_count = 0
            if file.content_type == "application/pdf":
                try:
                    page_count = validate_pdf_page_count(file_content, file.filename, settings.MAX_PAGES)
                except HTTPException as e:
                    responses.append(DocumentUploadResponse(
                        doc_id="",
                        filename=file.filename,
                        status=DocumentStatus.FAILED,
                        language=language,
                        message=e.detail
                    ))
                    continue
            
            # Generate document ID
            doc_id = str(uuid4())
            
            try:
                # Create document record immediately to avoid race conditions
                await orchestrator.firestore_client.create_document(
                    doc_id, file.filename, len(file_content), page_count, session_id, language
                )
                
                # Add to queue for processing
                await queue_manager.add_to_queue(
                    doc_id=doc_id,
                    filename=file.filename,
                    file_size=len(file_content),
                    mime_type=file.content_type,
                    session_id=session_id
                )
                
                # Start background processing with queue management
                await queue_manager.start_processing(
                    doc_id,
                    process_document_background,
                    doc_id,
                    file_content,
                    file.filename,
                    file.content_type,
                    orchestrator,
                    language,
                    session_id
                )
                
                responses.append(DocumentUploadResponse(
                    doc_id=doc_id,
                    filename=file.filename,
                    status=DocumentStatus.PROCESSING,
                    language=language,
                    message="Document uploaded and queued for processing"
                ))
                
                logger.info(f"Document queued for batch processing: {doc_id} ({file.filename})")
                
            except Exception as e:
                logger.error(f"Failed to create document record for {file.filename}: {e}")
                responses.append(DocumentUploadResponse(
                    doc_id="",
                    filename=file.filename,
                    status=DocumentStatus.FAILED,
                    language=language,
                    message=f"Failed to create document record: {str(e)}"
                ))
                
        except Exception as e:
            logger.error(f"Unexpected error processing file {file.filename}: {e}")
            responses.append(DocumentUploadResponse(
                doc_id="",
                filename=file.filename or "unknown",
                status=DocumentStatus.FAILED,
                language=language,
                message=f"Unexpected error: {str(e)}"
            ))
    
    successful_uploads = sum(1 for r in responses if r.status == DocumentStatus.PROCESSING)
    failed_uploads = sum(1 for r in responses if r.status == DocumentStatus.FAILED)
    
    logger.info(f"Batch upload completed: {successful_uploads}/{len(files)} successful")
    
    return BatchUploadResponse(
        uploads=responses,
        successful_count=successful_uploads,
        failed_count=failed_uploads,
        total_count=len(files)
    )


@router.get("/queue/status")
async def get_queue_status() -> Dict[str, Any]:
    """
    Get overall document processing queue status.
    
    Returns:
        Queue status information including counts and processing metrics
    """
    from app.services.document_queue_manager import get_queue_manager
    
    queue_manager = get_queue_manager()
    queue_status = await queue_manager.get_queue_status()
    
    return {
        "queue_status": {
            "total_items": queue_status.total_items,
            "queued_items": queue_status.queued_items,
            "processing_items": queue_status.processing_items,
            "completed_items": queue_status.completed_items,
            "failed_items": queue_status.failed_items,
            "max_concurrent": queue_status.max_concurrent,
            "avg_processing_time": queue_status.avg_processing_time,
            "estimated_wait_time": queue_status.estimated_wait_time
        }
    }


@router.get("/queue/items")
async def get_queue_items() -> Dict[str, Any]:
    """
    Get all items currently in the processing queue.
    
    Returns:
        List of queue items with their status and metadata
    """
    from app.services.document_queue_manager import get_queue_manager
    
    queue_manager = get_queue_manager()
    queue_items = await queue_manager.get_queue_items()
    
    return {
        "queue_items": [
            {
                "doc_id": item.doc_id,
                "filename": item.filename,
                "file_size": item.file_size,
                "mime_type": item.mime_type,
                "session_id": item.session_id,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
                "started_at": item.started_at.isoformat() if item.started_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "processing_time": item.processing_time,
                "wait_time": item.wait_time,
                "progress": item.progress,
                "error_message": item.error_message
            }
            for item in queue_items
        ]
    }


@router.get("/queue/item/{doc_id}")
async def get_queue_item(doc_id: str) -> Dict[str, Any]:
    """
    Get specific queue item by document ID.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        Queue item information or error if not found
    """
    from app.services.document_queue_manager import get_queue_manager
    
    queue_manager = get_queue_manager()
    queue_item = await queue_manager.get_queue_item(doc_id)
    
    if not queue_item:
        raise HTTPException(
            status_code=404,
            detail=f"Queue item not found for document: {doc_id}"
        )
    
    return {
        "queue_item": {
            "doc_id": queue_item.doc_id,
            "filename": queue_item.filename,
            "file_size": queue_item.file_size,
            "mime_type": queue_item.mime_type,
            "session_id": queue_item.session_id,
            "status": queue_item.status,
            "created_at": queue_item.created_at.isoformat(),
            "started_at": queue_item.started_at.isoformat() if queue_item.started_at else None,
            "completed_at": queue_item.completed_at.isoformat() if queue_item.completed_at else None,
            "processing_time": queue_item.processing_time,
            "wait_time": queue_item.wait_time,
            "progress": queue_item.progress,
            "error_message": queue_item.error_message
        }
    }


@router.post("/queue/cancel/{doc_id}")
async def cancel_processing(doc_id: str) -> Dict[str, Any]:
    """
    Cancel processing for a specific document.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        Cancellation result
    """
    from app.services.document_queue_manager import get_queue_manager
    
    queue_manager = get_queue_manager()
    cancelled = await queue_manager.cancel_processing(doc_id)
    
    if cancelled:
        return {"message": f"Processing cancelled for document: {doc_id}"}
    else:
        return {"message": f"Unable to cancel processing for document: {doc_id} (may already be completed)"}


@router.get("/status/{doc_id}")
async def get_document_status(
    doc_id: str,
    settings: Settings = Depends(get_settings),
    orchestrator: DocumentOrchestrator = Depends(get_document_orchestrator)
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
    language: Optional[SupportedLanguage] = None,
    settings: Settings = Depends(get_settings),
    orchestrator: DocumentOrchestrator = Depends(get_document_orchestrator)
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
            readability_metrics_data = clause_data.get("readability_metrics", {})

            summary = ClauseSummary(
                clause_id=clause_data.get("clause_id", ""),
                order=clause_data.get("order", 0),
                category=clause_data.get("category", "Other"),
                risk_level=clause_data.get("risk_level", "moderate"),
                summary=clause_data.get("summary", ""),
                language=clause_data.get("language", SupportedLanguage.ENGLISH.value),  # Use stored language from Firestore
                readability_metrics=ReadabilityMetrics(
                    original_grade=readability_metrics_data.get("original_grade", 0.0),
                    summary_grade=readability_metrics_data.get("summary_grade", 0.0),
                    delta=readability_metrics_data.get("delta", 0.0),
                    flesch_score=readability_metrics_data.get("flesch_score", 0.0)
                ),
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
    language: Optional[SupportedLanguage] = None,
    settings: Settings = Depends(get_settings),
    orchestrator: DocumentOrchestrator = Depends(get_document_orchestrator)
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
            language=clause_data.get("language", SupportedLanguage.ENGLISH.value),  # Use stored language from Firestore
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