"""
Question and Answer endpoints
"""
import logging
from typing import Dict, Any, List
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import SERVER_TIMESTAMP

from app.core.config import Settings, get_settings
from app.models.qa import QuestionRequest, AnswerResponse, SourceCitation
from app.services.firestore_client import FirestoreClient, FirestoreError
from app.services.embeddings_service import EmbeddingsService, EmbeddingsError
from app.services.gemini_client import GeminiClient, GeminiError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=AnswerResponse)
async def ask_question(
    request: QuestionRequest,
    settings: Settings = Depends(get_settings)
) -> AnswerResponse:
    """
    Ask a question about document clauses using vector similarity search and grounded prompting.
    
    Args:
        request: Question and document context
        
    Returns:
        Answer with supporting clause citations
        
    Raises:
        HTTPException: If document not found or question invalid
    """
    logger.info(f"Q&A request for doc_id: {request.doc_id}")
    
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        # Initialize services
        firestore_client = FirestoreClient()
        embeddings_service = EmbeddingsService()
        gemini_client = GeminiClient()
        
        # 1. Verify document exists and get its clauses
        logger.info(f"Fetching clauses for document: {request.doc_id}")
        clauses = await firestore_client.get_document_clauses(request.doc_id)
        
        if not clauses:
            raise HTTPException(
                status_code=404, 
                detail=f"No clauses found for document {request.doc_id}"
            )
        
        # 2. Filter clauses that have embeddings (should be pre-generated during document processing)
        clauses_with_embeddings = [
            clause for clause in clauses 
            if clause.get("embedding") and len(clause.get("embedding", [])) > 0
        ]
        
        if not clauses_with_embeddings:
            # Embeddings should have been generated during document processing
            # If they're missing, this indicates a processing failure or incomplete pipeline
            logger.warning(f"No embeddings found for document {request.doc_id}. Document may be incompletely processed.")
            
            # Check document status to understand why embeddings are missing
            document = await firestore_client.get_document(request.doc_id)
            if document and document.get("status") != "completed":
                raise HTTPException(
                    status_code=422,
                    detail=f"Document is not fully processed yet. Current status: {document.get('status', 'unknown')}. Please wait for processing to complete."
                )
            
            # If document is marked complete but missing embeddings, try to generate them as fallback
            logger.warning("Document marked as complete but missing embeddings. Generating embeddings as fallback.")
            try:
                await _generate_and_store_embeddings(
                    firestore_client, 
                    embeddings_service, 
                    request.doc_id, 
                    clauses
                )
                # Reload clauses with embeddings
                clauses = await firestore_client.get_document_clauses(request.doc_id)
                clauses_with_embeddings = [
                    clause for clause in clauses 
                    if clause.get("embedding") and len(clause.get("embedding", [])) > 0
                ]
            except Exception as fallback_error:
                logger.error(f"Fallback embeddings generation failed: {fallback_error}")
                raise HTTPException(
                    status_code=500,
                    detail="Document processing is incomplete. Embeddings are missing and could not be generated. Please re-upload the document."
                )
        
        if not clauses_with_embeddings:
            raise HTTPException(
                status_code=500,
                detail="No clauses with embeddings available for similarity search"
            )
        
        # 3. Find most relevant clauses using vector similarity
        logger.info(f"Searching {len(clauses_with_embeddings)} clauses for relevance")
        relevant_clauses = await embeddings_service.search_similar_clauses(
            question=request.question,
            clause_embeddings=clauses_with_embeddings,
            top_k=5,  # Get top 5 most relevant clauses
            min_similarity=0.2  # Minimum similarity threshold
        )
        
        if not relevant_clauses:
            # No relevant clauses found, return informative response
            return AnswerResponse(
                answer="I couldn't find any clauses in this document that relate to your question. Please try rephrasing your question or ask about different aspects of the document.",
                used_clause_ids=[],
                confidence=0.0,
                sources=[]
            )
        
        logger.info(f"Found {len(relevant_clauses)} relevant clauses")
        
        # 4. Use Gemini for grounded Q&A
        logger.info("Generating answer using Gemini")
        qa_result = await gemini_client.answer_question(
            question=request.question,
            relevant_clauses=relevant_clauses,
            doc_id=request.doc_id
        )
        
        # 5. Store Q&A in history
        await _store_qa_history(
            firestore_client,
            request,
            qa_result,
            relevant_clauses
        )
        
        # 6. Build response with proper source citations
        sources = []
        for clause in relevant_clauses:
            if clause.get("clause_id") in qa_result.get("used_clause_ids", []):
                # Use original text for snippet, truncate to reasonable length
                original_text = clause.get("original_text", "")
                snippet = original_text[:300] + "..." if len(original_text) > 300 else original_text
                
                sources.append(SourceCitation(
                    clause_id=clause["clause_id"],
                    clause_number=clause.get("order"),  # Use 'order' field as clause number
                    category=clause.get("category"),
                    snippet=snippet,
                    relevance_score=clause.get("similarity", 0.0)  # Use 'similarity' not 'similarity_score'
                ))
        
        return AnswerResponse(
            answer=qa_result.get("answer", ""),
            used_clause_ids=qa_result.get("used_clause_ids", []),
            confidence=qa_result.get("confidence", 0.0),
            sources=sources
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except (FirestoreError, EmbeddingsError, GeminiError) as e:
        logger.error(f"Service error in Q&A: {e}")
        raise HTTPException(status_code=500, detail=f"Q&A processing failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in Q&A: {e}")
        raise HTTPException(status_code=500, detail="Internal server error processing question")


async def _generate_and_store_embeddings(
    firestore_client: FirestoreClient,
    embeddings_service: EmbeddingsService,
    doc_id: str,
    clauses: List[Dict[str, Any]]
) -> None:
    """Generate and store embeddings for clauses that don't have them."""
    logger.info(f"Generating embeddings for {len(clauses)} clauses")
    
    # Prepare texts for embedding (use summary if available, fallback to original text)
    texts = []
    clause_ids = []
    for clause in clauses:
        text = clause.get("summary") or clause.get("original_text") or clause.get("content", "")
        if text.strip():
            texts.append(text)
            clause_ids.append(clause.get("clause_id"))
    
    if not texts:
        logger.warning("No valid text found in clauses for embedding")
        return
    
    # Generate embeddings in batches
    embeddings = await embeddings_service.generate_embeddings_batch(texts)
    
    # Store embeddings in Firestore
    embeddings_data = {}
    for clause_id, embedding in zip(clause_ids, embeddings):
        if embedding:  # Only store non-empty embeddings
            embeddings_data[clause_id] = embedding
    
    if embeddings_data:
        await firestore_client.update_clause_embeddings(doc_id, embeddings_data)
        logger.info(f"Stored embeddings for {len(embeddings_data)} clauses")


async def _store_qa_history(
    firestore_client: FirestoreClient,
    request: QuestionRequest,
    qa_result: Dict[str, Any],
    relevant_clauses: List[Dict[str, Any]]
) -> None:
    """Store Q&A interaction in history."""
    try:
        qa_id = str(uuid4())
        qa_history = {
            "qa_id": qa_id,
            "doc_id": request.doc_id,
            "question": request.question,
            "answer": qa_result.get("answer", ""),
            "clause_ids": qa_result.get("used_clause_ids", []),
            "confidence": qa_result.get("confidence", 0.0),
            "timestamp": SERVER_TIMESTAMP,
            "session_id": request.session_id,
            "relevant_clause_count": len(relevant_clauses)
        }
        
        # Store in qa_history collection
        db = firestore_client.db
        qa_ref = db.collection("qa_history").document(qa_id)
        qa_ref.set(qa_history)
        
        logger.info(f"Stored Q&A history: {qa_id}")
        
    except Exception as e:
        logger.error(f"Failed to store Q&A history: {e}")
        # Don't fail the main request if history storage fails


@router.get("/history/{doc_id}")
async def get_qa_history(
    doc_id: str,
    limit: int = 10,
    settings: Settings = Depends(get_settings)
) -> List[Dict[str, Any]]:
    """
    Get Q&A history for a document.
    
    Args:
        doc_id: Document ID
        limit: Maximum number of Q&A pairs to return
        
    Returns:
        List of previous questions and answers
    """
    try:
        firestore_client = FirestoreClient()
        db = firestore_client.db

        query = (
            db.collection("qa_history")
            .where("doc_id", "==", doc_id)
            .order_by("timestamp", direction="DESCENDING")
            .limit(limit)
        )

        results: List[Dict[str, Any]] = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            ts = data.get("timestamp")
            # Convert Firestore timestamp to ISO string if present
            if ts and hasattr(ts, "isoformat"):
                ts = ts.isoformat()
            elif ts:
                ts = str(ts)  # Fallback for other timestamp formats
            
            results.append(
                {
                    "timestamp": ts,
                    "question": data.get("question", ""),
                    "answer": data.get("answer", ""),
                    "clause_ids": data.get("clause_ids", []),
                }
            )

        return results
    except Exception as e:
        logger.error(f"Failed to fetch Q&A history for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve Q&A history")
