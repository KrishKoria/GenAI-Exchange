"""
Chat Session API endpoints for conversation memory management
"""
import logging
from typing import List, Optional
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.models.chat import (
    CreateChatSessionRequest,
    CreateChatSessionResponse,
    UpdateSessionDocumentsRequest,
    UpdateSessionDocumentsResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    AddMessageRequest,
    AddMessageResponse,
    ChatQuestionRequest,
    ChatAnswerResponse,
    MessageRole
)
from app.services.chat_session_service import ChatSessionService
from app.services.firestore_client import FirestoreClient, FirestoreError
from app.services.embeddings_service import EmbeddingsService, EmbeddingsError
from app.services.gemini_client import GeminiClient, GeminiError
from app.dependencies.services import (
    get_chat_session_service,
    get_firestore_client,
    get_embeddings_service,
    get_gemini_client,
    get_cache_service
)
from app.services.cache_service import InMemoryCache

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/sessions", response_model=CreateChatSessionResponse)
async def create_chat_session(
    request: CreateChatSessionRequest,
    settings: Settings = Depends(get_settings),
    chat_service: ChatSessionService = Depends(get_chat_session_service)
) -> CreateChatSessionResponse:
    """
    Create a new chat session with optional document context.
    
    Args:
        request: Session creation request
        
    Returns:
        Created session information
        
    Raises:
        HTTPException: If session creation fails
    """
    try:
        session, selected_documents = await chat_service.create_session(request)
        
        logger.info(f"Created chat session: {session.session_id}")
        
        return CreateChatSessionResponse(
            session_id=session.session_id,
            title=session.title,
            created_at=session.created_at,
            selected_documents=selected_documents
        )
        
    except FirestoreError as e:
        logger.error(f"Firestore error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error creating session")


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_chat_sessions(
    user_id: Optional[str] = Query(None, description="User ID to filter sessions"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of sessions to return"),
    include_archived: bool = Query(False, description="Include archived sessions"),
    settings: Settings = Depends(get_settings),
    chat_service: ChatSessionService = Depends(get_chat_session_service)
) -> ChatSessionListResponse:
    """
    List chat sessions for a user.
    
    Args:
        user_id: User identifier (optional)
        limit: Maximum number of sessions
        include_archived: Whether to include archived sessions
        
    Returns:
        List of chat sessions
    """
    try:
        sessions = await chat_service.list_sessions(
            user_id=user_id,
            limit=limit,
            include_archived=include_archived
        )
        
        return ChatSessionListResponse(
            sessions=sessions,
            total_count=len(sessions)
        )
        
    except FirestoreError as e:
        logger.error(f"Firestore error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Session listing failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error listing sessions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error listing sessions")


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: str,
    settings: Settings = Depends(get_settings),
    chat_service: ChatSessionService = Depends(get_chat_session_service)
) -> ChatSessionResponse:
    """
    Retrieve a chat session with full conversation history.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Chat session with messages
        
    Raises:
        HTTPException: If session not found
    """
    try:
        session = await chat_service.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        return ChatSessionResponse(session=session)
        
    except HTTPException:
        raise
    except FirestoreError as e:
        logger.error(f"Firestore error retrieving session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Session retrieval failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error retrieving session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error retrieving session")


@router.put("/sessions/{session_id}/documents", response_model=UpdateSessionDocumentsResponse)
async def update_session_documents(
    session_id: str,
    request: UpdateSessionDocumentsRequest,
    settings: Settings = Depends(get_settings),
    chat_service: ChatSessionService = Depends(get_chat_session_service)
) -> UpdateSessionDocumentsResponse:
    """
    Update the document context for a chat session.
    
    Args:
        session_id: Session identifier
        request: Document update request
        
    Returns:
        Updated document context
        
    Raises:
        HTTPException: If session not found or update fails
    """
    try:
        selected_documents = await chat_service.update_session_documents(
            session_id, request
        )
        
        return UpdateSessionDocumentsResponse(
            session_id=session_id,
            selected_documents=selected_documents,
            updated_at=datetime.utcnow()
        )
        
    except FirestoreError as e:
        logger.error(f"Firestore error updating session documents: {e}")
        raise HTTPException(status_code=500, detail=f"Document update failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error updating session documents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error updating documents")


