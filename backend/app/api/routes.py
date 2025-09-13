"""
API routes configuration
"""
from fastapi import APIRouter

from app.api.v1.endpoints import documents, health, metrics, qa, chat

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"]
)

api_router.include_router(
    qa.router,
    prefix="/qa",
    tags=["question-answering"]
)

api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["chat-sessions"]
)

api_router.include_router(
    metrics.router,
    prefix="/metrics",
    tags=["metrics"]
)