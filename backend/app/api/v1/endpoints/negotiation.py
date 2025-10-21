"""
Negotiation API endpoints for AI-powered clause alternative generation
"""
import logging
from typing import List, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import get_logger, LogContext
from app.models.negotiation import (
    NegotiationRequest,
    NegotiationResponse,
    BatchNegotiationRequest,
    BatchNegotiationResponse,
    SaveNegotiationRequest,
    NegotiationHistoryResponse,
    NegotiationHistory,
    QuickAlternativeRequest,
    QuickAlternativeResponse
)
from app.models.document import ClauseDetail, RiskLevel
from app.services.negotiation_service import NegotiationService
from app.services.firestore_client import FirestoreClient, FirestoreError
from app.services.gemini_client import GeminiClient
from app.services.risk_analyzer import RiskAnalyzer
from app.dependencies.services import (
    get_firestore_client,
    get_gemini_client
)

router = APIRouter()
logger = get_logger(__name__)


# Dependency to get NegotiationService
def get_negotiation_service(
    gemini_client: GeminiClient = Depends(get_gemini_client)
) -> NegotiationService:
    """Get or create NegotiationService instance."""
    risk_analyzer = RiskAnalyzer()
    return NegotiationService(
        gemini_client=gemini_client,
        risk_analyzer=risk_analyzer,
        enable_caching=True,
        cache_ttl=3600
    )


