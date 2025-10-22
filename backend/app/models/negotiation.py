"""
Negotiation-related Pydantic models for AI-powered clause alternatives
"""
from typing import Dict, Optional, Any, List
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.document import RiskLevel, SupportedLanguage


class AlternativeType(str, Enum):
    """Type of negotiation alternative."""
    BALANCED = "balanced"
    PROTECTIVE = "protective"
    SIMPLIFIED = "simplified"


class NegotiationAlternative(BaseModel):
    """Model for a single negotiation alternative."""
    alternative_id: Optional[str] = Field(default=None, description="Unique identifier for this alternative")
    alternative_text: str = Field(description="The complete rewritten clause text")
    strategic_benefit: str = Field(description="Why this alternative is better")
    risk_reduction: str = Field(description="Specific risks this alternative mitigates")
    implementation_notes: str = Field(description="Practical advice for proposing this change")
    confidence: float = Field(ge=0.0, le=1.0, description="AI confidence in this alternative")
    alternative_type: AlternativeType = Field(description="Type of alternative approach")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NegotiationRequest(BaseModel):
    """Request model for generating negotiation alternatives."""
    clause_text: str = Field(description="The original clause text to generate alternatives for")
    clause_category: Optional[str] = Field(default=None, description="Category of the clause")
    risk_level: Optional[RiskLevel] = Field(default=None, description="Pre-assessed risk level")
    language: SupportedLanguage = Field(
        default=SupportedLanguage.ENGLISH,
        description="Language for generating alternatives"
    )
    document_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context about the document"
    )
    user_preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User preferences for alternative generation"
    )
    clause_id: Optional[str] = Field(default=None, description="ID of the clause in the system")
    doc_id: Optional[str] = Field(default=None, description="ID of the document this clause belongs to")


class BatchNegotiationRequest(BaseModel):
    """Request model for batch negotiation alternative generation."""
    clause_ids: List[str] = Field(description="List of clause IDs to generate alternatives for")
    doc_id: str = Field(description="Document ID containing the clauses")
    document_context: Optional[Dict[str, Any]] = Field(default=None)
    user_preferences: Optional[Dict[str, Any]] = Field(default=None)
    max_concurrent: int = Field(default=5, ge=1, le=10, description="Max concurrent generations")


class RiskAnalysisSummary(BaseModel):
    """Summary of risk analysis for the original clause."""
    risk_level: RiskLevel = Field(description="Overall risk level")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in risk assessment")
    risk_score: float = Field(ge=0.0, le=1.0, description="Numerical risk score")
    detected_keywords: List[str] = Field(default_factory=list, description="Risk keywords detected")
    risk_factors: List[str] = Field(default_factory=list, description="Specific risk factors identified")


class NegotiationResponse(BaseModel):
    """Response model for negotiation alternatives."""
    negotiation_id: Optional[str] = Field(default=None, description="Unique identifier for this negotiation")
    original_clause: str = Field(description="The original clause text")
    original_risk_level: RiskLevel = Field(description="Risk level of original clause")
    alternatives: List[NegotiationAlternative] = Field(
        description="List of generated alternatives (typically 3)"
    )
    risk_analysis: Optional[RiskAnalysisSummary] = Field(
        default=None,
        description="Risk analysis summary"
    )
    generation_time: float = Field(description="Time taken to generate alternatives (seconds)")
    model_used: str = Field(description="AI model used for generation")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    clause_id: Optional[str] = Field(default=None, description="ID of the clause in the system")
    doc_id: Optional[str] = Field(default=None, description="ID of the document")


class BatchNegotiationResponse(BaseModel):
    """Response model for batch negotiation generation."""
    doc_id: str = Field(description="Document ID")
    total_clauses: int = Field(description="Total number of clauses requested")
    successful: int = Field(description="Number of successful generations")
    failed: int = Field(description="Number of failed generations")
    negotiations: List[NegotiationResponse] = Field(
        description="List of successful negotiation responses"
    )
    generation_time: float = Field(description="Total time for batch generation (seconds)")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SaveNegotiationRequest(BaseModel):
    """Request model for saving a negotiation interaction."""
    negotiation_id: str = Field(description="ID of the negotiation to save")
    doc_id: str = Field(description="Document ID")
    clause_id: str = Field(description="Clause ID")
    selected_alternative_id: Optional[str] = Field(
        default=None,
        description="ID of the alternative the user selected (if any)"
    )
    user_feedback: Optional[str] = Field(
        default=None,
        description="Optional user feedback"
    )
    was_helpful: Optional[bool] = Field(
        default=None,
        description="Whether the alternatives were helpful"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )


class NegotiationHistory(BaseModel):
    """Model for stored negotiation history."""
    negotiation_id: str = Field(description="Unique identifier")
    doc_id: str = Field(description="Document ID")
    clause_id: str = Field(description="Clause ID")
    original_clause: str = Field(description="Original clause text")
    alternatives: List[NegotiationAlternative] = Field(description="Generated alternatives")
    selected_alternative_id: Optional[str] = Field(default=None)
    user_feedback: Optional[str] = Field(default=None)
    was_helpful: Optional[bool] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)


class NegotiationHistoryResponse(BaseModel):
    """Response model for negotiation history query."""
    doc_id: str = Field(description="Document ID")
    total_negotiations: int = Field(description="Total number of negotiations")
    negotiations: List[NegotiationHistory] = Field(description="List of negotiation history entries")
    query_time: float = Field(description="Time taken to query (seconds)")


class NegotiationStats(BaseModel):
    """Statistics about negotiation usage."""
    total_negotiations: int = Field(description="Total negotiations generated")
    total_alternatives: int = Field(description="Total alternatives generated")
    average_generation_time: float = Field(description="Average generation time (seconds)")
    most_common_categories: List[Dict[str, Any]] = Field(
        description="Most common clause categories with counts"
    )
    alternative_selection_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Rate at which users select alternatives"
    )
    helpful_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Rate at which users find alternatives helpful"
    )


class QuickAlternativeRequest(BaseModel):
    """Simplified request for quick alternative generation (for demo)."""
    clause_text: str = Field(description="The clause text")
    clause_category: Optional[str] = Field(default="Other")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "clause_text": "The Company shall be indemnified and held harmless from any and all claims...",
                "clause_category": "Indemnity"
            }
        }


class QuickAlternativeResponse(BaseModel):
    """Simplified response for quick alternative display."""
    original_clause: str = Field(description="Original clause")
    alternatives: List[Dict[str, str]] = Field(
        description="Simplified alternatives with text, benefit, and type"
    )
    generation_time: float = Field(description="Generation time in seconds")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "original_clause": "The Company shall be indemnified...",
                "alternatives": [
                    {
                        "text": "Mutual indemnification clause...",
                        "benefit": "Creates balanced protection for both parties",
                        "type": "balanced"
                    }
                ],
                "generation_time": 1.2
            }
        }
