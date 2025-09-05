"""
Risk analysis service with LLM + keyword approach
"""
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import re

from app.core.logging import get_logger, LogContext
from app.models.document import RiskLevel

logger = get_logger(__name__)


class RiskCategory(Enum):
    """Categories of legal risks."""
    INDEMNITY = "indemnity"
    LIABILITY = "liability"
    TERMINATION = "termination"
    PAYMENT = "payment"
    CONFIDENTIALITY = "confidentiality"
    IP_OWNERSHIP = "ip_ownership"
    DISPUTE_RESOLUTION = "dispute_resolution"
    GOVERNING_LAW = "governing_law"
    ASSIGNMENT = "assignment"
    MODIFICATION = "modification"
    AUTO_RENEWAL = "auto_renewal"
    JURISDICTION = "jurisdiction"


@dataclass
class RiskKeyword:
    """Represents a risk-associated keyword with metadata."""
    keyword: str
    risk_weight: float  # 0.0 to 1.0
    categories: List[RiskCategory]
    requires_context: bool = False
    negative_contexts: Optional[List[str]] = None  # Contexts that reduce risk


@dataclass
class RiskAssessment:
    """Result of risk analysis for a clause."""
    risk_level: RiskLevel
    confidence: float
    risk_score: float  # 0.0 to 1.0
    detected_keywords: List[str]
    risk_factors: List[str]
    llm_assessment: Optional[Dict[str, Any]]
    keyword_assessment: Dict[str, Any]
    needs_review: bool
    explanation: str


