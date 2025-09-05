"""
Question and Answer endpoints
"""
import logging
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from google.cloud import firestore

from app.core.config import Settings, get_settings
from app.models.qa import QuestionRequest, AnswerResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=AnswerResponse)
async def ask_question(
    request: QuestionRequest,
    settings: Settings = Depends(get_settings)
) -> AnswerResponse:
    """
    Ask a question about document clauses.
    
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
    
    # TODO: Implement Q&A pipeline
    # 1. Generate embeddings for question
    # 2. Retrieve relevant clauses using cosine similarity
    # 3. Use Gemini with grounded prompting
    # 4. Return answer with citations
    
    # Placeholder response
    return AnswerResponse(
        answer="Based on the termination clause, either party can end the contract with 30 days written notice. The liability clause limits damages to the contract value.",
        used_clause_ids=["c1", "c3"],
        confidence=0.85,
        sources=[
            {
                "clause_id": "c1",
                "snippet": "Either party may terminate this Agreement upon thirty (30) days written notice",
                "relevance_score": 0.92
            },
            {
                "clause_id": "c3", 
                "snippet": "Total liability shall not exceed the total amount paid under this Agreement",
                "relevance_score": 0.78
            }
        ]
    )


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
        db = firestore.Client(
            project=settings.PROJECT_ID,
            database=settings.FIRESTORE_DATABASE,
        )

        query = (
            db.collection("qa_history")
            .where("doc_id", "==", doc_id)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        results: List[Dict[str, Any]] = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            ts = data.get("timestamp")
            # Convert Firestore timestamp to ISO string if present
            if hasattr(ts, "isoformat"):
                ts = ts.isoformat()
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
