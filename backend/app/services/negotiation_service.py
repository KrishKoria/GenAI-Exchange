"""
Negotiation Service - AI-Powered Clause Alternative Generation

This service generates strategic alternatives for risky contract clauses,
empowering users with negotiation leverage and safer contract options.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import asyncio
import uuid

from app.core.logging import get_logger, LogContext
from app.models.document import RiskLevel, ClauseDetail
from app.models.negotiation import (
    NegotiationAlternative,
    NegotiationResponse,
    AlternativeType,
    RiskAnalysisSummary
)
from app.services.risk_analyzer import RiskAnalyzer, RiskAssessment


logger = get_logger(__name__)


class NegotiationService:
    """
    Service for generating AI-powered negotiation alternatives for contract clauses.
    
    Features:
    - Generates 3 distinct alternatives per risky clause
    - Provides strategic benefits and implementation guidance
    - Context-aware suggestions based on risk assessment
    - Caching for common clause patterns
    - Batch processing support
    """
    
    def __init__(
        self,
        gemini_client: Any,  # GeminiClient instance
        risk_analyzer: Optional[RiskAnalyzer] = None,
        enable_caching: bool = True,
        cache_ttl: int = 3600  # 1 hour
    ):
        """
        Initialize NegotiationService.
        
        Args:
            gemini_client: Instance of GeminiClient for AI generation
            risk_analyzer: Optional RiskAnalyzer for context-aware suggestions
            enable_caching: Enable caching of common alternatives
            cache_ttl: Cache time-to-live in seconds
        """
        self.gemini_client = gemini_client
        self.risk_analyzer = risk_analyzer or RiskAnalyzer()
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[NegotiationResponse, float]] = {}
        
        logger.info("NegotiationService initialized", extra={
            "caching_enabled": enable_caching,
            "cache_ttl": cache_ttl
        })
    
    async def generate_alternatives(
        self,
        clause_text: str,
        clause_category: Optional[str] = None,
        risk_level: Optional[RiskLevel] = None,
        document_context: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> NegotiationResponse:
        """
        Generate negotiation alternatives for a single clause.
        
        Args:
            clause_text: The original clause text
            clause_category: Category of the clause (e.g., "Indemnity", "Liability")
            risk_level: Pre-assessed risk level (will analyze if not provided)
            document_context: Additional context about the document
            user_preferences: User preferences for alternative generation
            
        Returns:
            NegotiationResponse with alternatives and analysis
        """
        start_time = datetime.utcnow()
        
        with LogContext(logger, clause_category=clause_category, clause_risk_level=risk_level, has_context=bool(document_context)):
            logger.info("Generating negotiation alternatives for clause")
            
            try:
                # Check cache first
                if self.enable_caching:
                    cached_response = self._get_cached_response(clause_text)
                    if cached_response:
                        logger.info("Returning cached negotiation alternatives")
                        return cached_response
                
                # Perform risk analysis if not provided
                risk_assessment = None
                if risk_level is None:
                    risk_assessment = await self.risk_analyzer.analyze_clause_risk(
                        clause_text=clause_text,
                        clause_category=clause_category or "Other"
                    )
                    risk_level = risk_assessment.risk_level
                
                # Build negotiation prompt
                prompt = self._build_negotiation_prompt(
                    clause_text=clause_text,
                    clause_category=clause_category,
                    risk_level=risk_level,
                    risk_assessment=risk_assessment,
                    document_context=document_context,
                    user_preferences=user_preferences
                )
                
                # Generate alternatives using Gemini
                gemini_response = await self._call_gemini_for_alternatives(prompt)
                
                # Parse and validate alternatives
                alternatives = self._parse_alternatives_response(gemini_response)
                
                # Calculate generation time
                generation_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Convert risk assessment to summary
                risk_summary = None
                if risk_assessment:
                    risk_summary = RiskAnalysisSummary(
                        risk_level=risk_assessment.risk_level,
                        confidence=risk_assessment.confidence,
                        risk_score=risk_assessment.risk_score,
                        detected_keywords=risk_assessment.detected_keywords,
                        risk_factors=risk_assessment.risk_factors
                    )
                
                # Build response
                response = NegotiationResponse(
                    negotiation_id=str(uuid.uuid4()),
                    original_clause=clause_text,
                    original_risk_level=risk_level,
                    alternatives=alternatives,
                    risk_analysis=risk_summary,
                    generation_time=generation_time,
                    model_used="gemini-2.5-flash",
                    context={
                        "category": clause_category,
                        "document_context": document_context,
                        "user_preferences": user_preferences
                    }
                )
                
                # Cache the response
                if self.enable_caching:
                    self._cache_response(clause_text, response)
                
                logger.info(
                    "Successfully generated negotiation alternatives",
                    extra={
                        "num_alternatives": len(alternatives),
                        "generation_time": generation_time,
                        "clause_risk_level": risk_level
                    }
                )
                
                return response
                
            except Exception as e:
                logger.error(f"Failed to generate negotiation alternatives: {e}", exc_info=True)
                raise
    
    async def generate_batch_alternatives(
        self,
        clauses: List[ClauseDetail],
        document_context: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
        max_concurrent: int = 5
    ) -> List[NegotiationResponse]:
        """
        Generate negotiation alternatives for multiple clauses in batch.
        
        Args:
            clauses: List of ClauseDetail objects to generate alternatives for
            document_context: Additional context about the document
            user_preferences: User preferences for alternative generation
            max_concurrent: Maximum number of concurrent generations
            
        Returns:
            List of NegotiationResponse objects
        """
        logger.info(f"Starting batch alternative generation for {len(clauses)} clauses")
        
        # Filter clauses that need alternatives (moderate/attention risk)
        risky_clauses = [
            c for c in clauses 
            if c.risk_level in [RiskLevel.MODERATE, RiskLevel.ATTENTION]
        ]
        
        if not risky_clauses:
            logger.info("No risky clauses found requiring alternatives")
            return []
        
        logger.info(f"Generating alternatives for {len(risky_clauses)} risky clauses")
        
        # Create tasks for concurrent generation
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(clause: ClauseDetail) -> NegotiationResponse:
            async with semaphore:
                return await self.generate_alternatives(
                    clause_text=clause.original_text,
                    clause_category=clause.category,
                    risk_level=clause.risk_level,
                    document_context=document_context,
                    user_preferences=user_preferences
                )
        
        # Execute batch generation
        tasks = [generate_with_semaphore(clause) for clause in risky_clauses]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed generations
        successful_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(
                    f"Failed to generate alternatives for clause {i}: {response}",
                    exc_info=response
                )
            else:
                successful_responses.append(response)
        
        logger.info(
            f"Batch generation complete: {len(successful_responses)}/{len(risky_clauses)} successful"
        )
        
        return successful_responses
    
    def _build_negotiation_prompt(
        self,
        clause_text: str,
        clause_category: Optional[str],
        risk_level: RiskLevel,
        risk_assessment: Optional[RiskAssessment],
        document_context: Optional[Dict[str, Any]],
        user_preferences: Optional[Dict[str, Any]]
    ) -> str:
        """Build the negotiation prompt for Gemini."""
        
        # Base system instructions
        prompt = (
            "You are an expert contract negotiation advisor helping users understand "
            "and negotiate better contract terms. Your role is to generate strategic "
            "alternatives to risky or unfavorable contract clauses.\n\n"
            
            "TASK: Generate exactly 3 distinct alternative versions of the provided clause, "
            "each with a different strategic approach:\n"
            "1. BALANCED: A middle-ground alternative that addresses the main risks while remaining reasonable\n"
            "2. PROTECTIVE: A more protective alternative that significantly reduces risk\n"
            "3. SIMPLIFIED: A clearer, simpler version that removes ambiguity\n\n"
            
            "For each alternative, provide:\n"
            "- alternative_text: The complete rewritten clause text (full clause, not a fragment)\n"
            "- strategic_benefit: Why this alternative is better (1-2 sentences)\n"
            "- risk_reduction: Specific risks this alternative mitigates\n"
            "- implementation_notes: Practical advice for proposing this change\n"
            "- confidence: Your confidence in this alternative (0.0 to 1.0)\n\n"
            
            "REQUIREMENTS:\n"
            "- Each alternative must be a complete, standalone clause\n"
            "- Maintain professional legal language\n"
            "- Be specific and actionable\n"
            "- Focus on practical negotiation leverage\n"
            "- Consider Indian contract law context when relevant\n"
            "- Return response as valid JSON array with 3 objects\n\n"
        )
        
        # Add clause context
        prompt += f"ORIGINAL CLAUSE:\n{clause_text}\n\n"
        
        if clause_category:
            prompt += f"CLAUSE CATEGORY: {clause_category}\n"
        
        prompt += f"RISK LEVEL: {risk_level}\n"
        
        # Add risk assessment details
        if risk_assessment:
            prompt += f"\nRISK FACTORS:\n"
            for factor in risk_assessment.risk_factors:
                prompt += f"- {factor}\n"
            
            if risk_assessment.detected_keywords:
                prompt += f"\nKEY RISK INDICATORS: {', '.join(risk_assessment.detected_keywords)}\n"
        
        # Add document context
        if document_context:
            prompt += f"\nDOCUMENT CONTEXT:\n"
            if "document_type" in document_context:
                prompt += f"- Document Type: {document_context['document_type']}\n"
            if "party_role" in document_context:
                prompt += f"- Your Role: {document_context['party_role']}\n"
        
        # Add user preferences
        if user_preferences:
            prompt += f"\nUSER PREFERENCES:\n"
            if "risk_tolerance" in user_preferences:
                prompt += f"- Risk Tolerance: {user_preferences['risk_tolerance']}\n"
            if "negotiation_style" in user_preferences:
                prompt += f"- Negotiation Style: {user_preferences['negotiation_style']}\n"
        
        # Add JSON schema
        prompt += (
            "\n\nRESPONSE FORMAT (valid JSON array only):\n"
            "[\n"
            "  {\n"
            '    "alternative_text": "Complete rewritten clause...",\n'
            '    "strategic_benefit": "This version...",\n'
            '    "risk_reduction": "Reduces risk by...",\n'
            '    "implementation_notes": "When proposing this...",\n'
            '    "confidence": 0.85,\n'
            '    "alternative_type": "balanced"\n'
            "  },\n"
            "  ... (2 more alternatives with types: protective, simplified)\n"
            "]\n\n"
            
            "Generate the 3 alternatives now as valid JSON:"
        )
        
        return prompt
    
    async def _call_gemini_for_alternatives(self, prompt: str) -> str:
        """Call Gemini API to generate alternatives."""
        try:
            system_prompt = "You are an expert legal negotiation advisor. Generate strategic clause alternatives in valid JSON format."
            response = await self.gemini_client._generate_content(
                system_prompt=system_prompt,
                user_prompt=prompt
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}", exc_info=True)
            raise
    
    def _parse_alternatives_response(self, response: str) -> List[NegotiationAlternative]:
        """Parse and validate the alternatives response from Gemini."""
        try:
            # Extract JSON from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON array found in response")
            
            json_text = response[json_start:json_end]
            parsed_alternatives = json.loads(json_text)
            
            if not isinstance(parsed_alternatives, list):
                raise ValueError("Response is not a JSON array")
            
            if len(parsed_alternatives) < 3:
                logger.warning(f"Expected 3 alternatives, got {len(parsed_alternatives)}")
            
            # Convert to NegotiationAlternative objects
            alternatives = []
            expected_types = [AlternativeType.BALANCED, AlternativeType.PROTECTIVE, AlternativeType.SIMPLIFIED]
            
            for i, alt_data in enumerate(parsed_alternatives[:3]):  # Take first 3
                # Parse alternative type
                alt_type_str = alt_data.get("alternative_type", "").lower()
                if alt_type_str == "balanced":
                    alt_type = AlternativeType.BALANCED
                elif alt_type_str == "protective":
                    alt_type = AlternativeType.PROTECTIVE
                elif alt_type_str == "simplified":
                    alt_type = AlternativeType.SIMPLIFIED
                else:
                    alt_type = expected_types[i] if i < len(expected_types) else AlternativeType.BALANCED
                
                alternative = NegotiationAlternative(
                    alternative_id=str(uuid.uuid4()),
                    alternative_text=alt_data.get("alternative_text", ""),
                    strategic_benefit=alt_data.get("strategic_benefit", ""),
                    risk_reduction=alt_data.get("risk_reduction", ""),
                    implementation_notes=alt_data.get("implementation_notes", ""),
                    confidence=float(alt_data.get("confidence", 0.7)),
                    alternative_type=alt_type
                )
                
                # Validate required fields
                if not alternative.alternative_text:
                    logger.warning(f"Alternative {i} missing alternative_text")
                    continue
                
                alternatives.append(alternative)
            
            if not alternatives:
                raise ValueError("No valid alternatives parsed from response")
            
            return alternatives
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse alternatives response: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            
            # Return fallback alternatives
            return self._create_fallback_alternatives()
    
    def _create_fallback_alternatives(self) -> List[NegotiationAlternative]:
        """Create fallback alternatives when parsing fails."""
        return [
            NegotiationAlternative(
                alternative_id=str(uuid.uuid4()),
                alternative_text="[Alternative generation failed - please try again]",
                strategic_benefit="Unable to generate strategic alternative at this time",
                risk_reduction="N/A",
                implementation_notes="Please regenerate alternatives or consult a legal professional",
                confidence=0.0,
                alternative_type=AlternativeType.BALANCED
            )
        ]
    
    def _get_cached_response(self, clause_text: str) -> Optional[NegotiationResponse]:
        """Retrieve cached response if available and not expired."""
        cache_key = self._generate_cache_key(clause_text)
        
        if cache_key in self._cache:
            cached_response, cached_time = self._cache[cache_key]
            
            # Check if cache is expired
            elapsed = (datetime.utcnow().timestamp() - cached_time)
            if elapsed < self.cache_ttl:
                logger.debug(f"Cache hit for clause (age: {elapsed:.1f}s)")
                return cached_response
            else:
                # Remove expired cache entry
                del self._cache[cache_key]
                logger.debug("Cache expired, regenerating alternatives")
        
        return None
    
    def _cache_response(self, clause_text: str, response: NegotiationResponse) -> None:
        """Cache a negotiation response."""
        cache_key = self._generate_cache_key(clause_text)
        self._cache[cache_key] = (response, datetime.utcnow().timestamp())
        
        # Basic cache size management (keep last 100 entries)
        if len(self._cache) > 100:
            # Remove oldest entries
            sorted_cache = sorted(self._cache.items(), key=lambda x: x[1][1])
            self._cache = dict(sorted_cache[-100:])
            logger.debug("Cache pruned to 100 entries")
    
    def _generate_cache_key(self, clause_text: str) -> str:
        """Generate a cache key for a clause."""
        # Simple hash of first 200 chars (enough to identify unique clauses)
        return str(hash(clause_text[:200]))
    
    def clear_cache(self) -> None:
        """Clear the negotiation alternatives cache."""
        self._cache.clear()
        logger.info("Negotiation alternatives cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "cache_enabled": self.enable_caching,
            "cache_ttl": self.cache_ttl
        }