@router.post("/generate", response_model=NegotiationResponse)
async def generate_negotiation_alternatives(
    request: NegotiationRequest,
    negotiation_service: NegotiationService = Depends(get_negotiation_service),
    firestore_client: FirestoreClient = Depends(get_firestore_client),
    settings: Settings = Depends(get_settings)
):
    """
    Generate AI-powered negotiation alternatives for a single clause.
    
    This endpoint takes a contract clause and generates 3 strategic alternatives:
    - Balanced: Middle-ground approach
    - Protective: More risk-reducing approach
    - Simplified: Clearer, simpler version
    
    Each alternative includes strategic benefits, risk reduction details, and
    implementation guidance.
    """
    with LogContext(
        logger,
        clause_category=request.clause_category,
        risk_level=request.risk_level,
        has_doc_context=bool(request.document_context)
    ):
        logger.info("API request: Generate negotiation alternatives")
        
        try:
            response = await negotiation_service.generate_alternatives(
                clause_text=request.clause_text,
                clause_category=request.clause_category,
                risk_level=request.risk_level,
                document_context=request.document_context,
                user_preferences=request.user_preferences
            )
            
            # Add IDs from request if provided
            if request.clause_id:
                response.clause_id = request.clause_id
            if request.doc_id:
                response.doc_id = request.doc_id
            
            # Auto-save complete negotiation data to Firestore for history
            if response.negotiation_id and request.doc_id and request.clause_id:
                try:
                    history_entry = {
                        "negotiation_id": response.negotiation_id,
                        "doc_id": request.doc_id,
                        "clause_id": request.clause_id,
                        "original_clause": request.clause_text,
                        "alternatives": [alt.dict() for alt in response.alternatives],
                        "metadata": {
                            "clause_category": request.clause_category,
                            "risk_level": request.risk_level.value if request.risk_level else None,
                            "generation_time": response.generation_time,
                            "model_used": response.model_used
                        }
                    }
                    
                    await firestore_client.save_negotiation_history(
                        negotiation_id=response.negotiation_id,
                        history_data=history_entry
                    )
                    
                    logger.info(f"Auto-saved negotiation {response.negotiation_id} to Firestore")
                except Exception as save_error:
                    # Log but don't fail the request if save fails
                    logger.warning(f"Failed to auto-save negotiation: {save_error}")
            
            logger.info(
                "Successfully generated negotiation alternatives",
                extra={
                    "num_alternatives": len(response.alternatives),
                    "generation_time": response.generation_time
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate negotiation alternatives: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate alternatives: {str(e)}"
            )


@router.post("/quick", response_model=QuickAlternativeResponse)
async def generate_quick_alternatives(
    request: QuickAlternativeRequest,
    negotiation_service: NegotiationService = Depends(get_negotiation_service)
):
    """
    Quick alternative generation for demo purposes.
    
    Simplified endpoint that returns alternatives in a format optimized
    for quick display and demos.
    """
    logger.info("API request: Generate quick alternatives")
    
    try:
        start_time = datetime.utcnow()
        
        # Generate alternatives
        response = await negotiation_service.generate_alternatives(
            clause_text=request.clause_text,
            clause_category=request.clause_category
        )
        
        generation_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Simplify response format
        simplified_alternatives = []
        for alt in response.alternatives:
            simplified_alternatives.append({
                "text": alt.alternative_text,
                "benefit": alt.strategic_benefit,
                "type": alt.alternative_type.value,
                "risk_reduction": alt.risk_reduction
            })
        
        return QuickAlternativeResponse(
            original_clause=request.clause_text,
            alternatives=simplified_alternatives,
            generation_time=generation_time
        )
        
    except Exception as e:
        logger.error(f"Failed to generate quick alternatives: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate alternatives: {str(e)}"
        )


@router.post("/batch", response_model=BatchNegotiationResponse)
async def batch_generate_alternatives(
    request: BatchNegotiationRequest,
    background_tasks: BackgroundTasks,
    negotiation_service: NegotiationService = Depends(get_negotiation_service),
    firestore_client: FirestoreClient = Depends(get_firestore_client),
    settings: Settings = Depends(get_settings)
):
    """
    Generate negotiation alternatives for multiple clauses in batch.
    
    This endpoint processes multiple clauses concurrently and returns
    alternatives for all risky clauses (moderate and attention risk levels).
    """
    with LogContext(logger, doc_id=request.doc_id, clause_count=len(request.clause_ids)):
        logger.info("API request: Batch generate negotiation alternatives")
        
        try:
            start_time = datetime.utcnow()
            
            # Fetch clauses from Firestore
            clauses_to_process: List[ClauseDetail] = []
            for clause_id in request.clause_ids:
                try:
                    clause_data = await firestore_client.get_clause(
                        doc_id=request.doc_id,
                        clause_id=clause_id
                    )
                    
                    if clause_data:
                        clause = ClauseDetail(**clause_data)
                        # Only process clauses with moderate or attention risk
                        if clause.risk_level in [RiskLevel.MODERATE, RiskLevel.ATTENTION]:
                            clauses_to_process.append(clause)
                            
                except Exception as e:
                    logger.warning(f"Failed to fetch clause {clause_id}: {e}")
                    continue
            
            if not clauses_to_process:
                return BatchNegotiationResponse(
                    doc_id=request.doc_id,
                    total_clauses=len(request.clause_ids),
                    successful=0,
                    failed=0,
                    negotiations=[],
                    generation_time=0.0
                )
            
            # Generate alternatives for all clauses
            negotiations = await negotiation_service.generate_batch_alternatives(
                clauses=clauses_to_process,
                document_context=request.document_context,
                user_preferences=request.user_preferences,
                max_concurrent=request.max_concurrent
            )
            
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Schedule background task to save negotiations
            background_tasks.add_task(
                save_negotiations_background,
                firestore_client,
                request.doc_id,
                negotiations
            )
            
            logger.info(
                "Batch generation complete",
                extra={
                    "successful": len(negotiations),
                    "total": len(request.clause_ids),
                    "generation_time": generation_time
                }
            )
            
            return BatchNegotiationResponse(
                doc_id=request.doc_id,
                total_clauses=len(request.clause_ids),
                successful=len(negotiations),
                failed=len(clauses_to_process) - len(negotiations),
                negotiations=negotiations,
                generation_time=generation_time
            )
            
        except Exception as e:
            logger.error(f"Failed to batch generate alternatives: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to batch generate alternatives: {str(e)}"
            )


@router.post("/save")
async def save_negotiation(
    request: SaveNegotiationRequest,
    firestore_client: FirestoreClient = Depends(get_firestore_client),
    settings: Settings = Depends(get_settings)
):
    """
    Save a negotiation interaction with user feedback.
    
    This endpoint stores:
    - Which alternative (if any) the user selected
    - User feedback on the alternatives
    - Whether the alternatives were helpful
    
    This data helps improve future suggestions through the learning service.
    """
    with LogContext(
        logger,
        doc_id=request.doc_id,
        clause_id=request.clause_id,
        negotiation_id=request.negotiation_id
    ):
        logger.info("API request: Save negotiation interaction")
        
        try:
            # Prepare feedback update (merge with existing data, don't overwrite)
            feedback_update = {
                "selected_alternative_id": request.selected_alternative_id,
                "user_feedback": request.user_feedback,
                "was_helpful": request.was_helpful,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Merge metadata if provided
            if request.metadata:
                feedback_update["metadata"] = request.metadata
            
            # Save to Firestore negotiations collection (merge=True preserves existing fields)
            await firestore_client.save_negotiation_history(
                negotiation_id=request.negotiation_id,
                history_data=feedback_update
            )
            
            logger.info("Successfully saved negotiation interaction")
            
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Negotiation saved successfully",
                    "negotiation_id": request.negotiation_id
                }
            )
            
        except FirestoreError as e:
            logger.error(f"Firestore error saving negotiation: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save negotiation: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to save negotiation: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save negotiation: {str(e)}"
            )