@router.post("/sessions/{session_id}/messages", response_model=AddMessageResponse)
async def add_message_to_session(
    session_id: str,
    request: AddMessageRequest,
    settings: Settings = Depends(get_settings),
    chat_service: ChatSessionService = Depends(get_chat_session_service)
) -> AddMessageResponse:
    """
    Add a message to a chat session.
    
    Args:
        session_id: Session identifier
        request: Message data
        
    Returns:
        Created message information
        
    Raises:
        HTTPException: If session not found or message addition fails
    """
    try:
        message = await chat_service.add_message(session_id, request)
        
        return AddMessageResponse(
            message_id=message.message_id,
            session_id=session_id,
            timestamp=message.timestamp
        )
        
    except FirestoreError as e:
        logger.error(f"Firestore error adding message: {e}")
        raise HTTPException(status_code=500, detail=f"Message addition failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error adding message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error adding message")


@router.post("/sessions/{session_id}/ask", response_model=ChatAnswerResponse)
async def ask_question_with_memory(
    session_id: str,
    request: ChatQuestionRequest,
    settings: Settings = Depends(get_settings),
    chat_service: ChatSessionService = Depends(get_chat_session_service),
    firestore_client: FirestoreClient = Depends(get_firestore_client),
    embeddings_service: EmbeddingsService = Depends(get_embeddings_service),
    gemini_client: GeminiClient = Depends(get_gemini_client),
    cache_service: InMemoryCache = Depends(get_cache_service)
) -> ChatAnswerResponse:
    """
    Ask a question with chat session memory and document context.
    
    Args:
        session_id: Session identifier
        request: Question request with memory options
        
    Returns:
        Answer with session context and created message
        
    Raises:
        HTTPException: If session not found or question processing fails
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        # 1. Get session and verify it exists
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # 2. Validate that session has documents
        if not session.selected_documents:
            raise HTTPException(
                status_code=400, 
                detail="No documents selected in this chat session. Please add documents first."
            )
        
        # 3. Get conversation context if requested
        conversation_history = []
        context_summary = None
        conversation_context_used = False
        
        if request.include_conversation_history:
            conversation_history, context_summary = await chat_service.get_conversation_context(
                session_id, 
                max_messages=request.max_history_messages
            )
            conversation_context_used = len(conversation_history) > 0 or bool(context_summary)
        
        # 4. Add user message to session
        user_message = await chat_service.add_message(
            session_id,
            AddMessageRequest(
                role=MessageRole.USER,
                content=request.question,
                metadata={"include_history": request.include_conversation_history}
            )
        )
        
        # 5. Process each document in the session context
        all_relevant_clauses = []
        all_clause_ids = []
        
        for doc_context in session.selected_documents:
            doc_id = doc_context.doc_id
            
            # Get document clauses
            logger.info(f"Processing document {doc_id} for session {session_id}")
            clauses = await firestore_client.get_document_clauses(doc_id)
            
            if not clauses:
                logger.warning(f"No clauses found for document {doc_id}")
                continue
            
            # Filter clauses with embeddings
            clauses_with_embeddings = [
                clause for clause in clauses 
                if clause.get("embedding") and len(clause.get("embedding", [])) > 0
            ]
            
            if not clauses_with_embeddings:
                logger.warning(f"No embeddings found for document {doc_id}")
                continue
            
            # Find relevant clauses for this document
            relevant_clauses = await embeddings_service.search_similar_clauses(
                question=request.question,
                clause_embeddings=clauses_with_embeddings,
                top_k=3,  # Fewer per document since we may have multiple docs
                min_similarity=0.2
            )
            
            all_relevant_clauses.extend(relevant_clauses)
            all_clause_ids.extend([clause["clause_id"] for clause in relevant_clauses])
        
        if not all_relevant_clauses:
            # No relevant clauses found across all documents
            answer_text = "I couldn't find any clauses in the selected documents that relate to your question. Please try rephrasing your question or ask about different aspects of the documents."
            
            # Add assistant message
            assistant_message = await chat_service.add_message(
                session_id,
                AddMessageRequest(
                    role=MessageRole.ASSISTANT,
                    content=answer_text,
                    metadata={"no_relevant_clauses": True}
                )
            )
            
            return ChatAnswerResponse(
                session_id=session_id,
                message_id=assistant_message.message_id,
                answer=answer_text,
                used_clause_ids=[],
                confidence=0.0,
                sources=[],
                conversation_context_used=conversation_context_used,
                timestamp=assistant_message.timestamp
            )
        
        # 6. Generate answer using Gemini with conversation context
        logger.info(f"Generating answer with {len(all_relevant_clauses)} relevant clauses and conversation context")
        
        # Prepare conversation context for Gemini
        conversation_context = ""
        if conversation_context_used:
            if context_summary:
                conversation_context += f"Previous conversation summary: {context_summary}\n\n"
            
            if conversation_history:
                conversation_context += "Recent conversation:\n"
                for msg in conversation_history[-5:]:  # Last 5 messages
                    conversation_context += f"{msg.role.value}: {msg.content}\n"
                conversation_context += "\n"
        
        # Create enhanced question with conversation context
        enhanced_question = request.question
        if conversation_context:
            enhanced_question = f"Previous context:\n{conversation_context}\n\nCurrent question: {request.question}"
        
        qa_result = await gemini_client.answer_question(
            question=enhanced_question,
            relevant_clauses=all_relevant_clauses,
            doc_id=session.selected_documents[0].doc_id  # Use first document ID for compatibility
        )
        
        # 7. Build source citations
        sources = []
        for clause in all_relevant_clauses:
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
        
        # 8. Add assistant message to session
        assistant_message = await chat_service.add_message(
            session_id,
            AddMessageRequest(
                role=MessageRole.ASSISTANT,
                content=qa_result.get("answer", ""),
                sources=sources,
                metadata={
                    "used_clause_ids": qa_result.get("used_clause_ids", []),
                    "confidence": qa_result.get("confidence", 0.0),
                    "conversation_context_used": conversation_context_used,
                    "documents_processed": [doc.doc_id for doc in session.selected_documents]
                }
            )
        )
        
        return ChatAnswerResponse(
            session_id=session_id,
            message_id=assistant_message.message_id,
            answer=qa_result.get("answer", ""),
            used_clause_ids=qa_result.get("used_clause_ids", []),
            confidence=qa_result.get("confidence", 0.0),
            sources=sources,
            conversation_context_used=conversation_context_used,
            additional_insights=qa_result.get("additional_insights"),
            timestamp=assistant_message.timestamp
        )
        
    except HTTPException:
        raise
    except (FirestoreError, EmbeddingsError, GeminiError) as e:
        logger.error(f"Service error in chat Q&A: {e}")
        raise HTTPException(status_code=500, detail=f"Q&A processing failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in chat Q&A: {e}")
        raise HTTPException(status_code=500, detail="Internal server error processing question")


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    settings: Settings = Depends(get_settings),
    chat_service: ChatSessionService = Depends(get_chat_session_service)
) -> JSONResponse:
    """
    Delete a chat session and all its messages.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Success confirmation
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        success = await chat_service.delete_session(session_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete session")
        
        return JSONResponse(
            content={"message": f"Session {session_id} deleted successfully"},
            status_code=200
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error deleting session")


@router.put("/sessions/{session_id}/archive")
async def archive_chat_session(
    session_id: str,
    settings: Settings = Depends(get_settings),
    chat_service: ChatSessionService = Depends(get_chat_session_service)
) -> JSONResponse:
    """
    Archive a chat session (soft delete).
    
    Args:
        session_id: Session identifier
        
    Returns:
        Success confirmation
    """
    try:
        success = await chat_service.archive_session(session_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to archive session")
        
        return JSONResponse(
            content={"message": f"Session {session_id} archived successfully"},
            status_code=200
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error archiving session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error archiving session")