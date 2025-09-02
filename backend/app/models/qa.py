"""
Question and Answer Pydantic models
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    """Request model for asking questions about documents."""
    doc_id: str = Field(description="Document identifier")
    question: str = Field(description="Question about the document", min_length=1)
    session_id: Optional[str] = Field(description="Session identifier for tracking")


class SourceCitation(BaseModel):
    """Model for source citations in answers."""
    clause_id: str = Field(description="Referenced clause identifier")
    snippet: str = Field(description="Relevant text snippet from clause")
    relevance_score: float = Field(description="Relevance score", ge=0, le=1)


class AnswerResponse(BaseModel):
    """Response model for question answers."""
    answer: str = Field(description="Generated answer")
    used_clause_ids: List[str] = Field(description="List of clause IDs used for answer")
    confidence: float = Field(description="Answer confidence score", ge=0, le=1)
    sources: List[SourceCitation] = Field(description="Source citations with snippets")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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