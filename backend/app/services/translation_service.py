"""
Translation Service for multilingual document analysis support
Uses Google Cloud Translation API for professional-quality translations
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from google.cloud import translate_v2 as translate
from google.api_core.exceptions import GoogleAPIError

from app.core.config import get_settings
from app.core.logging import get_logger, LogContext, log_execution_time
from app.models.document import SupportedLanguage

logger = get_logger(__name__)


class TranslationError(Exception):
    """Custom exception for translation errors."""
    pass


@dataclass
class TranslationResult:
    """Result of a translation operation."""
    translated_text: str
    source_language: str
    target_language: str
    confidence: float
    method: str  # 'google_api' or 'cached'
    detected_source_language: Optional[str] = None


class TranslationService:
    """
    Service for translating legal document analysis outputs using Google Cloud Translation API.
    
    Features:
    - Batch translation for performance
    - In-memory caching to avoid redundant API calls
    - Async support for non-blocking operations
    - Fallback to English on translation failures
    - Preserves legal terminology accuracy
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[translate.Client] = None
        self._initialized = False
        self._translation_cache: Dict[str, str] = {}  # cache_key -> translated_text
        
        # Language code mapping
        self._language_code_map = {
            SupportedLanguage.ENGLISH: 'en',
            SupportedLanguage.HINDI: 'hi',
            SupportedLanguage.BENGALI: 'bn',
            SupportedLanguage.TAMIL: 'ta',
            SupportedLanguage.TELUGU: 'te',
            SupportedLanguage.MARATHI: 'mr',
            SupportedLanguage.GUJARATI: 'gu',
            SupportedLanguage.KANNADA: 'kn',
            SupportedLanguage.MALAYALAM: 'ml',
            SupportedLanguage.PUNJABI: 'pa',
            SupportedLanguage.URDU: 'ur',
        }
    
    async def initialize(self):
        """Initialize Google Cloud Translation client."""
        if self._initialized:
            return
        
        try:
            logger.info("Initializing Translation Service...")
            self._client = translate.Client()
            self._initialized = True
            logger.info("Translation Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Translation Service: {e}")
            raise TranslationError(f"Translation service initialization failed: {e}")
    
    async def translate_text(
        self,
        text: str,
        target_language: SupportedLanguage,
        source_language: Optional[SupportedLanguage] = None,
        use_cache: bool = True
    ) -> TranslationResult:
        """
        Translate a single text to the target language.
        
        Args:
            text: Text to translate
            target_language: Target language for translation
            source_language: Source language (auto-detected if None)
            use_cache: Whether to use cached translations
            
        Returns:
            TranslationResult with translated text and metadata
        """
        await self.initialize()
        
        if not text or not text.strip():
            return TranslationResult(
                translated_text="",
                source_language=source_language.value if source_language else "unknown",
                target_language=target_language.value,
                confidence=1.0,
                method="cached"
            )
        
        # Convert SupportedLanguage to language codes
        target_code = self._language_code_map.get(target_language, 'en')
        source_code = self._language_code_map.get(source_language, 'en') if source_language else None
        
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(text, source_code, target_code)
            cached_translation = self._translation_cache.get(cache_key)
            if cached_translation:
                logger.debug(f"Using cached translation for: {text[:50]}...")
                return TranslationResult(
                    translated_text=cached_translation,
                    source_language=source_code or "auto",
                    target_language=target_code,
                    confidence=1.0,
                    method="cached"
                )
        
        # Perform translation
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Call Google Translate API
            translation_result = await asyncio.to_thread(
                self._client.translate,
                text,
                target_language=target_code,
                source_language=source_code
            )
            
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            log_execution_time(logger, "translation", processing_time)
            
            translated_text = translation_result['translatedText']
            detected_source = translation_result.get('detectedSourceLanguage', source_code)
            
            # Cache the result
            if use_cache:
                cache_key = self._get_cache_key(text, source_code or detected_source, target_code)
                self._translation_cache[cache_key] = translated_text
            
            logger.info(f"Translated text from {detected_source} to {target_code}: {len(text)} chars")
            
            return TranslationResult(
                translated_text=translated_text,
                source_language=source_code or "auto",
                target_language=target_code,
                confidence=0.95,  # Google Translate is highly accurate
                method="google_api",
                detected_source_language=detected_source
            )
            
        except GoogleAPIError as e:
            logger.error(f"Google Translation API error: {e}")
            raise TranslationError(f"Translation failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected translation error: {e}")
            raise TranslationError(f"Translation failed: {e}")
    
    async def translate_batch(
        self,
        texts: List[str],
        target_language: SupportedLanguage,
        source_language: Optional[SupportedLanguage] = None,
        use_cache: bool = True
    ) -> List[TranslationResult]:
        """
        Translate multiple texts in batch for better performance.
        
        Args:
            texts: List of texts to translate
            target_language: Target language for all translations
            source_language: Source language (auto-detected if None)
            use_cache: Whether to use cached translations
            
        Returns:
            List of TranslationResult objects
        """
        await self.initialize()
        
        if not texts:
            return []
        
        with LogContext(logger, batch_size=len(texts), target_language=target_language.value):
            logger.info("Starting batch translation")
            
            target_code = self._language_code_map.get(target_language, 'en')
            source_code = self._language_code_map.get(source_language, 'en') if source_language else None
            
            results = []
            texts_to_translate = []
            indices_to_translate = []
            
            # Check cache and separate texts that need translation
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    results.append(TranslationResult(
                        translated_text="",
                        source_language=source_code or "auto",
                        target_language=target_code,
                        confidence=1.0,
                        method="cached"
                    ))
                    continue
                
                if use_cache:
                    cache_key = self._get_cache_key(text, source_code, target_code)
                    cached = self._translation_cache.get(cache_key)
                    if cached:
                        results.append(TranslationResult(
                            translated_text=cached,
                            source_language=source_code or "auto",
                            target_language=target_code,
                            confidence=1.0,
                            method="cached"
                        ))
                        continue
                
                # This text needs translation
                texts_to_translate.append(text)
                indices_to_translate.append(i)
                results.append(None)  # Placeholder
            
            # Translate texts that weren't cached
            if texts_to_translate:
                try:
                    start_time = asyncio.get_event_loop().time()
                    
                    # Call Google Translate API in batch
                    translation_results = await asyncio.to_thread(
                        self._client.translate,
                        texts_to_translate,
                        target_language=target_code,
                        source_language=source_code
                    )
                    
                    processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    log_execution_time(logger, "batch_translation", processing_time)
                    
                    # Process results
                    for idx, translation_result in zip(indices_to_translate, translation_results):
                        translated_text = translation_result['translatedText']
                        detected_source = translation_result.get('detectedSourceLanguage', source_code)
                        
                        # Cache the result
                        if use_cache:
                            cache_key = self._get_cache_key(
                                texts_to_translate[indices_to_translate.index(idx)],
                                source_code or detected_source,
                                target_code
                            )
                            self._translation_cache[cache_key] = translated_text
                        
                        results[idx] = TranslationResult(
                            translated_text=translated_text,
                            source_language=source_code or "auto",
                            target_language=target_code,
                            confidence=0.95,
                            method="google_api",
                            detected_source_language=detected_source
                        )
                    
                    logger.info(f"Batch translation completed: {len(texts_to_translate)} texts translated")
                    
                except Exception as e:
                    logger.error(f"Batch translation failed: {e}")
                    # Fill remaining results with error fallback
                    for idx in indices_to_translate:
                        if results[idx] is None:
                            results[idx] = TranslationResult(
                                translated_text=texts[idx],  # Return original text as fallback
                                source_language=source_code or "auto",
                                target_language=target_code,
                                confidence=0.0,
                                method="failed"
                            )
            
            return results
    
    async def translate_clause_summary(
        self,
        summary: str,
        target_language: SupportedLanguage,
        negotiation_tip: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Translate clause summary and optional negotiation tip.
        
        Args:
            summary: Clause summary in English
            target_language: Target language for translation
            negotiation_tip: Optional negotiation tip to translate
            
        Returns:
            Dictionary with 'summary' and optionally 'negotiation_tip' keys
        """
        texts_to_translate = [summary]
        if negotiation_tip:
            texts_to_translate.append(negotiation_tip)
        
        results = await self.translate_batch(
            texts_to_translate,
            target_language,
            source_language=SupportedLanguage.ENGLISH
        )
        
        translations = {"summary": results[0].translated_text}
        if negotiation_tip and len(results) > 1:
            translations["negotiation_tip"] = results[1].translated_text
        
        return translations
    
    async def translate_qa_response(
        self,
        answer: str,
        target_language: SupportedLanguage,
        additional_insights: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Translate Q&A response and optional additional insights.
        
        Args:
            answer: Answer text in English
            target_language: Target language for translation
            additional_insights: Optional additional insights to translate
            
        Returns:
            Dictionary with 'answer' and optionally 'additional_insights' keys
        """
        texts_to_translate = [answer]
        if additional_insights:
            texts_to_translate.append(additional_insights)
        
        results = await self.translate_batch(
            texts_to_translate,
            target_language,
            source_language=SupportedLanguage.ENGLISH
        )
        
        translations = {"answer": results[0].translated_text}
        if additional_insights and len(results) > 1:
            translations["additional_insights"] = results[1].translated_text
        
        return translations
    
    def _get_cache_key(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        """Generate cache key for a translation."""
        import hashlib
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"{source_lang or 'auto'}_{target_lang}_{text_hash}"
    
    def clear_cache(self):
        """Clear the translation cache."""
        self._translation_cache.clear()
        logger.info("Translation cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get translation cache statistics."""
        return {
            "cache_size": len(self._translation_cache),
            "cache_keys": list(self._translation_cache.keys())[:10]  # Sample of keys
        }