@router.get("/history/{doc_id}", response_model=NegotiationHistoryResponse)
async def get_negotiation_history(
    doc_id: str,
    clause_id: Optional[str] = Query(None, description="Filter by clause ID"),
    firestore_client: FirestoreClient = Depends(get_firestore_client),
    settings: Settings = Depends(get_settings)
):
    """
    Retrieve negotiation history for a document or specific clause.
    
    Returns all negotiation interactions, including:
    - Generated alternatives
    - User selections
    - Feedback
    """
    with LogContext(logger, doc_id=doc_id, clause_id=clause_id):
        logger.info("API request: Get negotiation history")
        
        try:
            start_time = datetime.utcnow()
            
            # Fetch negotiations from Firestore
            negotiations_data = await firestore_client.get_negotiation_history(
                doc_id=doc_id,
                clause_id=clause_id
            )
            
            # Convert to NegotiationHistory objects
            negotiations = []
            for neg_data in negotiations_data:
                try:
                    negotiation = NegotiationHistory(**neg_data)
                    negotiations.append(negotiation)
                except Exception as e:
                    logger.warning(f"Failed to parse negotiation history: {e}")
                    continue
            
            query_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                "Retrieved negotiation history",
                extra={"count": len(negotiations), "query_time": query_time}
            )
            
            return NegotiationHistoryResponse(
                doc_id=doc_id,
                total_negotiations=len(negotiations),
                negotiations=negotiations,
                query_time=query_time
            )
            
        except FirestoreError as e:
            logger.error(f"Firestore error retrieving history: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve history: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to retrieve negotiation history: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve history: {str(e)}"
            )


@router.get("/stats/{doc_id}")
async def get_negotiation_stats(
    doc_id: str,
    firestore_client: FirestoreClient = Depends(get_firestore_client)
):
    """
    Get statistics about negotiation usage for a document.
    
    Returns:
    - Total negotiations generated
    - Alternative selection rates
    - Helpful ratings
    - Most common categories
    """
    with LogContext(logger, doc_id=doc_id):
        logger.info("API request: Get negotiation statistics")
        
        try:
            negotiations_data = await firestore_client.get_negotiation_history(doc_id=doc_id)
            
            if not negotiations_data:
                return JSONResponse(
                    status_code=200,
                    content={
                        "total_negotiations": 0,
                        "message": "No negotiations found for this document"
                    }
                )
            
            # Calculate statistics
            total = len(negotiations_data)
            total_alternatives = sum(
                len(neg.get("alternatives", [])) for neg in negotiations_data
            )
            
            selections = sum(
                1 for neg in negotiations_data
                if neg.get("selected_alternative_id")
            )
            selection_rate = selections / total if total > 0 else 0.0
            
            helpful_count = sum(
                1 for neg in negotiations_data
                if neg.get("was_helpful") is True
            )
            helpful_rate = helpful_count / total if total > 0 else 0.0
            
            # Category distribution
            category_counts = {}
            for neg in negotiations_data:
                cat = neg.get("metadata", {}).get("category", "Unknown")
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            most_common = sorted(
                [{"category": k, "count": v} for k, v in category_counts.items()],
                key=lambda x: x["count"],
                reverse=True
            )[:5]
            
            return JSONResponse(
                status_code=200,
                content={
                    "doc_id": doc_id,
                    "total_negotiations": total,
                    "total_alternatives": total_alternatives,
                    "selection_rate": round(selection_rate, 2),
                    "helpful_rate": round(helpful_rate, 2),
                    "most_common_categories": most_common
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate statistics: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to calculate statistics: {str(e)}"
            )


# Background task helper
async def save_negotiations_background(
    firestore_client: FirestoreClient,
    doc_id: str,
    negotiations: List[NegotiationResponse]
):
    """Background task to save negotiation responses to Firestore."""
    logger.info(f"Background: Saving {len(negotiations)} negotiations for doc {doc_id}")
    
    for negotiation in negotiations:
        try:
            # Skip if negotiation_id is None
            if not negotiation.negotiation_id or not negotiation.clause_id:
                logger.warning(f"Skipping negotiation save - missing IDs")
                continue
            
            # Prepare negotiation history entry
            history_entry = {
                "negotiation_id": negotiation.negotiation_id,
                "doc_id": doc_id,
                "clause_id": negotiation.clause_id,
                "original_clause": negotiation.original_clause,
                "alternatives": [alt.dict() for alt in negotiation.alternatives],
                "risk_analysis": negotiation.risk_analysis.dict() if negotiation.risk_analysis else None,
                "generation_time": negotiation.generation_time,
                "model_used": negotiation.model_used,
                "context": negotiation.context,
                "created_at": negotiation.created_at.isoformat()
            }
            
            await firestore_client.save_negotiation_history(
                negotiation_id=negotiation.negotiation_id,
                history_data=history_entry
            )
            
        except Exception as e:
            logger.error(f"Failed to save negotiation {negotiation.negotiation_id}: {e}")
            continue
    
    logger.info(f"Background: Completed saving negotiations for doc {doc_id}")