class RiskAnalyzer:
    """Service for analyzing legal clause risks using hybrid approach."""
    
    def __init__(self):
        self.risk_keywords = self._initialize_risk_keywords()
        self.compiled_patterns = self._compile_keyword_patterns()
        
        # Risk level thresholds
        self.risk_thresholds = {
            "low": 0.3,
            "moderate": 0.6,
            "attention": 0.8
        }
    
    def _initialize_risk_keywords(self) -> List[RiskKeyword]:
        """Initialize risk keywords from PROJECT_OUTLINE specifications."""
        
        keywords = [
            # High-risk indemnification terms
            RiskKeyword(
                keyword="indemnify|indemnification|indemnities",
                risk_weight=0.8,
                categories=[RiskCategory.INDEMNITY],
                requires_context=True,
                negative_contexts=["mutual indemnification", "limited indemnification"]
            ),
            RiskKeyword(
                keyword="hold harmless",
                risk_weight=0.9,
                categories=[RiskCategory.INDEMNITY, RiskCategory.LIABILITY]
            ),
            RiskKeyword(
                keyword="defend",
                risk_weight=0.7,
                categories=[RiskCategory.INDEMNITY],
                requires_context=True,
                negative_contexts=["right to defend", "option to defend"]
            ),
            
            # Unlimited liability terms
            RiskKeyword(
                keyword="unlimited",
                risk_weight=0.95,
                categories=[RiskCategory.LIABILITY]
            ),
            RiskKeyword(
                keyword="without limit|no limit",
                risk_weight=0.9,
                categories=[RiskCategory.LIABILITY]
            ),
            RiskKeyword(
                keyword="consequential damages",
                risk_weight=0.8,
                categories=[RiskCategory.LIABILITY],
                negative_contexts=["excluding consequential", "no consequential"]
            ),
            RiskKeyword(
                keyword="punitive damages",
                risk_weight=0.85,
                categories=[RiskCategory.LIABILITY],
                negative_contexts=["excluding punitive", "no punitive"]
            ),
            
            # Automatic renewal risks
            RiskKeyword(
                keyword="automatic renewal|auto-renewal|automatically renew",
                risk_weight=0.7,
                categories=[RiskCategory.AUTO_RENEWAL, RiskCategory.TERMINATION]
            ),
            RiskKeyword(
                keyword="perpetual|in perpetuity",
                risk_weight=0.9,
                categories=[RiskCategory.TERMINATION, RiskCategory.AUTO_RENEWAL]
            ),
            RiskKeyword(
                keyword="rolling basis|successive periods",
                risk_weight=0.6,
                categories=[RiskCategory.AUTO_RENEWAL]
            ),
            
            # Termination risks
            RiskKeyword(
                keyword="terminate without cause|terminate for convenience",
                risk_weight=0.8,
                categories=[RiskCategory.TERMINATION]
            ),
            RiskKeyword(
                keyword="immediate termination|terminate immediately",
                risk_weight=0.7,
                categories=[RiskCategory.TERMINATION]
            ),
            RiskKeyword(
                keyword="sole discretion",
                risk_weight=0.75,
                categories=[RiskCategory.TERMINATION, RiskCategory.MODIFICATION]
            ),
            
            # Payment risks
            RiskKeyword(
                keyword="liquidated damages",
                risk_weight=0.8,
                categories=[RiskCategory.PAYMENT, RiskCategory.LIABILITY]
            ),
            RiskKeyword(
                keyword="penalty|penalties",
                risk_weight=0.75,
                categories=[RiskCategory.PAYMENT]
            ),
            RiskKeyword(
                keyword="late fees|interest on overdue",
                risk_weight=0.5,
                categories=[RiskCategory.PAYMENT]
            ),
            
            # Jurisdiction and legal risks
            RiskKeyword(
                keyword="exclusive jurisdiction",
                risk_weight=0.7,
                categories=[RiskCategory.JURISDICTION, RiskCategory.DISPUTE_RESOLUTION]
            ),
            RiskKeyword(
                keyword="waive|waiver",
                risk_weight=0.8,
                categories=[RiskCategory.DISPUTE_RESOLUTION],
                requires_context=True
            ),
            RiskKeyword(
                keyword="jury trial waiver|waive jury trial",
                risk_weight=0.85,
                categories=[RiskCategory.DISPUTE_RESOLUTION]
            ),
            
            # Assignment risks
            RiskKeyword(
                keyword="assignment without consent|assign without consent",
                risk_weight=0.7,
                categories=[RiskCategory.ASSIGNMENT]
            ),
            RiskKeyword(
                keyword="freely assign|assign freely",
                risk_weight=0.6,
                categories=[RiskCategory.ASSIGNMENT]
            ),
            
            # IP and confidentiality risks
            RiskKeyword(
                keyword="work for hire|work made for hire",
                risk_weight=0.8,
                categories=[RiskCategory.IP_OWNERSHIP]
            ),
            RiskKeyword(
                keyword="all rights|exclusive rights",
                risk_weight=0.7,
                categories=[RiskCategory.IP_OWNERSHIP],
                requires_context=True
            ),
            RiskKeyword(
                keyword="perpetual confidentiality|indefinite confidentiality",
                risk_weight=0.6,
                categories=[RiskCategory.CONFIDENTIALITY]
            ),
            
            # Modification risks
            RiskKeyword(
                keyword="unilateral|unilaterally",
                risk_weight=0.75,
                categories=[RiskCategory.MODIFICATION],
                requires_context=True
            ),
            RiskKeyword(
                keyword="at any time|without notice",
                risk_weight=0.65,
                categories=[RiskCategory.MODIFICATION, RiskCategory.TERMINATION],
                requires_context=True
            ),
        ]
        
        return keywords
    
    def _compile_keyword_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for efficient keyword matching."""
        patterns = {}
        
        for risk_keyword in self.risk_keywords:
            pattern = re.compile(
                rf'\b({risk_keyword.keyword})\b',
                re.IGNORECASE | re.MULTILINE
            )
            patterns[risk_keyword.keyword] = pattern
        
        return patterns
    
    async def analyze_clause_risk(
        self, 
        clause_text: str,
        clause_summary: Optional[str] = None,
        llm_risk_assessment: Optional[str] = None,
        clause_category: Optional[str] = None
    ) -> RiskAssessment:
        """
        Analyze risk level of a clause using hybrid approach.
        
        Args:
            clause_text: Original clause text
            clause_summary: Plain language summary
            llm_risk_assessment: Risk level from LLM ("low", "moderate", "attention")
            clause_category: Clause category for context
            
        Returns:
            Comprehensive risk assessment
        """
        with LogContext(logger, clause_length=len(clause_text), category=clause_category):
            logger.info("Analyzing clause risk")
            
            # Step 1: Keyword-based analysis
            keyword_assessment = await self._analyze_keywords(clause_text, clause_summary)
            
            # Step 2: Parse LLM assessment
            llm_assessment = self._parse_llm_assessment(llm_risk_assessment)
            
            # Step 3: Hybrid scoring
            hybrid_score = await self._calculate_hybrid_score(
                keyword_assessment, llm_assessment, clause_category
            )
            
            # Step 4: Determine final risk level
            final_risk_level = self._determine_risk_level(hybrid_score)
            
            # Step 5: Conflict detection and review flagging
            needs_review = await self._detect_conflicts(
                keyword_assessment, llm_assessment, hybrid_score
            )
            
            # Step 6: Generate explanation
            explanation = await self._generate_risk_explanation(
                keyword_assessment, llm_assessment, final_risk_level, needs_review
            )
            
            assessment = RiskAssessment(
                risk_level=final_risk_level,
                confidence=self._calculate_confidence(keyword_assessment, llm_assessment),
                risk_score=hybrid_score,
                detected_keywords=keyword_assessment["detected_keywords"],
                risk_factors=keyword_assessment["risk_factors"],
                llm_assessment=llm_assessment,
                keyword_assessment=keyword_assessment,
                needs_review=needs_review,
                explanation=explanation
            )
            
            logger.info(f"Risk analysis complete: {final_risk_level.value} (score: {hybrid_score:.3f})")
            
            return assessment
    
    async def _analyze_keywords(
        self, 
        clause_text: str, 
        clause_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze clause using keyword patterns.
        
        Args:
            clause_text: Original clause text
            clause_summary: Optional summary text
            
        Returns:
            Keyword analysis results
        """
        # Combine text sources for analysis
        analysis_text = clause_text
        if clause_summary:
            analysis_text += f"\n{clause_summary}"
        
        detected_keywords = []
        risk_factors = []
        category_scores = {category: 0.0 for category in RiskCategory}
        total_risk_score = 0.0
        
        for risk_keyword in self.risk_keywords:
            pattern = self.compiled_patterns[risk_keyword.keyword]
            matches = pattern.findall(analysis_text)
            
            if matches:
                detected_keywords.extend([match.lower() if isinstance(match, str) else match[0].lower() for match in matches])
                
                # Calculate context-adjusted risk score
                keyword_risk = risk_keyword.risk_weight
                
                # Check for negative contexts that reduce risk
                if risk_keyword.negative_contexts:
                    for neg_context in risk_keyword.negative_contexts:
                        if re.search(neg_context, analysis_text, re.IGNORECASE):
                            keyword_risk *= 0.5  # Reduce risk by half
                            risk_factors.append(f"Mitigated: {neg_context}")
                            break
                
                total_risk_score += keyword_risk
                
                # Add to category scores
                for category in risk_keyword.categories:
                    category_scores[category] = max(category_scores[category], keyword_risk)
                
                risk_factors.append(f"High-risk keyword: {matches[0]}")
        
        # Normalize total risk score
        if detected_keywords:
            total_risk_score = min(1.0, total_risk_score / len(detected_keywords))
        
        return {
            "risk_score": total_risk_score,
            "detected_keywords": list(set(detected_keywords)),
            "risk_factors": risk_factors,
            "category_scores": category_scores,
            "keyword_count": len(set(detected_keywords)),
            "method": "keyword_analysis"
        }
    
    def _parse_llm_assessment(self, llm_risk_assessment: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Parse and validate LLM risk assessment.
        
        Args:
            llm_risk_assessment: Risk level from LLM
            
        Returns:
            Parsed LLM assessment data
        """
        if not llm_risk_assessment:
            return None
        
        # Normalize the assessment
        assessment_lower = llm_risk_assessment.lower().strip()
        
        # Map to our risk levels
        risk_level_map = {
            "low": 0.2,
            "moderate": 0.5,
            "attention": 0.8,
            "high": 0.8,
            "critical": 0.9
        }
        
        risk_score = risk_level_map.get(assessment_lower, 0.5)
        
        return {
            "original_assessment": llm_risk_assessment,
            "normalized_level": assessment_lower,
            "risk_score": risk_score,
            "confidence": 0.8,  # Default LLM confidence
            "method": "llm_assessment"
        }
    
    async def _calculate_hybrid_score(
        self, 
        keyword_assessment: Dict[str, Any],
        llm_assessment: Optional[Dict[str, Any]],
        clause_category: Optional[str]
    ) -> float:
        """
        Calculate hybrid risk score combining keyword and LLM assessments.
        
        Args:
            keyword_assessment: Keyword analysis results
            llm_assessment: LLM assessment results
            clause_category: Clause category for weighting
            
        Returns:
            Combined risk score (0.0 to 1.0)
        """
        keyword_score = keyword_assessment.get("risk_score", 0.0)
        
        if llm_assessment:
            llm_score = llm_assessment.get("risk_score", 0.5)
            
            # Weight the scores based on presence of keywords
            if keyword_assessment.get("keyword_count", 0) > 0:
                # Keywords detected: give more weight to keyword analysis
                hybrid_score = (keyword_score * 0.7) + (llm_score * 0.3)
            else:
                # No keywords: rely more on LLM
                hybrid_score = (keyword_score * 0.3) + (llm_score * 0.7)
        else:
            # Only keyword analysis available
            hybrid_score = keyword_score
        
        # Apply category-specific adjustments
        if clause_category:
            category_multiplier = self._get_category_risk_multiplier(clause_category)
            hybrid_score *= category_multiplier
        
        return min(1.0, hybrid_score)
    
    def _get_category_risk_multiplier(self, clause_category: str) -> float:
        """
        Get risk multiplier based on clause category.
        
        Args:
            clause_category: Clause category
            
        Returns:
            Risk multiplier (0.8 to 1.2)
        """
        # Categories with inherently higher risk
        high_risk_categories = {
            "Indemnity": 1.2,
            "Liability": 1.15,
            "Termination": 1.1,
            "Assignment": 1.1
        }
        
        # Categories with moderate risk
        moderate_risk_categories = {
            "Payment": 1.0,
            "Confidentiality": 1.0,
            "IP Ownership": 1.05,
            "Dispute Resolution": 1.05
        }
        
        # Lower risk categories
        low_risk_categories = {
            "Governing Law": 0.9,
            "Modification": 0.95,
            "Other": 0.9
        }
        
        return (
            high_risk_categories.get(clause_category) or
            moderate_risk_categories.get(clause_category) or
            low_risk_categories.get(clause_category, 1.0)
        )
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """
        Convert risk score to risk level.
        
        Args:
            risk_score: Numerical risk score
            
        Returns:
            Risk level enum
        """
        if risk_score >= self.risk_thresholds["attention"]:
            return RiskLevel.ATTENTION
        elif risk_score >= self.risk_thresholds["moderate"]:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW
    
    async def _detect_conflicts(
        self,
        keyword_assessment: Dict[str, Any],
        llm_assessment: Optional[Dict[str, Any]],
        hybrid_score: float
    ) -> bool:
        """
        Detect conflicts between LLM and keyword assessments.
        
        Args:
            keyword_assessment: Keyword analysis results
            llm_assessment: LLM assessment results
            hybrid_score: Combined risk score
            
        Returns:
            True if manual review is needed
        """
        needs_review = False
        
        if llm_assessment:
            keyword_level = self._determine_risk_level(keyword_assessment["risk_score"])
            llm_level = self._determine_risk_level(llm_assessment["risk_score"])
            
            # Flag for review if there's a significant disagreement
            if abs(keyword_assessment["risk_score"] - llm_assessment["risk_score"]) > 0.4:
                needs_review = True
                logger.info(f"Risk assessment conflict detected: keyword={keyword_level.value}, llm={llm_level.value}")
        
        # Flag high-risk items for review
        if hybrid_score >= 0.8:
            needs_review = True
        
        # Flag items with many risk keywords
        if keyword_assessment.get("keyword_count", 0) >= 3:
            needs_review = True
        
        return needs_review
    
    def _calculate_confidence(
        self,
        keyword_assessment: Dict[str, Any],
        llm_assessment: Optional[Dict[str, Any]]
    ) -> float:
        """
        Calculate confidence in the risk assessment.
        
        Args:
            keyword_assessment: Keyword analysis results
            llm_assessment: LLM assessment results
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        base_confidence = 0.6
        
        # Increase confidence with keyword detection
        if keyword_assessment.get("keyword_count", 0) > 0:
            base_confidence += 0.2
        
        # Increase confidence with LLM agreement
        if llm_assessment:
            keyword_score = keyword_assessment.get("risk_score", 0.0)
            llm_score = llm_assessment.get("risk_score", 0.5)
            
            # Higher confidence when both methods agree
            agreement = 1.0 - abs(keyword_score - llm_score)
            base_confidence += agreement * 0.2
        
        return min(1.0, base_confidence)
    
    async def _generate_risk_explanation(
        self,
        keyword_assessment: Dict[str, Any],
        llm_assessment: Optional[Dict[str, Any]],
        risk_level: RiskLevel,
        needs_review: bool
    ) -> str:
        """
        Generate human-readable risk explanation.
        
        Args:
            keyword_assessment: Keyword analysis results
            llm_assessment: LLM assessment results
            risk_level: Final risk level
            needs_review: Whether manual review is needed
            
        Returns:
            Risk explanation text
        """
        explanation_parts = []
        
        # Risk level explanation
        level_explanations = {
            RiskLevel.LOW: "This clause appears to have minimal risk.",
            RiskLevel.MODERATE: "This clause contains terms that require attention.",
            RiskLevel.ATTENTION: "This clause contains potentially problematic terms."
        }
        explanation_parts.append(level_explanations[risk_level])
        
        # Keyword findings
        detected_keywords = keyword_assessment.get("detected_keywords", [])
        if detected_keywords:
            explanation_parts.append(
                f"Risk keywords detected: {', '.join(detected_keywords[:3])}{'...' if len(detected_keywords) > 3 else ''}."
            )
        
        # Risk factors
        risk_factors = keyword_assessment.get("risk_factors", [])
        if risk_factors:
            top_factors = risk_factors[:2]  # Show top 2 factors
            explanation_parts.append(f"Key concerns: {'. '.join(top_factors)}.")
        
        # Review recommendation
        if needs_review:
            explanation_parts.append("Manual legal review recommended.")
        
        return " ".join(explanation_parts)
    
    async def analyze_document_risk_profile(
        self, 
        clause_assessments: List[RiskAssessment]
    ) -> Dict[str, Any]:
        """
        Analyze overall risk profile for a document.
        
        Args:
            clause_assessments: List of individual clause assessments
            
        Returns:
            Document-level risk analysis
        """
        if not clause_assessments:
            return {
                "overall_risk_level": "low",
                "total_clauses": 0,
                "risk_distribution": {"low": 0, "moderate": 0, "attention": 0},
                "needs_review_count": 0,
                "top_risks": [],
                "average_risk_score": 0.0
            }
        
        # Calculate risk distribution
        risk_distribution = {"low": 0, "moderate": 0, "attention": 0}
        needs_review_count = 0
        total_risk_score = 0.0
        top_risks = []
        
        for assessment in clause_assessments:
            risk_distribution[assessment.risk_level.value] += 1
            total_risk_score += assessment.risk_score
            
            if assessment.needs_review:
                needs_review_count += 1
            
            # Collect high-risk clauses for top risks
            if assessment.risk_level == RiskLevel.ATTENTION:
                top_risks.append({
                    "risk_factors": assessment.risk_factors[:2],  # Top 2 factors
                    "risk_score": assessment.risk_score,
                    "keywords": assessment.detected_keywords[:3]  # Top 3 keywords
                })
        
        # Sort top risks by score
        top_risks.sort(key=lambda x: x["risk_score"], reverse=True)
        top_risks = top_risks[:5]  # Keep top 5
        
        # Determine overall risk level
        attention_ratio = risk_distribution["attention"] / len(clause_assessments)
        moderate_ratio = risk_distribution["moderate"] / len(clause_assessments)
        
        if attention_ratio >= 0.3:  # 30% or more high-risk clauses
            overall_risk = "attention"
        elif attention_ratio >= 0.1 or moderate_ratio >= 0.5:  # 10% high-risk or 50% moderate
            overall_risk = "moderate"
        else:
            overall_risk = "low"
        
        return {
            "overall_risk_level": overall_risk,
            "total_clauses": len(clause_assessments),
            "risk_distribution": risk_distribution,
            "needs_review_count": needs_review_count,
            "top_risks": top_risks,
            "average_risk_score": total_risk_score / len(clause_assessments),
            "risk_ratios": {
                "attention_ratio": attention_ratio,
                "moderate_ratio": moderate_ratio,
                "low_ratio": risk_distribution["low"] / len(clause_assessments)
            }
        }