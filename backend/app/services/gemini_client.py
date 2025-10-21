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
from app.models.document import SupportedLanguage

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
        include_negotiation_tips: bool = True,
        language: SupportedLanguage = SupportedLanguage.ENGLISH
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
                    response_mime_type="application/json",  # Force JSON output with proper escaping
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
            "You are a trusted legal advisor focused on helping people understand their legal documents clearly and confidently. "
            "Your role is to translate complex legal language into accessible explanations while maintaining accuracy.\n\n"
            
            "YOUR MISSION: Transform complex legal language into clear, understandable explanations.\n\n"
            
            "FOR EACH CLAUSE, you must:"
            "\n1. TRANSLATE: Break down complex legal language into simple, everyday terms (8th grade level)"
            "\n2. CATEGORIZE: Classify the clause type accurately"
            "\n3. ASSESS RISK: Identify potential implications and considerations for the reader"
            "\n4. OUTPUT: Provide structured JSON responses"
            
            "\n\nYOUR COMMUNICATION STYLE:"
            "\n• Be INFORMATIVE - explain important implications clearly"
            "\n• Be THOROUGH - highlight potential risks and benefits"
            "\n• Be EMPOWERING - help them understand their rights and obligations"
            "\n• Be CLEAR - use simple language and examples when helpful"
            "\n• Maintain professional objectivity while being accessible"
            
            "\n\nLEGAL JARGON TRANSLATION RULES:"
            "\n• Replace 'herein' with 'in this document'"
            "\n• Replace 'whereas' with 'since' or 'because'"
            "\n• Replace 'shall' with 'will' or 'must'"
            "\n• Replace 'party' with 'you' or 'the company' as appropriate"
            "\n• Replace 'notwithstanding' with 'despite' or 'even though'"
            "\n• Turn passive voice into active voice"
            "\n• Break down run-on sentences into digestible pieces"
            
            "\n\nQUALITY STANDARDS:"
            "\n• Focus on practical impact and implications"
            "\n• Use clear, professional tone while staying accessible"
            "\n• Always provide valid JSON that can be parsed programmatically"
            "\n• Never add facts not in the original text"
        )
        if include_negotiation_tips:
            base_prompt += (
                "\n\n5. NEGOTIATION GUIDANCE: Provide practical, actionable recommendations for improving terms"
                "\n• Be constructive - suggest specific improvements where appropriate"
                "\n• Be specific - recommend exact language changes when possible"
                "\n• Be strategic - explain the reasoning behind suggested changes"
                "\n• Focus on practical steps they can take"
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
            "summary": "Clear explanation of what this clause means in everyday language, focusing on practical implications",
            "clause_category": "One of: Termination, Liability, Indemnity, Confidentiality, Payment, IP Ownership, Dispute Resolution, Governing Law, Assignment, Modification, Warranties, Force Majeure, Definitions, Other",
            "risk_level": "One of: low, moderate, attention",
            "negotiation_tip": "Specific, actionable advice for improving this clause (or null if not applicable)"
        }
        prompt = (
            f"{clauses_text}\n\nYOUR OBJECTIVE: Transform each clause into clear, understandable guidance.\n\n"
            f"Return a JSON array with one object per clause using this exact format:\n"
            f"{json.dumps([output_format], indent=2)}"
            "\n\nCATEGORY CLASSIFICATION GUIDELINES:"
            "\n- Termination: Contract ending, breach, cancellation, expiration, notice requirements"
            "\n- Liability: Damages, responsibility for losses, harm, limitation of liability"
            "\n- Indemnity: Hold harmless, defend against claims, reimbursement, third-party protection"
            "\n- Confidentiality: Non-disclosure, proprietary information, trade secrets, privacy"
            "\n- Payment: Fees, costs, billing terms, invoice requirements, late payments"
            "\n- IP Ownership: Intellectual property rights, copyrights, trademarks, work product ownership"
            "\n- Dispute Resolution: Arbitration, mediation, court procedures, litigation, ADR"
            "\n- Governing Law: Applicable jurisdiction, choice of law, venue, legal framework"
            "\n- Assignment: Transfer of rights/obligations, delegation, subcontracting restrictions"
            "\n- Modification: Contract amendments, changes, written consent requirements, waivers"
            "\n- Warranties: Guarantees, representations, disclaimers, 'as-is' statements"
            "\n- Force Majeure: Acts of God, uncontrollable events, performance excuses"
            "\n- Definitions: Term definitions, meanings, interpretations, capitalized terms"
            "\n- Other: Use only when clause doesn't clearly fit above categories"
            "\n\nCATEGORIZATION EXAMPLES:"
            "\n• 'This Agreement shall terminate immediately upon material breach' → Termination"
            "\n• 'Party A shall indemnify Party B against third-party claims' → Indemnity"
            "\n• 'All Confidential Information must remain private' → Confidentiality"
            "\n• 'Payment is due within 30 days of invoice' → Payment"
            "\n• 'All work product shall be owned by Company' → IP Ownership"
            "\n• 'Any disputes shall be resolved by arbitration' → Dispute Resolution"
            "\n• 'This Agreement is governed by California law' → Governing Law"
            "\n• 'No assignment without prior written consent' → Assignment"
            "\n• 'This Agreement may only be modified in writing' → Modification"
            "\n• 'Company warrants the software will perform as described' → Warranties"
            "\n• 'Performance excused due to acts of God' → Force Majeure"
            "\n• 'Confidential Information means non-public data' → Definitions"
            "\n\nQUALITY STANDARDS:"
            "\n- All strings are properly escaped for JSON"
            "\n- Each clause gets exactly one result object"
            "\n- SUMMARY: Explain the clause clearly and objectively"
            "\n- CATEGORY: Choose most specific category that fits the clause's primary purpose"
            "\n- RISK LEVELS: 'low' = minimal concern, 'moderate' = worth understanding, 'attention' = requires attention"
            "\n- NEGOTIATION TIPS: Provide specific, practical advice when applicable"
            "\n- Use clear, professional language throughout"
            "\n- Focus on practical implications and meaning"
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
            "Assignment", "Modification", "Warranties", "Force Majeure", "Definitions", "Other"
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
        doc_id: str,
        language: SupportedLanguage = SupportedLanguage.ENGLISH
    ) -> Dict[str, Any]:
        """
        Answer a question using relevant clauses with grounded prompting.

        Args:
            question: User question
            relevant_clauses: List of relevant clause data
            doc_id: Document ID for context
            language: Language for the response (default: English)

        Returns:
            Structured answer with citations
        """
        await self.initialize()
        
        with LogContext(logger, doc_id=doc_id, clause_count=len(relevant_clauses)):
            logger.info(f"Processing Q&A request: {question[:100]}...")
            
            try:
                # Build Q&A prompt
                system_prompt = self._build_qa_system_prompt(language)
                user_prompt = self._build_qa_user_prompt(question, relevant_clauses, language)
                
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
    
    def _build_qa_system_prompt(self, language: SupportedLanguage = SupportedLanguage.ENGLISH) -> str:
        """Build system prompt for Q&A with language support."""

        # Language-specific instructions
        language_instructions = {
            SupportedLanguage.ENGLISH: {
                "role": "You are a professional legal advisor focused on helping people understand their contracts clearly and thoroughly.",
                "language_note": "Respond in clear, professional English.",
                "example_ref": '"Clause 3 (Payment Terms)"',
                "not_specified": '"This document doesn\'t clearly address that aspect, but the related clauses indicate..."'
            },
            SupportedLanguage.HINDI: {
                "role": "आप एक पेशेवर कानूनी सलाहकार हैं जो लोगों को उनके अनुबंधों को स्पष्ट और संपूर्ण रूप से समझने में मदद करने पर केंद्रित हैं।",
                "language_note": "हिंदी में स्पष्ट, पेशेवर उत्तर दें। कानूनी शब्दावली के लिए अंग्रेजी शब्दों का उपयोग करें लेकिन स्पष्टीकरण हिंदी में दें।",
                "example_ref": '"खंड 3 (भुगतान की शर्तें / Payment Terms)"',
                "not_specified": '"यह दस्तावेज़ इस पहलू को स्पष्ट रूप से संबोधित नहीं करता, लेकिन संबंधित खंड इंगित करते हैं..."'
            },
            SupportedLanguage.BENGALI: {
                "role": "আপনি একজন পেশাদার আইনি পরামর্শদাতা যিনি মানুষকে তাদের চুক্তিগুলি স্পষ্ট এবং সম্পূর্ণভাবে বুঝতে সাহায্য করার উপর দৃষ্টি নিবদ্ধ করেন।",
                "language_note": "বাংলায় স্পষ্ট, পেশাদার উত্তর দিন। আইনি পরিভাষার জন্য ইংরেজি শব্দ ব্যবহার করুন কিন্তু ব্যাখ্যা বাংলায় দিন।",
                "example_ref": '"ধারা ৩ (পেমেন্টের শর্তাবলী / Payment Terms)"',
                "not_specified": '"এই নথিটি এই দিকটি স্পষ্টভাবে সম্বোধন করে না, তবে সংশ্লিষ্ট ধারাগুলি নির্দেশ করে..."'
            }
        }

        lang_config = language_instructions.get(language, language_instructions[SupportedLanguage.ENGLISH])

        return f"""{lang_config["role"]}

YOUR OBJECTIVE: Provide comprehensive, accurate guidance that addresses the user's question and highlights relevant considerations.

LANGUAGE REQUIREMENTS:
• {lang_config["language_note"]}
• Keep legal terms in English but provide explanations in the target language
• Use hybrid approach: English legal terminology + native language explanations

COMMUNICATION APPROACH:
• Be INFORMATIVE - provide clear, complete answers based on the available clauses
• Be THOROUGH - identify related considerations and implications
• Be HELPFUL - explain complex terms and concepts in accessible language
• Use professional, clear language while remaining accessible
• Focus on practical understanding and implications

ANSWER GUIDELINES:
• Base answers ONLY on the provided clauses - never add information not present
• If something isn't clearly specified, state {lang_config["not_specified"]}
• Reference clauses in user-friendly format: {lang_config["example_ref"]} instead of technical IDs
• Use clear, professional language that is easy to understand
• Focus on helping users understand their rights and obligations

CLAUSE REFERENCING RULES:
• Always use "Clause X (Category)" format when citing clauses
• Examples: "Clause 1 (Terms)", "Clause 5 (Termination)", "Clause 8 (Payment)"
• Never use technical clause IDs like "doc123_clause_5" - these are not user-friendly
• Make your references natural: "as outlined in Clause 3 (Privacy)"

COMPREHENSIVE GUIDANCE:
• Identify related clauses that may be relevant to the question
• Highlight important considerations or potential concerns
• Explain practical implications of the relevant terms
• Suggest areas where clarification might be beneficial

Always output in strict JSON format only."""
    
    def _build_qa_user_prompt(
        self,
        question: str,
        relevant_clauses: List[Dict[str, Any]],
        language: SupportedLanguage = SupportedLanguage.ENGLISH
    ) -> str:
        """Build user prompt for Q&A with language support."""

        clauses_text = "CLAUSES:\n"
        for i, clause in enumerate(relevant_clauses):
            clause_order = clause.get('order', i + 1)
            clause_category = clause.get('category', 'Unknown')
            clauses_text += f"Clause {clause_order} ({clause_category}):\n"
            clauses_text += f"Summary: {clause.get('summary', '')}\n"
            clauses_text += f"Original: {clause.get('original_text', '')[:500]}...\n\n"

        # Language-specific response format examples
        language_examples = {
            SupportedLanguage.ENGLISH: {
                "answer": "Professional, clear response based on the clauses, including relevant considerations and implications",
                "additional_insights": "Optional: Related considerations, important implications, or areas requiring attention"
            },
            SupportedLanguage.HINDI: {
                "answer": "खंडों के आधार पर पेशेवर, स्पष्ट उत्तर, संबंधित विचार और निहितार्थों सहित",
                "additional_insights": "वैकल्पिक: संबंधित विचार, महत्वपूर्ण निहितार्थ, या ध्यान देने की आवश्यकता वाले क्षेत्र"
            },
            SupportedLanguage.BENGALI: {
                "answer": "ধারাগুলির উপর ভিত্তি করে পেশাদার, স্পষ্ট প্রতিক্রিয়া, প্রাসঙ্গিক বিবেচনা এবং প্রভাব সহ",
                "additional_insights": "ঐচ্ছিক: সম্পর্কিত বিবেচনা, গুরুত্বপূর্ণ প্রভাব, বা মনোযোগের প্রয়োজনীয় এলাকা"
            }
        }

        lang_example = language_examples.get(language, language_examples[SupportedLanguage.ENGLISH])

        output_format = {
            "answer": lang_example["answer"],
            "used_clause_numbers": [1, 2],
            "confidence": 0.85,
            "additional_insights": lang_example["additional_insights"]
        }

        return f"""{clauses_text}

QUESTION: {question}

YOUR OBJECTIVE: Provide a comprehensive answer that addresses the question and highlights relevant considerations.

LANGUAGE: Respond in {language.value} ({'English' if language == SupportedLanguage.ENGLISH else 'हिंदी' if language == SupportedLanguage.HINDI else 'বাংলা'})

Return response in this exact JSON format:
{json.dumps(output_format, indent=2)}

RESPONSE GUIDELINES:
• ANSWER: Provide clear, professional guidance based on what the clauses state
• CONFIDENCE: 0-1 based on how clearly the clauses answer the question
• ADDITIONAL_INSIGHTS: Include relevant considerations, implications, or important related information
• Use clear, professional language that remains accessible
• Reference clauses as "Clause X (Category Name)" where X is the clause number
• When citing clauses, use natural language like "as outlined in Clause 3 (Termination)"
• IMPORTANT: Keep legal terms in English but provide explanations in the target language"""
    
    def _parse_qa_response(
        self, 
        response: str, 
        relevant_clauses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parse Q&A response JSON with robust error handling for control characters."""
        
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error(f"No JSON object found in response. Response text: {response[:500]}")
                raise ValueError("No JSON object found in response")
            
            json_text = response[json_start:json_end]
            
            # Try parsing with strict=False first (allows control characters)
            try:
                result = json.loads(json_text, strict=False)
            except json.JSONDecodeError as strict_error:
                # If strict=False fails, try cleaning the JSON text
                logger.warning(f"Initial JSON parse failed: {strict_error}. Attempting to clean JSON text.")
                
                # Replace common problematic control characters
                cleaned_json = json_text.replace('\r', '\\r').replace('\t', '\\t')
                
                # Try parsing again
                try:
                    result = json.loads(cleaned_json, strict=False)
                    logger.info("Successfully parsed JSON after cleaning control characters")
                except json.JSONDecodeError as clean_error:
                    # Log the problematic JSON for debugging
                    logger.error(f"JSON parsing failed even after cleaning: {clean_error}")
                    logger.error(f"Problematic JSON (first 1000 chars): {json_text[:1000]}")
                    raise
            
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
            logger.error(f"Response text (first 500 chars): {response[:500]}")
            
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
        """Post-process text to improve clarity and professional tone."""
        if not text:
            return text
            
        # Legal jargon translations for clarity
        jargon_translations = {
            "the contract": "your contract",
            "the agreement": "your agreement", 
            "you should": "it is recommended that you",
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
        
        # Professional clarifications - remove overly casual tone
        professional_clarifications = {
            "this means": "This means:",
            "important": "important",
            "risk": "potential risk",
            "attention": "requires attention",
            "unlimited": "unlimited",
            "automatically": "automatically",
            "perpetual": "perpetual",
            "irrevocable": "cannot be changed later",
            "waive": "give up your right to",
            "hold harmless": "protect them from any costs",
            "sole discretion": "their complete discretion",
            "reasonable": "reasonable"
        }
        
        enhanced_text = text
        
        # Apply jargon translations for clarity
        for legal_term, plain_language in jargon_translations.items():
            enhanced_text = enhanced_text.replace(legal_term, plain_language)
        
        # Apply professional clarifications
        for term, clarified_term in professional_clarifications.items():
            enhanced_text = enhanced_text.replace(term, clarified_term)
        
        # Add professional guidance prefix for negotiation tips
        if "negotiate" in enhanced_text.lower() or "ask for" in enhanced_text.lower():
            if not enhanced_text.startswith("Recommendation:"):
                enhanced_text = f"Recommendation: {enhanced_text}"
        
        return enhanced_text