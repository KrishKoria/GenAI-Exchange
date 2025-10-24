"""
Question and Answer endpoints
"""
import logging
from typing import Dict, Any, List
from uuid import uuid4
from datetime import datetime
import json
import hashlib

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from google.cloud.firestore import SERVER_TIMESTAMP

from app.core.config import Settings, get_settings
from app.models.qa import QuestionRequest, AnswerResponse, SourceCitation
from app.models.chat import MessageRole, AddMessageRequest
from app.models.document import SupportedLanguage
from app.models.analytics import QuestionAskedEvent
from app.services.analytics_service import get_analytics_service
from app.services.firestore_client import FirestoreClient, FirestoreError
from app.services.embeddings_service import EmbeddingsService, EmbeddingsError
from app.services.gemini_client import GeminiClient, GeminiError
from app.services.chat_session_service import ChatSessionService
from app.services.language_detection_service import LanguageDetectionService
from app.dependencies.services import (
    get_firestore_client,
    get_embeddings_service,
    get_gemini_client,
    get_chat_session_service,
    get_cache_service,
    get_language_detection_service
)
from app.services.cache_service import CacheKeys, InMemoryCache

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=AnswerResponse)
async def ask_question(
    request: QuestionRequest,
    language: SupportedLanguage = SupportedLanguage.ENGLISH,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    settings: Settings = Depends(get_settings),
    firestore_client: FirestoreClient = Depends(get_firestore_client),
    embeddings_service: EmbeddingsService = Depends(get_embeddings_service),
    gemini_client: GeminiClient = Depends(get_gemini_client),
    chat_session_service: ChatSessionService = Depends(get_chat_session_service),
    language_detection_service: LanguageDetectionService = Depends(get_language_detection_service),
    cache_service: InMemoryCache = Depends(get_cache_service)
) -> AnswerResponse:
    """
    Ask a question about document clauses using vector similarity search and grounded prompting.
    Supports both legacy single-doc Q&A and new chat session-based Q&A with memory.
    
    Args:
        request: Question and document context
        
    Returns:
        Answer with supporting clause citations
        
    Raises:
        HTTPException: If document not found or question invalid
    """
    start_time = datetime.now()
    logger.info(f"Q&A request for doc_id: {request.doc_id}")

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        # Auto-detect language if enabled, otherwise use override or default
        detected_language = None
        response_language = language  # Default to the language parameter
        language_detection_confidence = None
        detection_method = None

        if request.auto_detect_language:
            logger.info("Auto-detecting language from question")
            detection_result = await language_detection_service.detect_language_advanced(
                text=request.question,
                session_id=request.session_id,
                context=request.session_context
            )

            detected_language = detection_result.language
            language_detection_confidence = detection_result.confidence
            detection_method = detection_result.method

            # Use detected language if confidence is high enough, otherwise use override or default
            if request.language_override:
                response_language = request.language_override
                logger.info(f"Using language override: {response_language}")
            elif detection_result.confidence > 0.8:
                response_language = detected_language
                logger.info(f"Using auto-detected language: {response_language} (confidence: {detection_result.confidence:.2f})")
            else:
                logger.info(f"Low detection confidence ({detection_result.confidence:.2f}), using default: {response_language}")
        elif request.language_override:
            response_language = request.language_override
            logger.info(f"Using manual language override: {response_language}")

        logger.info(f"Final response language: {response_language}")
        # Check if this is a chat session-based request
        conversation_context = ""
        conversation_context_used = False
        chat_session_id = None
        
        if request.chat_session_id and request.use_conversation_memory:
            # Get conversation context from chat session
            conversation_history, context_summary = await chat_session_service.get_conversation_context(
                request.chat_session_id,
                max_messages=10
            )
            
            if context_summary:
                conversation_context += f"Previous conversation summary: {context_summary}\n\n"
            
            if conversation_history:
                conversation_context += "Recent conversation:\n"
                for msg in conversation_history[-5:]:  # Last 5 messages
                    conversation_context += f"{msg.role.value}: {msg.content}\n"
                conversation_context += "\n"
                
            conversation_context_used = len(conversation_history) > 0 or bool(context_summary)
            chat_session_id = request.chat_session_id
            
            # Add user message to chat session - moved to background task
            background_tasks.add_task(
                chat_session_service.add_message,
                request.chat_session_id,
                AddMessageRequest(
                    role=MessageRole.USER,
                    content=request.question,
                    metadata={"doc_id": request.doc_id, "legacy_qa": True}
                )
            )
        
        # 1. Verify document exists and get its clauses (with caching)
        logger.info(f"Fetching clauses for document: {request.doc_id}")
        
        # Check cache first
        cache_key = CacheKeys.document_clauses(request.doc_id)
        clauses = await cache_service.get(cache_key)
        
        if clauses is None:
            # Cache miss - fetch from Firestore
            logger.info(f"Cache miss for document clauses: {request.doc_id}")
            clauses = await firestore_client.get_document_clauses(request.doc_id)
            
            # Cache the result for future requests (cache for 30 minutes)
            if clauses:
                await cache_service.set(cache_key, clauses, ttl=1800)
                logger.info(f"Cached {len(clauses)} clauses for document: {request.doc_id}")
        else:
            logger.info(f"Cache hit for document clauses: {request.doc_id} ({len(clauses)} clauses)")
        
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
            answer_text = "I couldn't find any clauses in this document that relate to your question. Please try rephrasing your question or ask about different aspects of the document."
            
            # Add to chat session if applicable (background task)
            if chat_session_id:
                background_tasks.add_task(
                    chat_session_service.add_message,
                    chat_session_id,
                    AddMessageRequest(
                        role=MessageRole.ASSISTANT,
                        content=answer_text,
                        metadata={"no_relevant_clauses": True, "doc_id": request.doc_id}
                    )
                )
            
            return AnswerResponse(
                answer=answer_text,
                used_clause_ids=[],
                confidence=0.0,
                sources=[],
                chat_session_id=chat_session_id,
                conversation_context_used=conversation_context_used,
                detected_language=detected_language,
                response_language=response_language,
                language_detection_confidence=language_detection_confidence,
                detection_method=detection_method
            )
        
        logger.info(f"Found {len(relevant_clauses)} relevant clauses")
        
        # 4. Use Gemini for grounded Q&A with conversation context
        logger.info("Generating answer using Gemini")
        
        # Prepare enhanced question with conversation context
        enhanced_question = request.question
        if conversation_context:
            enhanced_question = f"Previous context:\n{conversation_context}\n\nCurrent question: {request.question}"
        
        qa_result = await gemini_client.answer_question(
            question=enhanced_question,
            relevant_clauses=relevant_clauses,
            doc_id=request.doc_id,
            language=response_language
        )
        
        # 5. Build response with proper source citations
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
        
        # 6. Move background operations to background tasks for better performance
        # Store Q&A in history (background task)
        background_tasks.add_task(
            _store_qa_history,
            firestore_client,
            request,
            qa_result,
            relevant_clauses
        )
        
        # 7. Add assistant message to chat session (background task)
        if chat_session_id:
            background_tasks.add_task(
                chat_session_service.add_message,
                chat_session_id,
                AddMessageRequest(
                    role=MessageRole.ASSISTANT,
                    content=qa_result.get("answer", ""),
                    sources=[source.model_dump() for source in sources],
                    metadata={
                        "used_clause_ids": qa_result.get("used_clause_ids", []),
                        "confidence": qa_result.get("confidence", 0.0),
                        "doc_id": request.doc_id,
                        "conversation_context_used": conversation_context_used
                    }
                )
            )
        
        # Publish analytics event for question asked
        try:
            response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            analytics_service = get_analytics_service()
            
            # Hash question for privacy (no PII in events)
            question_hash = hashlib.sha256(request.question.encode('utf-8')).hexdigest()
            
            event = QuestionAskedEvent(
                question_hash=question_hash,
                answer_confidence=qa_result.get("confidence", 0.0),
                citation_count=len(sources),
                response_time_ms=response_time_ms,
                session_id=chat_session_id
            )
            
            # Publish asynchronously (fire-and-forget)
            analytics_service.publish_event(event)
            logger.debug(f"Published QuestionAskedEvent (hash: {question_hash[:8]}...)")
            
        except Exception as analytics_error:
            # Don't fail Q&A if analytics fails
            logger.error(f"Failed to publish QuestionAskedEvent: {analytics_error}")
        
        return AnswerResponse(
            answer=qa_result.get("answer", ""),
            used_clause_ids=qa_result.get("used_clause_ids", []),
            confidence=qa_result.get("confidence", 0.0),
            sources=sources,
            chat_session_id=chat_session_id,
            conversation_context_used=conversation_context_used,
            detected_language=detected_language,
            response_language=response_language,
            language_detection_confidence=language_detection_confidence,
            detection_method=detection_method
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


@router.post("/ask-stream")
async def ask_question_stream(
    request: QuestionRequest,
    language: SupportedLanguage = SupportedLanguage.ENGLISH,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    settings: Settings = Depends(get_settings),
    firestore_client: FirestoreClient = Depends(get_firestore_client),
    embeddings_service: EmbeddingsService = Depends(get_embeddings_service),
    gemini_client: GeminiClient = Depends(get_gemini_client),
    chat_session_service: ChatSessionService = Depends(get_chat_session_service),
    language_detection_service: LanguageDetectionService = Depends(get_language_detection_service),
    cache_service: InMemoryCache = Depends(get_cache_service)
):
    """
    Streaming version of ask_question that provides real-time updates.
    Returns Server-Sent Events (SSE) stream.
    """
    async def event_stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Processing your question...'})}\n\n"
            
            # Same logic as ask_question but with streaming updates
            if not request.question.strip():
                yield f"data: {json.dumps({'type': 'error', 'message': 'Question cannot be empty'})}\n\n"
                return

            # Auto-detect language if enabled, otherwise use override or default
            detected_language = None
            response_language = language  # Default to the language parameter
            language_detection_confidence = None
            detection_method = None

            if request.auto_detect_language:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Detecting language...'})}\n\n"
                detection_result = await language_detection_service.detect_language_advanced(
                    text=request.question,
                    session_id=request.session_id,
                    context=request.session_context
                )

                detected_language = detection_result.language
                language_detection_confidence = detection_result.confidence
                detection_method = detection_result.method

                # Use detected language if confidence is high enough, otherwise use override or default
                if request.language_override:
                    response_language = request.language_override
                elif detection_result.confidence > 0.8:
                    response_language = detected_language
                    yield f"data: {json.dumps({'type': 'language_detection', 'detected_language': response_language.value, 'confidence': detection_result.confidence})}\n\n"
            elif request.language_override:
                response_language = request.language_override

            # Add user message to chat session immediately (background task)
            conversation_context = ""
            conversation_context_used = False
            chat_session_id = None
            
            if request.chat_session_id and request.use_conversation_memory:
                chat_session_id = request.chat_session_id
                
                # Send user message event immediately
                yield f"data: {json.dumps({'type': 'user_message', 'content': request.question, 'chat_session_id': chat_session_id})}\n\n"
                
                # Add user message in background
                background_tasks.add_task(
                    chat_session_service.add_message,
                    request.chat_session_id,
                    AddMessageRequest(
                        role=MessageRole.USER,
                        content=request.question,
                        metadata={"doc_id": request.doc_id, "legacy_qa": True}
                    )
                )
                
                # Get conversation context
                yield f"data: {json.dumps({'type': 'status', 'message': 'Loading conversation context...'})}\n\n"
                conversation_history, context_summary = await chat_session_service.get_conversation_context(
                    request.chat_session_id,
                    max_messages=10
                )
                
                if context_summary:
                    conversation_context += f"Previous conversation summary: {context_summary}\n\n"
                
                if conversation_history:
                    conversation_context += "Recent conversation:\n"
                    for msg in conversation_history[-5:]:
                        conversation_context += f"{msg.role.value}: {msg.content}\n"
                    conversation_context += "\n"
                    
                conversation_context_used = len(conversation_history) > 0 or bool(context_summary)
            
            # Get document clauses with caching
            yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching document clauses...'})}\n\n"
            
            cache_key = CacheKeys.document_clauses(request.doc_id)
            clauses = await cache_service.get(cache_key)
            
            if clauses is None:
                clauses = await firestore_client.get_document_clauses(request.doc_id)
                if clauses:
                    await cache_service.set(cache_key, clauses, ttl=1800)
            
            if not clauses:
                yield f"data: {json.dumps({'type': 'error', 'message': f'No clauses found for document {request.doc_id}'})}\n\n"
                return
            
            # Filter clauses with embeddings
            clauses_with_embeddings = [
                clause for clause in clauses 
                if clause.get("embedding") and len(clause.get("embedding", [])) > 0
            ]
            
            if not clauses_with_embeddings:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Document processing incomplete. Please try again later.'})}\n\n"
                return
            
            # Find relevant clauses
            yield f"data: {json.dumps({'type': 'status', 'message': f'Searching {len(clauses_with_embeddings)} clauses for relevance...'})}\n\n"
            
            relevant_clauses = await embeddings_service.search_similar_clauses(
                question=request.question,
                clause_embeddings=clauses_with_embeddings,
                top_k=5,
                min_similarity=0.2
            )
            
            if not relevant_clauses:
                answer_text = "I couldn't find any clauses in this document that relate to your question. Please try rephrasing your question or ask about different aspects of the document."
                
                yield f"data: {json.dumps({'type': 'answer', 'content': answer_text, 'confidence': 0.0, 'sources': [], 'chat_session_id': chat_session_id})}\n\n"
                
                if chat_session_id:
                    background_tasks.add_task(
                        chat_session_service.add_message,
                        chat_session_id,
                        AddMessageRequest(
                            role=MessageRole.ASSISTANT,
                            content=answer_text,
                            metadata={"no_relevant_clauses": True, "doc_id": request.doc_id}
                        )
                    )
                return
            
            # Generate answer
            yield f"data: {json.dumps({'type': 'status', 'message': f'Found {len(relevant_clauses)} relevant clauses. Generating answer...'})}\n\n"
            
            enhanced_question = request.question
            if conversation_context:
                enhanced_question = f"Previous context:\n{conversation_context}\n\nCurrent question: {request.question}"
            
            qa_result = await gemini_client.answer_question(
                question=enhanced_question,
                relevant_clauses=relevant_clauses,
                doc_id=request.doc_id,
                language=response_language
            )
            
            # Build sources
            sources = []
            for clause in relevant_clauses:
                if clause.get("clause_id") in qa_result.get("used_clause_ids", []):
                    original_text = clause.get("original_text", "")
                    snippet = original_text[:300] + "..." if len(original_text) > 300 else original_text
                    
                    sources.append({
                        "clause_id": clause["clause_id"],
                        "clause_number": clause.get("order"),
                        "category": clause.get("category"),
                        "snippet": snippet,
                        "relevance_score": clause.get("similarity", 0.0)
                    })
            
            # Send final answer
            yield f"data: {json.dumps({'type': 'answer', 'content': qa_result.get('answer', ''), 'confidence': qa_result.get('confidence', 0.0), 'sources': sources, 'chat_session_id': chat_session_id, 'conversation_context_used': conversation_context_used})}\n\n"
            
            # Background tasks for storage
            background_tasks.add_task(
                _store_qa_history,
                firestore_client,
                request,
                qa_result,
                relevant_clauses
            )
            
            if chat_session_id:
                background_tasks.add_task(
                    chat_session_service.add_message,
                    chat_session_id,
                    AddMessageRequest(
                        role=MessageRole.ASSISTANT,
                        content=qa_result.get("answer", ""),
                        sources=sources,
                        metadata={
                            "used_clause_ids": qa_result.get("used_clause_ids", []),
                            "confidence": qa_result.get("confidence", 0.0),
                            "doc_id": request.doc_id,
                            "conversation_context_used": conversation_context_used
                        }
                    )
                )
            
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming Q&A error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Internal server error processing question'})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


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
    settings: Settings = Depends(get_settings),
    firestore_client: FirestoreClient = Depends(get_firestore_client)
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


@router.get("/cache/stats")
async def get_cache_stats(
    settings: Settings = Depends(get_settings),
    cache_service: InMemoryCache = Depends(get_cache_service)
) -> Dict[str, Any]:
    """
    Get cache statistics for monitoring performance.
    
    Returns:
        Cache statistics including hit rate, size, etc.
    """
    try:
        stats = cache_service.get_stats()
        return {
            "cache_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache statistics")


@router.post("/cache/clear")
async def clear_cache(
    settings: Settings = Depends(get_settings),
    cache_service: InMemoryCache = Depends(get_cache_service)
) -> Dict[str, Any]:
    """
    Clear all cache entries (admin endpoint).
    
    Returns:
        Success message
    """
    try:
        await cache_service.clear()
        logger.info("Cache cleared successfully")
        return {
            "message": "Cache cleared successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")
