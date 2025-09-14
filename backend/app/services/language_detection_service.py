"""
Advanced Language Detection Service for Automatic Language Recognition
Implements multi-tier detection using FastText + Gemini + Google Cloud Translation API
"""
import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.document import SupportedLanguage

logger = get_logger(__name__)


class DetectionMethod(str, Enum):
    """Detection method enumeration for tracking accuracy"""
    FASTTEXT = "fasttext"
    GEMINI_CONTEXT = "gemini_context"
    GOOGLE_API = "google_api"
    PATTERN_BASED = "pattern_based"
    SESSION_HINT = "session_hint"


@dataclass
class LanguageDetectionResult:
    """Result of language detection with metadata"""
    language: SupportedLanguage
    confidence: float
    method: DetectionMethod
    raw_detection: Optional[str] = None
    reasoning: Optional[str] = None


class LanguageDetectionService:
    """
    Advanced multi-tier language detection service optimized for 2025.

    Detection Priority:
    1. Session hint (if user has consistent pattern)
    2. Pattern-based detection (script detection for speed)
    3. FastText detection (primary - fast and accurate)
    4. Gemini contextual understanding (secondary - for ambiguous cases)
    5. Google Cloud API (fallback - highest accuracy)
    """

    def __init__(self):
        self.settings = get_settings()
        self._fasttext_model = None
        self._google_translate_client = None
        self._initialized = False

        # Language pattern recognition for quick detection
        self._language_patterns = {
            'hi': re.compile(r'[\u0900-\u097F]+'),  # Devanagari script
            'bn': re.compile(r'[\u0980-\u09FF]+'),  # Bengali script
            'ta': re.compile(r'[\u0B80-\u0BFF]+'),  # Tamil script
            'te': re.compile(r'[\u0C00-\u0C7F]+'),  # Telugu script
            'mr': re.compile(r'[\u0900-\u097F]+'),  # Marathi (Devanagari)
            'gu': re.compile(r'[\u0A80-\u0AFF]+'),  # Gujarati script
            'kn': re.compile(r'[\u0C80-\u0CFF]+'),  # Kannada script
            'ml': re.compile(r'[\u0D00-\u0D7F]+'),  # Malayalam script
            'pa': re.compile(r'[\u0A00-\u0A7F]+'),  # Gurmukhi script
            'ur': re.compile(r'[\u0600-\u06FF]+'),  # Arabic script for Urdu
        }

        # Language code mapping
        self._language_code_mapping = {
            'en': SupportedLanguage.ENGLISH,
            'hi': SupportedLanguage.HINDI,
            'bn': SupportedLanguage.BENGALI,
            'ta': SupportedLanguage.TAMIL,
            'te': SupportedLanguage.TELUGU,
            'mr': SupportedLanguage.MARATHI,
            'gu': SupportedLanguage.GUJARATI,
            'kn': SupportedLanguage.KANNADA,
            'ml': SupportedLanguage.MALAYALAM,
            'pa': SupportedLanguage.PUNJABI,
            'ur': SupportedLanguage.URDU,
        }

        # Session language tracking
        self._session_language_cache = {}  # session_id -> language preferences

    async def initialize(self):
        """Initialize detection services lazily"""
        if self._initialized:
            return

        try:
            logger.info("Initializing Language Detection Service...")

            # Note: FastText initialization would go here
            # For now, we'll use pattern-based + Gemini + Google API
            # await self._initialize_fasttext()

            # Initialize Google Translate client if credentials available
            await self._initialize_google_translate()

            self._initialized = True
            logger.info("Language Detection Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Language Detection Service: {e}")
            # Continue without FastText - use other methods
            self._initialized = True

    async def _initialize_google_translate(self):
        """Initialize Google Cloud Translation client"""
        try:
            from google.cloud import translate_v2 as translate
            self._google_translate_client = translate.Client()
            logger.info("Google Translate API client initialized")
        except Exception as e:
            logger.warning(f"Google Translate API not available: {e}")

    async def detect_language_advanced(
        self,
        text: str,
        session_id: Optional[str] = None,
        context: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> LanguageDetectionResult:
        """
        Advanced multi-tier language detection with intelligent fallbacks.

        Args:
            text: Text to analyze
            session_id: Session ID for tracking preferences
            context: Previous conversation context
            user_id: User ID for personalization

        Returns:
            LanguageDetectionResult with language, confidence, and method
        """
        await self.initialize()

        if not text or not text.strip():
            return LanguageDetectionResult(
                language=SupportedLanguage.ENGLISH,
                confidence=0.5,
                method=DetectionMethod.PATTERN_BASED,
                reasoning="Empty or whitespace text"
            )

        text_clean = text.strip()
        logger.info(f"Detecting language for text: '{text_clean[:50]}{'...' if len(text_clean) > 50 else ''}'")

        # Tier 1: Session hint (fastest)
        if session_id:
            session_hint = await self._get_session_language_hint(session_id)
            if session_hint:
                logger.info(f"Using session language hint: {session_hint.value}")
                return LanguageDetectionResult(
                    language=session_hint,
                    confidence=0.75,
                    method=DetectionMethod.SESSION_HINT,
                    reasoning="Based on session language pattern"
                )

        # Tier 2: Pattern-based script detection (very fast, high confidence for clear scripts)
        pattern_result = await self._detect_with_patterns(text_clean)
        if pattern_result.confidence > 0.85:
            logger.info(f"Pattern detection successful: {pattern_result.language.value} ({pattern_result.confidence:.2f})")
            await self._update_session_language(session_id, pattern_result.language)
            return pattern_result

        # Tier 3: FastText detection (would be primary in production)
        # fasttext_result = await self._detect_with_fasttext(text_clean)
        # if fasttext_result.confidence > 0.80:
        #     return fasttext_result

        # Tier 4: Gemini contextual understanding (for ambiguous cases)
        if context or len(text_clean) > 20:  # Use Gemini for longer text or with context
            try:
                gemini_result = await self._detect_with_gemini_context(text_clean, context)
                if gemini_result.confidence > 0.75:
                    logger.info(f"Gemini detection successful: {gemini_result.language.value} ({gemini_result.confidence:.2f})")
                    await self._update_session_language(session_id, gemini_result.language)
                    return gemini_result
            except Exception as e:
                logger.warning(f"Gemini detection failed: {e}")

        # Tier 5: Google Cloud Translation API (fallback)
        if self._google_translate_client:
            try:
                google_result = await self._detect_with_google_api(text_clean)
                if google_result.confidence > 0.70:
                    logger.info(f"Google API detection successful: {google_result.language.value} ({google_result.confidence:.2f})")
                    await self._update_session_language(session_id, google_result.language)
                    return google_result
            except Exception as e:
                logger.warning(f"Google API detection failed: {e}")

        # Final fallback: Use pattern result or default to English
        if pattern_result.confidence > 0.0:
            logger.info(f"Using pattern detection as fallback: {pattern_result.language.value}")
            return pattern_result

        logger.info("All detection methods failed, defaulting to English")
        return LanguageDetectionResult(
            language=SupportedLanguage.ENGLISH,
            confidence=0.5,
            method=DetectionMethod.PATTERN_BASED,
            reasoning="Fallback to English after all detection methods failed"
        )

    async def _detect_with_patterns(self, text: str) -> LanguageDetectionResult:
        """Fast pattern-based detection using Unicode script ranges"""
        script_scores = {}
        total_chars = len(text)

        # Count characters in each script
        for lang_code, pattern in self._language_patterns.items():
            matches = pattern.findall(text)
            if matches:
                script_chars = sum(len(match) for match in matches)
                script_scores[lang_code] = script_chars / total_chars

        # Check for English (Latin script + common English patterns)
        latin_pattern = re.compile(r'[a-zA-Z]+')
        latin_matches = latin_pattern.findall(text)
        if latin_matches:
            latin_chars = sum(len(match) for match in latin_matches)
            # Boost English if we see common English words
            english_indicators = ['the', 'and', 'is', 'are', 'this', 'that', 'what', 'how', 'when', 'where']
            english_boost = sum(1 for word in english_indicators if word.lower() in text.lower()) * 0.1
            script_scores['en'] = (latin_chars / total_chars) + english_boost

        if not script_scores:
            return LanguageDetectionResult(
                language=SupportedLanguage.ENGLISH,
                confidence=0.3,
                method=DetectionMethod.PATTERN_BASED,
                reasoning="No script patterns detected, assuming English"
            )

        # Find highest scoring language
        detected_code = max(script_scores.items(), key=lambda x: x[1])
        lang_code, confidence = detected_code

        detected_language = self._language_code_mapping.get(lang_code, SupportedLanguage.ENGLISH)

        return LanguageDetectionResult(
            language=detected_language,
            confidence=min(confidence * 1.2, 0.95),  # Boost confidence but cap at 95%
            method=DetectionMethod.PATTERN_BASED,
            raw_detection=lang_code,
            reasoning=f"Script pattern detection: {confidence:.2f} confidence for {lang_code}"
        )

    async def _detect_with_gemini_context(
        self,
        text: str,
        context: Optional[str] = None
    ) -> LanguageDetectionResult:
        """Use Gemini for context-aware language detection"""
        from app.services.gemini_client import GeminiClient, GeminiError

        try:
            gemini_client = GeminiClient()
            await gemini_client.initialize()

            # Build detection prompt
            system_prompt = self._build_gemini_detection_system_prompt()
            user_prompt = self._build_gemini_detection_user_prompt(text, context)

            # Generate detection response
            response = await gemini_client._generate_content(system_prompt, user_prompt)

            # Parse response
            detection_data = self._parse_gemini_detection_response(response)

            detected_language = self._language_code_mapping.get(
                detection_data.get('language_code', 'en'),
                SupportedLanguage.ENGLISH
            )

            return LanguageDetectionResult(
                language=detected_language,
                confidence=detection_data.get('confidence', 0.7),
                method=DetectionMethod.GEMINI_CONTEXT,
                raw_detection=detection_data.get('language_code'),
                reasoning=detection_data.get('reasoning', 'Gemini contextual analysis')
            )

        except Exception as e:
            logger.error(f"Gemini language detection failed: {e}")
            raise

    async def _detect_with_google_api(self, text: str) -> LanguageDetectionResult:
        """Fallback detection using Google Cloud Translation API"""
        if not self._google_translate_client:
            raise Exception("Google Translate client not initialized")

        try:
            # Detect language using Google API
            result = self._google_translate_client.detect_language(text)

            lang_code = result.get('language', 'en')
            confidence = result.get('confidence', 0.7)

            detected_language = self._language_code_mapping.get(lang_code, SupportedLanguage.ENGLISH)

            return LanguageDetectionResult(
                language=detected_language,
                confidence=confidence,
                method=DetectionMethod.GOOGLE_API,
                raw_detection=lang_code,
                reasoning=f"Google Cloud Translation API detection"
            )

        except Exception as e:
            logger.error(f"Google API language detection failed: {e}")
            raise

    def _build_gemini_detection_system_prompt(self) -> str:
        """Build system prompt for Gemini language detection"""
        return """You are an expert language detection specialist. Your task is to identify the language of text with high accuracy.

SUPPORTED LANGUAGES:
- English (en)
- Hindi/हिन्दी (hi) - Devanagari script
- Bengali/বাংলা (bn) - Bengali script
- Tamil/தமிழ் (ta) - Tamil script
- Telugu/తెలుగు (te) - Telugu script
- Marathi/मराठी (mr) - Devanagari script
- Gujarati/ગુજરાતી (gu) - Gujarati script
- Kannada/ಕನ್ನಡ (kn) - Kannada script
- Malayalam/മലയാളം (ml) - Malayalam script
- Punjabi/ਪੰਜਾਬੀ (pa) - Gurmukhi script
- Urdu/اردو (ur) - Arabic script

ANALYSIS APPROACH:
1. Examine script/alphabet used
2. Identify language-specific patterns
3. Consider context from conversation
4. Handle code-switching between languages
5. Provide confidence based on clarity of indicators

Always respond with valid JSON only."""

    def _build_gemini_detection_user_prompt(self, text: str, context: str = None) -> str:
        """Build user prompt for Gemini language detection"""
        context_info = ""
        if context:
            context_info = f"Previous conversation context: {context[:200]}...\n\n"

        return f"""{context_info}Text to analyze: "{text}"

Analyze the language of this text and return ONLY a JSON response:

{{
    "language_code": "xx",
    "confidence": 0.95,
    "reasoning": "Brief explanation of detection basis"
}}

Consider mixed languages and choose the dominant one for response."""

    def _parse_gemini_detection_response(self, response: str) -> Dict[str, Any]:
        """Parse Gemini's JSON detection response"""
        import json

        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")

            json_text = response[json_start:json_end]
            data = json.loads(json_text)

            # Validate and normalize data
            lang_code = data.get('language_code', 'en').lower()
            confidence = float(data.get('confidence', 0.7))
            reasoning = data.get('reasoning', 'Gemini analysis')

            return {
                'language_code': lang_code,
                'confidence': min(max(confidence, 0.0), 1.0),  # Clamp to [0,1]
                'reasoning': reasoning
            }

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse Gemini detection response: {e}")
            return {
                'language_code': 'en',
                'confidence': 0.6,
                'reasoning': 'Gemini response parsing failed'
            }

    async def _get_session_language_hint(self, session_id: str) -> Optional[SupportedLanguage]:
        """Get language hint based on session history"""
        if session_id in self._session_language_cache:
            session_data = self._session_language_cache[session_id]

            # Return language if it's been consistent
            if session_data.get('consistency_count', 0) >= 2:
                return session_data.get('preferred_language')

        return None

    async def _update_session_language(self, session_id: Optional[str], language: SupportedLanguage):
        """Update session language tracking"""
        if not session_id:
            return

        if session_id not in self._session_language_cache:
            self._session_language_cache[session_id] = {
                'preferred_language': language,
                'consistency_count': 1,
                'detections': [language]
            }
        else:
            session_data = self._session_language_cache[session_id]
            session_data['detections'].append(language)

            # Keep only last 5 detections
            session_data['detections'] = session_data['detections'][-5:]

            # Update preferred language if consistent
            recent_detections = session_data['detections']
            if len(recent_detections) >= 2:
                if recent_detections[-1] == recent_detections[-2]:
                    session_data['preferred_language'] = language
                    session_data['consistency_count'] = session_data.get('consistency_count', 0) + 1
                else:
                    session_data['consistency_count'] = max(0, session_data.get('consistency_count', 0) - 1)

    async def get_optimal_response_language(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        context: Optional[str] = None,
        user_override: Optional[SupportedLanguage] = None,
        auto_detect: bool = True
    ) -> Tuple[SupportedLanguage, LanguageDetectionResult]:
        """
        Get optimal language for response with full detection metadata.

        Returns:
            Tuple of (response_language, detection_result)
        """
        # If user explicitly overrides, use that
        if user_override and not auto_detect:
            return user_override, LanguageDetectionResult(
                language=user_override,
                confidence=1.0,
                method=DetectionMethod.SESSION_HINT,
                reasoning="User manual override"
            )

        # Auto-detect from user input
        if auto_detect and user_input.strip():
            detection_result = await self.detect_language_advanced(
                user_input, session_id, context
            )

            # Use override if detection confidence is low and override is provided
            if user_override and detection_result.confidence < 0.75:
                return user_override, LanguageDetectionResult(
                    language=user_override,
                    confidence=0.8,
                    method=DetectionMethod.SESSION_HINT,
                    reasoning="User override due to low detection confidence"
                )

            return detection_result.language, detection_result

        # Fallback to English
        return SupportedLanguage.ENGLISH, LanguageDetectionResult(
            language=SupportedLanguage.ENGLISH,
            confidence=0.5,
            method=DetectionMethod.PATTERN_BASED,
            reasoning="No auto-detection, fallback to English"
        )