"""
Chat Session Service for managing conversation memory and document context
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
from datetime import datetime, timedelta

from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter, Increment

from app.core.config import get_settings
from app.models.chat import (
    ChatSession, 
    ChatMessage, 
    DocumentContext, 
    MessageRole,
    CreateChatSessionRequest,
    UpdateSessionDocumentsRequest,
    AddMessageRequest
)
from app.services.firestore_client import FirestoreClient, FirestoreError
from app.services.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class ChatSessionService:
    """Service for managing chat sessions and conversation memory."""
    
    def __init__(self):
        self.firestore_client = FirestoreClient()
        self.gemini_client = GeminiClient()
        self.settings = get_settings()
        
        # Collection names
        self.sessions_collection = "chat_sessions"
        self.messages_collection = "messages"
        
        # Configuration
        self.max_messages_per_session = 200
        self.context_window_messages = 20  # Messages to include in context
        self.auto_summary_threshold = 50  # Summarize when session exceeds this
        
    async def create_session(
        self, 
        request: CreateChatSessionRequest
    ) -> Tuple[ChatSession, List[DocumentContext]]:
        """
        Create a new chat session with optional document context.
        
        Args:
            request: Session creation request
            
        Returns:
            Tuple of (created session, selected documents with metadata)
            
        Raises:
            FirestoreError: If session creation fails
        """
        session_id = str(uuid4())
        now = datetime.utcnow()
        
        try:
            # Get document metadata for selected documents
            selected_documents = []
            if request.selected_document_ids:
                selected_documents = await self._get_documents_metadata(
                    request.selected_document_ids
                )
            
            # Create session
            session = ChatSession(
                session_id=session_id,
                title=request.title or f"Chat {now.strftime('%m/%d %H:%M')}",
                created_at=now,
                updated_at=now,
                user_id=request.user_id,
                selected_documents=selected_documents,
                messages=[],
                last_activity=now
            )
            
            # Store in Firestore
            db = self.firestore_client.db
            session_ref = db.collection(self.sessions_collection).document(session_id)
            
            session_data = session.model_dump()
            session_data['created_at'] = SERVER_TIMESTAMP
            session_data['updated_at'] = SERVER_TIMESTAMP
            session_data['last_activity'] = SERVER_TIMESTAMP
            
            session_ref.set(session_data)
            
            logger.info(f"Created chat session: {session_id}")
            return session, selected_documents
            
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            raise FirestoreError(f"Session creation failed: {str(e)}")
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Retrieve a chat session with full conversation history.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Chat session or None if not found
        """
        try:
            db = self.firestore_client.db
            session_ref = db.collection(self.sessions_collection).document(session_id)
            session_doc = session_ref.get()
            
            if not session_doc.exists:
                return None
            
            session_data = session_doc.to_dict()
            
            # Convert Firestore timestamps to datetime
            for field in ['created_at', 'updated_at', 'last_activity']:
                if field in session_data and session_data[field]:
                    session_data[field] = session_data[field]
            
            # Get messages for this session
            messages = await self._get_session_messages(session_id)
            session_data['messages'] = messages
            
            session = ChatSession(**session_data)
            return session
            
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}")
            raise FirestoreError(f"Session retrieval failed: {str(e)}")
    
    async def list_sessions(
        self, 
        user_id: Optional[str] = None,
        limit: int = 50,
        include_archived: bool = False
    ) -> List[ChatSession]:
        """
        List chat sessions for a user.
        
        Args:
            user_id: User identifier (optional)
            limit: Maximum number of sessions to return
            include_archived: Whether to include archived sessions
            
        Returns:
            List of chat sessions (without full message history)
        """
        try:
            db = self.firestore_client.db
            query = db.collection(self.sessions_collection)
            
            # Filter by user if provided
            if user_id:
                query = query.where("user_id", "==", user_id)
            
            # Filter archived sessions
            if not include_archived:
                query = query.where("is_archived", "==", False)
            
            # Order by last activity (most recent first)
            query = query.order_by("last_activity", direction="DESCENDING")
            query = query.limit(limit)
            
            sessions = []
            for doc in query.stream():
                session_data = doc.to_dict()
                
                # Convert timestamps
                for field in ['created_at', 'updated_at', 'last_activity']:
                    if field in session_data and session_data[field]:
                        session_data[field] = session_data[field]
                
                # Don't include full message history in list view
                session_data['messages'] = []
                
                sessions.append(ChatSession(**session_data))
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise FirestoreError(f"Session listing failed: {str(e)}")
    
    async def update_session_documents(
        self, 
        session_id: str, 
        request: UpdateSessionDocumentsRequest
    ) -> List[DocumentContext]:
        """
        Update the document context for a chat session.
        
        Args:
            session_id: Session identifier
            request: Document update request
            
        Returns:
            Updated document context list
            
        Raises:
            FirestoreError: If update fails
        """
        try:
            # Get document metadata
            selected_documents = await self._get_documents_metadata(
                request.document_ids
            )
            
            # Update session
            db = self.firestore_client.db
            session_ref = db.collection(self.sessions_collection).document(session_id)
            
            update_data = {
                'selected_documents': [doc.model_dump() for doc in selected_documents],
                'updated_at': SERVER_TIMESTAMP,
                'last_activity': SERVER_TIMESTAMP
            }
            
            session_ref.update(update_data)
            
            logger.info(f"Updated documents for session {session_id}: {len(selected_documents)} docs")
            return selected_documents
            
        except Exception as e:
            logger.error(f"Failed to update session documents: {e}")
            raise FirestoreError(f"Document update failed: {str(e)}")
    
    async def add_message(
        self, 
        session_id: str, 
        request: AddMessageRequest
    ) -> ChatMessage:
        """
        Add a message to a chat session.
        
        Args:
            session_id: Session identifier
            request: Message data
            
        Returns:
            Created message
            
        Raises:
            FirestoreError: If message addition fails
        """
        try:
            message_id = str(uuid4())
            now = datetime.utcnow()
            
            message = ChatMessage(
                message_id=message_id,
                role=request.role,
                content=request.content,
                timestamp=now,
                sources=request.sources or [],
                metadata=request.metadata or {}
            )
            
            # Store message in subcollection
            db = self.firestore_client.db
            message_ref = (
                db.collection(self.sessions_collection)
                .document(session_id)
                .collection(self.messages_collection)
                .document(message_id)
            )
            
            message_data = message.model_dump()
            message_data['timestamp'] = SERVER_TIMESTAMP
            message_ref.set(message_data)
            
            # Update session metadata
            session_ref = db.collection(self.sessions_collection).document(session_id)
            
            update_data = {
                'total_messages': Increment(1),
                'updated_at': SERVER_TIMESTAMP,
                'last_activity': SERVER_TIMESTAMP
            }
            
            if request.role == MessageRole.USER:
                update_data['total_questions'] = Increment(1)
            
            session_ref.update(update_data)
            
            # Check if we need to summarize conversation
            await self._maybe_summarize_session(session_id)
            
            logger.info(f"Added message to session {session_id}: {message_id}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to add message to session {session_id}: {e}")
            raise FirestoreError(f"Message addition failed: {str(e)}")
    
    async def get_conversation_context(
        self, 
        session_id: str,
        max_messages: int = 10
    ) -> Tuple[List[ChatMessage], Optional[str]]:
        """
        Get conversation context for Q&A processing.
        
        Args:
            session_id: Session identifier  
            max_messages: Maximum number of recent messages to include
            
        Returns:
            Tuple of (recent messages, context summary)
        """
        try:
            # Get session to check for existing summary
            session = await self.get_session(session_id)
            if not session:
                return [], None
            
            # Get recent messages
            messages = await self._get_session_messages(
                session_id, 
                limit=max_messages
            )
            
            return messages, session.context_summary
            
        except Exception as e:
            logger.error(f"Failed to get conversation context for {session_id}: {e}")
            return [], None
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session and all its messages.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        try:
            db = self.firestore_client.db
            
            # Delete all messages in subcollection
            messages_ref = (
                db.collection(self.sessions_collection)
                .document(session_id)
                .collection(self.messages_collection)
            )
            
            # Delete messages in batches
            batch = db.batch()
            batch_count = 0
            
            for message_doc in messages_ref.stream():
                batch.delete(message_doc.reference)
                batch_count += 1
                
                if batch_count >= 500:  # Firestore batch limit
                    batch.commit()
                    batch = db.batch()
                    batch_count = 0
            
            if batch_count > 0:
                batch.commit()
            
            # Delete session document
            session_ref = db.collection(self.sessions_collection).document(session_id)
            session_ref.delete()
            
            logger.info(f"Deleted chat session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    async def archive_session(self, session_id: str) -> bool:
        """
        Archive a chat session (soft delete).
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        try:
            db = self.firestore_client.db
            session_ref = db.collection(self.sessions_collection).document(session_id)
            
            session_ref.update({
                'is_archived': True,
                'updated_at': SERVER_TIMESTAMP
            })
            
            logger.info(f"Archived chat session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to archive session {session_id}: {e}")
            return False
    
    async def _get_documents_metadata(
        self, 
        document_ids: List[str]
    ) -> List[DocumentContext]:
        """Get metadata for selected documents."""
        documents = []
        
        for doc_id in document_ids:
            try:
                doc = await self.firestore_client.get_document(doc_id)
                if doc:
                    documents.append(DocumentContext(
                        doc_id=doc_id,
                        doc_name=doc.get('filename', f'Document {doc_id[:8]}'),
                        status=doc.get('status'),
                        added_at=datetime.utcnow()
                    ))
            except Exception as e:
                logger.warning(f"Could not get metadata for document {doc_id}: {e}")
                # Add with minimal info
                documents.append(DocumentContext(
                    doc_id=doc_id,
                    doc_name=f'Document {doc_id[:8]}',
                    added_at=datetime.utcnow()
                ))
        
        return documents
    
    async def _get_session_messages(
        self, 
        session_id: str, 
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """Get messages for a session, ordered by timestamp."""
        try:
            db = self.firestore_client.db
            
            if limit:
                # Get most recent messages (descending order) then reverse
                messages_ref = (
                    db.collection(self.sessions_collection)
                    .document(session_id)
                    .collection(self.messages_collection)
                    .order_by("timestamp", direction="DESCENDING")
                    .limit(limit)
                )
            else:
                # Get all messages in ascending order
                messages_ref = (
                    db.collection(self.sessions_collection)
                    .document(session_id)
                    .collection(self.messages_collection)
                    .order_by("timestamp", direction="ASCENDING")
                )
            
            messages = []
            for doc in messages_ref.stream():
                message_data = doc.to_dict()
                
                # Convert timestamp
                if 'timestamp' in message_data and message_data['timestamp']:
                    message_data['timestamp'] = message_data['timestamp']
                
                messages.append(ChatMessage(**message_data))
            
            # If we limited and reversed, reverse back to chronological order
            if limit:
                messages.reverse()
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}")
            return []
    
    async def _maybe_summarize_session(self, session_id: str) -> None:
        """Check if session needs summarization and perform it if needed."""
        try:
            session = await self.get_session(session_id)
            if not session:
                return
            
            # Check if we need to summarize
            if (session.total_messages >= self.auto_summary_threshold and 
                not session.context_summary):
                
                logger.info(f"Auto-summarizing session {session_id}")
                await self._summarize_conversation(session_id)
                
        except Exception as e:
            logger.warning(f"Failed to check/perform summarization for {session_id}: {e}")
    
    async def _summarize_conversation(self, session_id: str) -> Optional[str]:
        """Generate a summary of the conversation using Gemini."""
        try:
            # Get older messages to summarize (exclude recent ones)
            all_messages = await self._get_session_messages(session_id)
            
            if len(all_messages) < 10:
                return None
            
            # Summarize older messages, keep recent ones as-is
            messages_to_summarize = all_messages[:-self.context_window_messages]
            
            if not messages_to_summarize:
                return None
            
            # Create conversation text for summarization
            conversation_text = "\n".join([
                f"{msg.role.value}: {msg.content}"
                for msg in messages_to_summarize
            ])
            
            # Use Gemini to create summary - for now use a simple approach
            # TODO: Add summarize_conversation method to GeminiClient
            summary_prompt = f"""Please provide a concise summary of this conversation:

{conversation_text}

Focus on:
- Main topics discussed
- Key questions asked
- Important decisions or conclusions
- Document context used

Keep the summary under 200 words."""

            try:
                # For now, create a simple summary based on message count and topics
                # This can be enhanced with actual Gemini summarization later
                summary = f"Conversation with {len(messages_to_summarize)} messages covering document analysis and Q&A."
                
                logger.info(f"Generated simple summary for session {session_id}")
            except Exception as summary_error:
                logger.warning(f"Could not generate AI summary, using fallback: {summary_error}")
                summary = f"Conversation with {len(messages_to_summarize)} messages."
            
            if summary:
                # Update session with summary
                db = self.firestore_client.db
                session_ref = db.collection(self.sessions_collection).document(session_id)
                
                session_ref.update({
                    'context_summary': summary,
                    'updated_at': SERVER_TIMESTAMP
                })
                
                logger.info(f"Generated conversation summary for session {session_id}")
                return summary
            
        except Exception as e:
            logger.error(f"Failed to summarize conversation for {session_id}: {e}")
        
        return None