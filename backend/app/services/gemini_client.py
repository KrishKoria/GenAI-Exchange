"""
Gemini AI client for batch summarization and Q&A
"""
import logging
import json
import asyncio
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from google import genai
from google.genai import types
from google.api_core.exceptions import GoogleAPIError
from app.core.config import get_settings
from app.core.logging import get_logger, LogContext, log_execution_time
from app.services.clause_segmenter import ClauseCandidate

logger = get_logger(__name__)

class GeminiError(Exception):
    """Custom exception for Gemini API errors."""
    pass

class TokenEstimator:
    """Utility class for estimating token counts."""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Rough token estimation (1 token ≈ 4 characters for English).
        """
        return max(1, len(text) // 4)
    
    @staticmethod
    def can_fit_in_context(
        texts: List[str], 
        max_tokens: int, 
        buffer_ratio: float = 0.8
    ) -> bool:
        """
        Check if texts can fit in the context window.
        """
        total_tokens = sum(TokenEstimator.estimate_tokens(text) for text in texts)
        return total_tokens <= (max_tokens * buffer_ratio)

class GeminiClient:
    """Service for interacting with Gemini models via Google GenAI."""
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[genai.Client] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Google GenAI client."""
        if self._initialized:
            return
        
        try:
            # Initialize Google GenAI client for Vertex AI
            self._client = genai.Client(
                vertexai=True,
                project=self.settings.PROJECT_ID,
                location=self.settings.VERTEX_AI_LOCATION
            )
            
            self._initialized = True
            logger.info(f"Google GenAI client initialized for model: {self.settings.GEMINI_MODEL_NAME}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google GenAI client: {e}")
            raise GeminiError(f"GenAI client initialization failed: {e}")

    async def batch_summarize_clauses(
        self, 
        clauses: List[ClauseCandidate],
        include_negotiation_tips: bool = True
    ) -> List[Dict[str, Any]]:
        """Batch summarize clauses using Gemini with structured JSON output and parallel processing."""
        await self.initialize()
        start_time = asyncio.get_event_loop().time()
        
        with LogContext(logger, clause_count=len(clauses)):
            logger.info("Starting batch clause summarization")
            batches = self._create_batches(clauses, self.settings.MAX_CLAUSES_PER_BATCH)
            
            # Create tasks for all batches to process them in parallel
            batch_tasks = []
            for i, batch in enumerate(batches):
                logger.info(f"Queuing batch {i+1}/{len(batches)} with {len(batch)} clauses")
                task = asyncio.create_task(
                    self._process_batch_with_retry(batch, include_negotiation_tips, i+1)
                )
                batch_tasks.append(task)
            
            logger.info(f"Processing {len(batch_tasks)} batches concurrently...")
            all_results = []
            
            # Process batches as they complete
            for task in asyncio.as_completed(batch_tasks):
                try:
                    batch_results = await task
                    all_results.extend(batch_results)
                except Exception as e:
                    logger.error(f"Batch task failed: {e}")
                    # Task should have already handled fallback, but add safety check
                    continue
            
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            log_execution_time(logger, "batch_summarization", processing_time)
            logger.info(f"Batch summarization complete: {len(all_results)} results")
            return all_results
    
    async def _process_batch(
        self, 
        clauses: List[ClauseCandidate], 
        include_negotiation_tips: bool
    ) -> List[Dict[str, Any]]:
        """Process a single batch of clauses."""
        
        system_prompt = self._build_system_prompt(include_negotiation_tips)
        user_prompt = self._build_batch_prompt(clauses)
        
        total_tokens = (
            TokenEstimator.estimate_tokens(system_prompt) +
            TokenEstimator.estimate_tokens(user_prompt)
        )
        
        logger.info(f"Estimated prompt tokens: {total_tokens}")
        
        if total_tokens > self.settings.MAX_PROMPT_TOKENS:
            logger.warning(f"Prompt exceeds token limit, splitting batch")
            mid = len(clauses) // 2
            batch1 = await self._process_batch(clauses[:mid], include_negotiation_tips)
            batch2 = await self._process_batch(clauses[mid:], include_negotiation_tips)
            return batch1 + batch2
        
        try:
            response = await self._generate_content(system_prompt, user_prompt)
            results = self._parse_batch_response(response, clauses)
            return results
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise GeminiError(f"Failed to process batch: {e}")
    
    async def _process_batch_with_retry(
        self, 
        batch: List[ClauseCandidate], 
        include_negotiation_tips: bool,
        batch_num: int
    ) -> List[Dict[str, Any]]:
        """Process a batch with error handling and fallback results."""
        try:
            logger.info(f"Processing batch {batch_num} with {len(batch)} clauses")
            return await self._process_batch(batch, include_negotiation_tips)
        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            fallback_results = self._create_fallback_results(batch)
            return fallback_results
    
    async def _generate_content(self, system_prompt: str, user_prompt: str) -> str:
        """Generate content using Google GenAI client."""
        if not self._client:
            raise GeminiError("Client not initialized")
        
        try:
            # Define safety settings
            safety_settings = [
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                ),
            ]
            
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = await self._client.aio.models.generate_content(
                model=self.settings.GEMINI_MODEL_NAME,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=self.settings.MAX_OUTPUT_TOKENS,
                    temperature=0.3,  # Slightly higher for more engaging, conversational responses
                    top_p=0.9,       # Increased for more diverse language choices
                    top_k=50,        # Increased for more varied vocabulary
                    safety_settings=safety_settings
                )
            )
            if not response.text:
                raise GeminiError("Empty response from Gemini")
            return response.text
        except GoogleAPIError as e:
            logger.error(f"Gemini API error: {e}")
            raise GeminiError(f"Gemini API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in content generation: {e}")
            raise GeminiError(f"Content generation failed: {e}")
    
    def _build_system_prompt(self, include_negotiation_tips: bool) -> str:
        """Build the system prompt for clause summarization."""
        base_prompt = (
            "You are a trusted legal advisor and translator, passionate about empowering everyday people to understand their legal documents. "
            "You're like having a friendly lawyer who speaks in plain English and genuinely cares about protecting people from legal surprises.\n\n"
            
            "YOUR MISSION: Transform confusing legal jargon into crystal-clear explanations that anyone can understand.\n\n"
            
            "FOR EACH CLAUSE, you must:"
            "\n1. TRANSLATE: Break down complex legal language into simple, everyday terms (8th grade level)"
            "\n2. CATEGORIZE: Classify the clause type accurately"
            "\n3. ASSESS RISK: Identify potential dangers or benefits for the reader"
            "\n4. OUTPUT: Provide structured JSON responses"
            
            "\n\nYOUR ADVISOR PERSONALITY:"
            "\n• Be PROACTIVE - point out important implications they might miss"
            "\n• Be PROTECTIVE - warn about potential risks with enthusiasm"
            "\n• Be EMPOWERING - help them understand their rights and obligations"
            "\n• Be CLEAR - use analogies and examples when helpful"
            "\n• Think like you're advising your best friend about their contract"
            
            "\n\nLEGAL JARGON TRANSLATION RULES:"
            "\n• Replace 'herein' with 'in this document'"
            "\n• Replace 'whereas' with 'since' or 'because'"
            "\n• Replace 'shall' with 'will' or 'must'"
            "\n• Replace 'party' with 'you' or 'the company' as appropriate"
            "\n• Replace 'notwithstanding' with 'despite' or 'even though'"
            "\n• Turn passive voice into active voice"
            "\n• Break down run-on sentences into digestible pieces"
            
            "\n\nQUALITY STANDARDS:"
            "\n• Focus on practical impact: 'What does this mean for ME?'"
            "\n• Use conversational tone while staying accurate"
            "\n• Always provide valid JSON that can be parsed programmatically"
            "\n• Never add facts not in the original text"
        )
        if include_negotiation_tips:
            base_prompt += (
                "\n\n5. NEGOTIATION GUIDANCE: Provide enthusiastic, actionable tips for improving terms"
                "\n• Be encouraging - 'You CAN negotiate this!'"
                "\n• Be specific - suggest exact language changes when possible"
                "\n• Be strategic - explain WHY a change matters"
                "\n• Think like you're coaching them for success"
            )
        return base_prompt
    
    def _build_batch_prompt(self, clauses: List[ClauseCandidate]) -> str:
        """Build the user prompt for a batch of clauses."""
        clauses_text = "CLAUSES:\n"
        for i, clause in enumerate(clauses):
            clauses_text += f"===\n"
            clauses_text += f'{{"id": "clause_{i}", "text": "{self._escape_json_string(clause.text[:2000])}"}} \n'
            clauses_text += "===\n"
        output_format = {
            "id": "clause_0",
            "summary": "ADVISOR-STYLE TRANSLATION: Explain what this really means in everyday language, with enthusiasm for protecting the reader",
            "clause_category": "One of: Termination, Liability, Indemnity, Confidentiality, Payment, IP Ownership, Dispute Resolution, Governing Law, Assignment, Modification, Other",
            "risk_level": "One of: low, moderate, attention",
            "negotiation_tip": "EMPOWERING tip: Specific, actionable advice for improving this clause (or null if not applicable)"
        }
        prompt = (
            f"{clauses_text}\n\nYOUR MISSION: Transform each clause into friendly, protective advice!\n\n"
            f"Return a JSON array with one object per clause using this exact format:\n"
            f"{json.dumps([output_format], indent=2)}"
            "\n\nQUALITY CHECKLIST:"
            "\n- All strings are properly escaped for JSON"
            "\n- Each clause gets exactly one result object"  
            "\n- SUMMARY: Write like you're explaining to a friend what this clause REALLY means"
            "\n- RISK LEVELS: 'low' = no worries, 'moderate' = worth understanding, 'attention' = RED FLAG!"
            "\n- NEGOTIATION TIPS: Be specific and encouraging - give them actual words to use!"
            "\n- Use active voice and conversational tone throughout"
            "\n- Focus on practical impact: 'Here's what this means for YOU...'"
            "\n- Must be valid, parseable JSON only"
        )
        return prompt
    
    def _escape_json_string(self, text: str) -> str:
        """Escape string for JSON inclusion."""
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        text = text.replace("\n", "\\n")
        text = text.replace("\r", "\\r")
        text = text.replace("\t", "\\t")
        return text
    
    def _parse_batch_response(
        self, 
        response: str, 
        original_clauses: List[ClauseCandidate]
    ) -> List[Dict[str, Any]]:
        """Parse and validate the batch response JSON."""
        
        try:
            # Try to extract JSON from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON array found in response")
            
            json_text = response[json_start:json_end]
            parsed_results = json.loads(json_text)
            
            if not isinstance(parsed_results, list):
                raise ValueError("Response is not a JSON array")
            
            # Validate and enrich results
            validated_results = []
            for i, result in enumerate(parsed_results):
                if i < len(original_clauses):
                    validated_result = self._validate_result(result, original_clauses[i], i)
                    validated_results.append(validated_result)
            
            # Fill in missing results with fallbacks
            while len(validated_results) < len(original_clauses):
                i = len(validated_results)
                fallback_result = self._create_fallback_result(original_clauses[i], i)
                validated_results.append(fallback_result)
            
            return validated_results
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse batch response: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            
            # Return fallback results
            return self._create_fallback_results(original_clauses)
    
    def _validate_result(
        self, 
        result: Dict[str, Any], 
        original_clause: ClauseCandidate, 
        index: int
    ) -> Dict[str, Any]:
        """Validate and enrich a single result."""
        
        # Required fields with defaults
        validated = {
            "clause_id": f"clause_{index}",
            "original_text": original_clause.text,
            "summary": self._enhance_advisor_language(result.get("summary", "Summary not available")),
            "category": result.get("clause_category", "Other"),
            "risk_level": result.get("risk_level", "moderate"),
            "negotiation_tip": self._enhance_advisor_language(result.get("negotiation_tip", "")) if result.get("negotiation_tip") else None,
            "confidence": 0.8,  # Default confidence for Gemini results
            "processing_method": "gemini",
            "processed_at": datetime.utcnow().isoformat()
        }
        
        # Validate risk level
        valid_risk_levels = ["low", "moderate", "attention"]
        if validated["risk_level"] not in valid_risk_levels:
            validated["risk_level"] = "moderate"
        
        # Validate category
        valid_categories = [
            "Termination", "Liability", "Indemnity", "Confidentiality",
            "Payment", "IP Ownership", "Dispute Resolution", "Governing Law",
            "Assignment", "Modification", "Other"
        ]
        if validated["category"] not in valid_categories:
            validated["category"] = "Other"
        
        return validated
    
    def _create_fallback_results(self, clauses: List[ClauseCandidate]) -> List[Dict[str, Any]]:
        """Create fallback results for failed batch processing."""
        return [self._create_fallback_result(clause, i) for i, clause in enumerate(clauses)]
    
    def _create_fallback_result(self, clause: ClauseCandidate, index: int) -> Dict[str, Any]:
        """Create a fallback result for a single clause."""
        return {
            "clause_id": f"clause_{index}",
            "original_text": clause.text,
            "summary": "This clause requires manual review. Automatic summarization failed.",
            "category": getattr(clause, 'category', 'Other'),
            "risk_level": "moderate",
            "negotiation_tip": None,
            "confidence": 0.3,
            "processing_method": "fallback",
            "processed_at": datetime.utcnow().isoformat(),
            "needs_review": True
        }
    
    def _create_batches(
        self, 
        clauses: List[ClauseCandidate], 
        max_batch_size: int
    ) -> List[List[ClauseCandidate]]:
        """Split clauses into batches for processing."""
        batches = []
        
        current_batch = []
        current_tokens = 0
        
        for clause in clauses:
            clause_tokens = TokenEstimator.estimate_tokens(clause.text)
            
            # Check if adding this clause would exceed limits
            if (len(current_batch) >= max_batch_size or 
                current_tokens + clause_tokens > self.settings.MAX_PROMPT_TOKENS * 0.7):
                
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
            
            current_batch.append(clause)
            current_tokens += clause_tokens
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    async def answer_question(
        self, 
        question: str, 
        relevant_clauses: List[Dict[str, Any]],
        doc_id: str
    ) -> Dict[str, Any]:
        """
        Answer a question using relevant clauses with grounded prompting.
        
        Args:
            question: User question
            relevant_clauses: List of relevant clause data
            doc_id: Document ID for context
            
        Returns:
            Structured answer with citations
        """
        await self.initialize()
        
        with LogContext(logger, doc_id=doc_id, clause_count=len(relevant_clauses)):
            logger.info(f"Processing Q&A request: {question[:100]}...")
            
            try:
                # Build Q&A prompt
                system_prompt = self._build_qa_system_prompt()
                user_prompt = self._build_qa_user_prompt(question, relevant_clauses)
                
                # Generate response
                response = await self._generate_content(system_prompt, user_prompt)
                
                # Parse and validate Q&A response
                result = self._parse_qa_response(response, relevant_clauses)
                
                return result
                
            except Exception as e:
                logger.error(f"Q&A processing failed: {e}")
                return {
                    "answer": "I'm sorry, I couldn't process your question at this time. Please try rephrasing or contact support.",
                    "used_clause_ids": [],
                    "confidence": 0.0,
                    "sources": [],
                    "error": str(e)
                }
    
    def _build_qa_system_prompt(self) -> str:
        """Build system prompt for Q&A."""
        return """You are an enthusiastic legal advisor who genuinely cares about helping people understand their contracts! 
Think of yourself as a trusted friend with legal expertise who wants to protect and empower the person asking questions.

YOUR MISSION: Provide helpful, proactive advice that goes beyond just answering the question.

ADVISORY APPROACH:
• Be PROACTIVE - if you see related risks or opportunities in the clauses, mention them!
• Be PROTECTIVE - warn about potential issues they should be aware of
• Be EMPOWERING - help them understand their rights and what they can do
• Use conversational, friendly language while staying accurate
• Think "What would I want my best friend to know about this?"

ANSWER GUIDELINES:
• Base answers ONLY on the provided clauses - never hallucinate
• If something isn't clearly specified, say "This document doesn't clearly address that, but here's what the related clauses suggest..."
• Reference clauses in user-friendly format: "Clause 3 (Payment Terms)" instead of technical IDs
• Use everyday language that anyone can understand
• Be enthusiastic about helping them understand their rights

CLAUSE REFERENCING RULES:
• Always use "Clause X (Category)" format when citing clauses
• Examples: "Clause 1 (Terms)", "Clause 5 (Termination)", "Clause 8 (Payment)"
• Never use technical clause IDs like "doc123_clause_5" - these confuse users
• Make your references natural: "as stated in Clause 3 (Privacy)" 

PROACTIVE BONUS POINTS:
• Point out related clauses they should also pay attention to
• Mention if there are any red flags in nearby clauses
• Suggest what questions they might want to ask the other party
• Explain the practical implications of what you found

Always output in strict JSON format only."""
    
    def _build_qa_user_prompt(
        self, 
        question: str, 
        relevant_clauses: List[Dict[str, Any]]
    ) -> str:
        """Build user prompt for Q&A."""
        
        clauses_text = "CLAUSES:\n"
        for i, clause in enumerate(relevant_clauses):
            clause_order = clause.get('order', i + 1)
            clause_category = clause.get('category', 'Unknown')
            clauses_text += f"Clause {clause_order} ({clause_category}):\n"
            clauses_text += f"Summary: {clause.get('summary', '')}\n"
            clauses_text += f"Original: {clause.get('original_text', '')[:500]}...\n\n"
        
        output_format = {
            "answer": "ADVISOR-STYLE RESPONSE: Your enthusiastic, helpful answer based on the clauses, with proactive insights",
            "used_clause_numbers": [1, 2],
            "confidence": 0.85,
            "additional_insights": "Optional: Proactive warnings, related clause suggestions, or empowering tips"
        }
        
        return f"""{clauses_text}

QUESTION: {question}

YOUR ADVISOR MISSION: Answer their question AND provide helpful insights they might not have thought to ask about!

Return response in this exact JSON format:
{json.dumps(output_format, indent=2)}

RESPONSE GUIDELINES:
• ANSWER: Be conversational and helpful - explain what the clauses say in everyday terms
• CONFIDENCE: 0-1 based on how clearly the clauses answer the question
• ADDITIONAL_INSIGHTS: Be proactive! Mention related risks, opportunities, or things they should know
• Use enthusiastic, protective language that empowers them
• Reference clauses as "Clause X (Category Name)" where X is the clause number - this is much more user-friendly than technical IDs
• When citing clauses, use natural language like "as mentioned in Clause 3 (Termination)" instead of technical identifiers"""
    
    def _parse_qa_response(
        self, 
        response: str, 
        relevant_clauses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parse Q&A response JSON."""
        
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in response")
            
            json_text = response[json_start:json_end]
            result = json.loads(json_text)
            
            # Handle both old and new format for backward compatibility
            used_clause_numbers = result.get("used_clause_numbers", [])
            used_clause_ids = result.get("used_clause_ids", [])
            
            sources = []
            
            # If we have clause numbers, match them to the relevant clauses
            if used_clause_numbers:
                for clause_num in used_clause_numbers:
                    for clause in relevant_clauses:
                        clause_order = clause.get("order", 0)
                        if clause_order == clause_num:
                            sources.append({
                                "clause_id": clause.get("clause_id", f"clause_{clause_num}"),
                                "clause_number": clause_num,
                                "category": clause.get("category", "Unknown"),
                                "snippet": clause.get("summary", "")[:200] + "...",
                                "relevance_score": 0.8
                            })
                            break
            else:
                # Fallback to clause IDs for backward compatibility
                for clause_id in used_clause_ids:
                    for clause in relevant_clauses:
                        if clause.get("clause_id") == clause_id:
                            sources.append({
                                "clause_id": clause_id,
                                "clause_number": clause.get("order", 0),
                                "category": clause.get("category", "Unknown"),
                                "snippet": clause.get("summary", "")[:200] + "...",
                                "relevance_score": 0.8
                            })
                            break
            
            # Enhance response with advisor language
            result["answer"] = self._enhance_advisor_language(result.get("answer", ""))
            if result.get("additional_insights"):
                result["additional_insights"] = self._enhance_advisor_language(result["additional_insights"])
            
            # Ensure we return both formats for compatibility
            result["used_clause_ids"] = [source["clause_id"] for source in sources]
            result["used_clause_numbers"] = [source["clause_number"] for source in sources]
            result["sources"] = sources
            result["timestamp"] = datetime.utcnow().isoformat()
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Q&A response: {e}")
            
            # Return fallback response
            return {
                "answer": "I apologize, but I'm having trouble processing your question right now.",
                "used_clause_ids": [],
                "used_clause_numbers": [],
                "confidence": 0.0,
                "sources": [],
                "error": "Response parsing failed"
            }
    
    def _enhance_advisor_language(self, text: str) -> str:
        """Post-process text to enhance advisor-like language and enthusiasm."""
        if not text:
            return text
            
        # Legal jargon translations
        jargon_translations = {
            "this clause": "this clause (here's what this really means)",
            "the contract": "your contract",
            "the agreement": "your agreement", 
            "you should": "I recommend you",
            "it is important": "this is really important",
            "may result in": "could lead to",
            "pursuant to": "according to",
            "in the event that": "if",
            "notwithstanding": "despite",
            "hereinafter": "from now on in this document",
            "whereas": "since",
            "therefor": "because of this",
            "aforementioned": "mentioned earlier",
            "subsequent": "later",
            "prior": "earlier",
            "terminate": "end",
            "commence": "start",
            "obligations": "responsibilities",
            "liabilities": "potential costs or responsibilities",
            "indemnify": "protect and cover costs for",
            "liquidated damages": "penalty fees",
            "force majeure": "uncontrollable events (like natural disasters)",
            "intellectual property": "ideas, designs, and creative work",
            "proprietary": "owned exclusively by",
            "confidential": "private and secret",
            "jurisdiction": "which court system handles disputes"
        }
        
        # Advisor enhancements - make language more protective and empowering
        advisor_enhancements = {
            "this means": "Here's what this really means for you:",
            "important": "IMPORTANT",
            "risk": "potential risk",
            "attention": "PAY ATTENTION",
            "unlimited": "UNLIMITED (this is a big red flag!)",
            "automatically": "automatically (heads up!)",
            "perpetual": "forever (that's a long time!)",
            "irrevocable": "can't be changed later",
            "waive": "give up your right to",
            "hold harmless": "protect them from any costs",
            "sole discretion": "they decide everything",
            "reasonable": "fair and appropriate"
        }
        
        enhanced_text = text
        
        # Apply jargon translations first
        for legal_term, plain_language in jargon_translations.items():
            enhanced_text = enhanced_text.replace(legal_term, plain_language)
        
        # Apply advisor enhancements
        for term, enhanced_term in advisor_enhancements.items():
            enhanced_text = enhanced_text.replace(term, enhanced_term)
        
        # Add encouraging phrases for negotiation tips
        if "negotiate" in enhanced_text.lower() or "ask for" in enhanced_text.lower():
            if not enhanced_text.startswith("TIP:"):
                enhanced_text = f"TIP: {enhanced_text}"
        
        return enhanced_text