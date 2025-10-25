"""
Question and Answer Pydantic models
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field
from app.models.document import SupportedLanguage


class QuestionRequest(BaseModel):
    """Request model for asking questions about documents."""
    doc_id: str = Field(description="Document identifier")
    question: str = Field(description="Question about the document", min_length=1)
    session_id: Optional[str] = Field(description="Session identifier for tracking")
    chat_session_id: Optional[str] = Field(description="Chat session identifier for memory context", default=None)
    use_conversation_memory: bool = Field(description="Whether to use conversation memory", default=False)

    # Auto Language Detection fields
    auto_detect_language: bool = Field(description="Automatically detect language from question", default=True)
    language_override: Optional[SupportedLanguage] = Field(description="Manual language override", default=None)
    session_context: Optional[str] = Field(description="Additional context for better language detection", default=None)


class SourceCitation(BaseModel):
    """Model for source citations in answers."""
    clause_id: str = Field(description="Referenced clause identifier")
    clause_number: Optional[int] = Field(description="Clause number in document", default=None)
    category: Optional[str] = Field(description="Clause category", default=None)
    snippet: str = Field(description="Relevant text snippet from clause")
    relevance_score: float = Field(description="Relevance score", ge=0, le=1)
    doc_id: Optional[str] = Field(description="Source document identifier", default=None)
    doc_name: Optional[str] = Field(description="Source document name", default=None)


class AnswerResponse(BaseModel):
    """Response model for question answers."""
    answer: str = Field(description="Generated answer")
    used_clause_ids: List[str] = Field(description="List of clause IDs used for answer")
    confidence: float = Field(description="Answer confidence score", ge=0, le=1)
    sources: List[SourceCitation] = Field(description="Source citations with snippets")
    additional_insights: Optional[str] = Field(description="Proactive insights and recommendations", default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    chat_session_id: Optional[str] = Field(description="Associated chat session", default=None)
    conversation_context_used: bool = Field(description="Whether conversation history was used", default=False)

    # Language Detection Information
    detected_language: Optional[SupportedLanguage] = Field(description="Automatically detected language", default=None)
    response_language: SupportedLanguage = Field(description="Language used for response", default=SupportedLanguage.ENGLISH)
    language_detection_confidence: Optional[float] = Field(description="Language detection confidence", default=None)
    detection_method: Optional[str] = Field(description="Method used for detection", default=None)


class QAHistory(BaseModel):
    """Model for Q&A history entries."""
    qa_id: str = Field(description="Unique Q&A identifier")
    doc_id: str = Field(description="Document identifier")
    question: str = Field(description="Original question")
    answer: str = Field(description="Generated answer")
    clause_ids: List[str] = Field(description="Referenced clause IDs")
    confidence: float = Field(description="Answer confidence")
    timestamp: datetime = Field(description="Q&A timestamp")
    session_id: Optional[str] = Field(description="Session identifier")


class QAMetrics(BaseModel):
    """Model for Q&A performance metrics."""
    total_questions: int = Field(description="Total number of questions")
    avg_confidence: float = Field(description="Average confidence score")
    citation_coverage: float = Field(description="Percentage of answers with citations")
    avg_response_time_ms: int = Field(description="Average response time in milliseconds")
    common_question_types: List[Dict[str, Any]] = Field(description="Most common question patterns")