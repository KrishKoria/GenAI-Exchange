"""
Chat Session Pydantic models for conversation memory management
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Enumeration for message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Model for individual chat messages within a session."""
    message_id: str = Field(description="Unique message identifier")
    role: MessageRole = Field(description="Message role (user, assistant, system)")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sources: Optional[List[Dict[str, Any]]] = Field(
        description="Source citations for assistant messages", 
        default_factory=list
    )
    metadata: Optional[Dict[str, Any]] = Field(
        description="Additional message metadata",
        default_factory=dict
    )


class DocumentContext(BaseModel):
    """Model for document context within a chat session."""
    doc_id: str = Field(description="Document identifier")
    doc_name: str = Field(description="Human-readable document name")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    status: Optional[str] = Field(description="Document processing status", default=None)


class ChatSession(BaseModel):
    """Model for chat sessions with conversation memory."""
    session_id: str = Field(description="Unique session identifier")
    title: Optional[str] = Field(description="Session title", default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = Field(description="User identifier", default=None)
    
    # Document context
    selected_documents: List[DocumentContext] = Field(
        description="Documents selected for this chat session",
        default_factory=list
    )
    
    # Conversation memory
    messages: List[ChatMessage] = Field(
        description="Conversation history",
        default_factory=list
    )
    
    # Session metadata
    total_messages: int = Field(description="Total number of messages", default=0)
    total_questions: int = Field(description="Total number of user questions", default=0)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    
    # Memory management
    context_summary: Optional[str] = Field(
        description="Summary of conversation when context window exceeded",
        default=None
    )
    is_archived: bool = Field(description="Whether session is archived", default=False)


class CreateChatSessionRequest(BaseModel):
    """Request model for creating a new chat session."""
    title: Optional[str] = Field(description="Optional session title", default=None)
    user_id: Optional[str] = Field(description="User identifier", default=None)
    selected_document_ids: Optional[List[str]] = Field(
        description="Initial document selection",
        default_factory=list
    )


class CreateChatSessionResponse(BaseModel):
    """Response model for chat session creation."""
    session_id: str = Field(description="Created session identifier")
    title: Optional[str] = Field(description="Session title")
    created_at: datetime = Field(description="Creation timestamp")
    selected_documents: List[DocumentContext] = Field(
        description="Selected documents with metadata"
    )


class UpdateSessionDocumentsRequest(BaseModel):
    """Request model for updating session document context."""
    document_ids: List[str] = Field(description="Document IDs to associate with session")


class UpdateSessionDocumentsResponse(BaseModel):
    """Response model for updating session documents."""
    session_id: str = Field(description="Session identifier")
    selected_documents: List[DocumentContext] = Field(description="Updated document context")
    updated_at: datetime = Field(description="Update timestamp")


class ChatSessionListResponse(BaseModel):
    """Response model for listing chat sessions."""
    sessions: List[ChatSession] = Field(description="List of chat sessions")
    total_count: int = Field(description="Total number of sessions")
    
    
class ChatSessionResponse(BaseModel):
    """Response model for retrieving a single chat session."""
    session: ChatSession = Field(description="Chat session with full conversation history")


class AddMessageRequest(BaseModel):
    """Request model for adding a message to a chat session."""
    role: MessageRole = Field(description="Message role")
    content: str = Field(description="Message content")
    sources: Optional[List[Dict[str, Any]]] = Field(
        description="Source citations for assistant messages",
        default_factory=list
    )
    metadata: Optional[Dict[str, Any]] = Field(
        description="Additional message metadata",
        default_factory=dict
    )


class AddMessageResponse(BaseModel):
    """Response model for adding a message."""
    message_id: str = Field(description="Created message identifier")
    session_id: str = Field(description="Session identifier")
    timestamp: datetime = Field(description="Message timestamp")


class ChatQuestionRequest(BaseModel):
    """Enhanced question request with chat session context."""
    session_id: str = Field(description="Chat session identifier")
    question: str = Field(description="Question about the documents", min_length=1)
    include_conversation_history: bool = Field(
        description="Whether to include conversation history in context",
        default=True
    )
    max_history_messages: int = Field(
        description="Maximum number of previous messages to include",
        default=10,
        ge=0,
        le=50
    )


class ChatAnswerResponse(BaseModel):
    """Enhanced answer response with session context."""
    session_id: str = Field(description="Chat session identifier")
    message_id: str = Field(description="Created message identifier")
    answer: str = Field(description="Generated answer")
    used_clause_ids: List[str] = Field(description="List of clause IDs used for answer")
    confidence: float = Field(description="Answer confidence score", ge=0, le=1)
    sources: List[Dict[str, Any]] = Field(description="Source citations with snippets")
    conversation_context_used: bool = Field(
        description="Whether conversation history was used for context",
        default=False
    )
    additional_insights: Optional[str] = Field(
        description="Proactive insights and recommendations", 
        default=None
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionSummaryRequest(BaseModel):
    """Request model for generating session summary."""
    session_id: str = Field(description="Session to summarize")
    max_messages: int = Field(
        description="Maximum messages to include in summary",
        default=50,
        ge=1,
        le=200
    )


class SessionSummaryResponse(BaseModel):
    """Response model for session summary."""
    session_id: str = Field(description="Session identifier")
    summary: str = Field(description="Generated conversation summary")
    summarized_message_count: int = Field(description="Number of messages summarized")
    created_at: datetime = Field(default_factory=datetime.utcnow)