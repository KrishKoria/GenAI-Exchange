"""
Service dependencies for FastAPI with singleton pattern to optimize performance.
"""
import logging
from functools import lru_cache
from typing import Optional

from app.services.firestore_client import FirestoreClient
from app.services.embeddings_service import EmbeddingsService
from app.services.gemini_client import GeminiClient
from app.services.chat_session_service import ChatSessionService
from app.services.cache_service import InMemoryCache, get_cache
from app.services.document_orchestrator import DocumentOrchestrator

logger = logging.getLogger(__name__)

# Global service instances (singletons)
_firestore_client: Optional[FirestoreClient] = None
_embeddings_service: Optional[EmbeddingsService] = None
_gemini_client: Optional[GeminiClient] = None
_chat_session_service: Optional[ChatSessionService] = None
_document_orchestrator: Optional[DocumentOrchestrator] = None


@lru_cache()
def get_cache_service() -> InMemoryCache:
    """
    Get singleton Cache service instance.
    Uses lru_cache to ensure only one instance is created.
    """
    return get_cache()


@lru_cache()
def get_firestore_client() -> FirestoreClient:
    """
    Get singleton Firestore client instance.
    Uses lru_cache to ensure only one instance is created.
    """
    global _firestore_client
    if _firestore_client is None:
        logger.info("Initializing singleton Firestore client")
        _firestore_client = FirestoreClient()
    return _firestore_client


@lru_cache()
def get_embeddings_service() -> EmbeddingsService:
    """
    Get singleton Embeddings service instance.
    Uses lru_cache to ensure only one instance is created.
    """
    global _embeddings_service
    if _embeddings_service is None:
        logger.info("Initializing singleton Embeddings service")
        _embeddings_service = EmbeddingsService()
    return _embeddings_service


@lru_cache()
def get_gemini_client() -> GeminiClient:
    """
    Get singleton Gemini client instance.
    Uses lru_cache to ensure only one instance is created.
    """
    global _gemini_client
    if _gemini_client is None:
        logger.info("Initializing singleton Gemini client")
        _gemini_client = GeminiClient()
    return _gemini_client


@lru_cache()
def get_chat_session_service() -> ChatSessionService:
    """
    Get singleton Chat Session service instance.
    Uses lru_cache to ensure only one instance is created.
    """
    global _chat_session_service
    if _chat_session_service is None:
        logger.info("Initializing singleton Chat Session service")
        _chat_session_service = ChatSessionService()
    return _chat_session_service


@lru_cache()
def get_document_orchestrator() -> DocumentOrchestrator:
    """
    Get singleton Document Orchestrator instance.
    Uses lru_cache to ensure only one instance is created.
    """
    global _document_orchestrator
    if _document_orchestrator is None:
        logger.info("Initializing singleton Document Orchestrator")
        _document_orchestrator = DocumentOrchestrator()
    return _document_orchestrator


def reset_services():
    """
    Reset all service instances (useful for testing or reinitialization).
    """
    global _firestore_client, _embeddings_service, _gemini_client, _chat_session_service, _document_orchestrator
    
    logger.info("Resetting all service instances")
    
    _firestore_client = None
    _embeddings_service = None
    _gemini_client = None
    _chat_session_service = None
    _document_orchestrator = None
    
    # Clear lru_cache for all dependency functions
    get_firestore_client.cache_clear()
    get_embeddings_service.cache_clear()
    get_gemini_client.cache_clear()
    get_chat_session_service.cache_clear()
    get_document_orchestrator.cache_clear()
    get_cache_service.cache_clear()
    get_embeddings_service.cache_clear()
    get_gemini_client.cache_clear()
    get_chat_session_service.cache_clear()


async def initialize_services():
    """
    Initialize all services at startup for faster subsequent access.
    """
    logger.info("Pre-initializing all services for optimal performance")
    
    # Initialize all services
    firestore_client = get_firestore_client()
    embeddings_service = get_embeddings_service()
    gemini_client = get_gemini_client()
    chat_session_service = get_chat_session_service()
    cache_service = get_cache_service()
    
    # Initialize Gemini client (async initialization)
    await gemini_client.initialize()
    
    # Start cache cleanup task
    from app.services.cache_service import start_cache_cleanup_task
    await start_cache_cleanup_task()
    
    logger.info("All services pre-initialized successfully")