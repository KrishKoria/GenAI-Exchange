"""
Health check endpoints
"""
import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=Dict[str, Any])
async def health_check(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """
    Health check endpoint for service monitoring.
    
    Returns:
        Service health status and basic information
    """
    return {
        "status": "healthy",
        "service": "clausecompass-api",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
    }


@router.get("/ready", response_model=Dict[str, Any])
async def readiness_check(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """
    Readiness check endpoint for Kubernetes/Cloud Run.
    
    Returns:
        Service readiness status
    """
    # TODO: Add checks for GCP services connectivity
    # - Firestore connection
    # - Document AI availability
    # - Vertex AI access
    
    return {
        "status": "ready",
        "service": "clausecompass-api",
        "checks": {
            "firestore": "not_implemented",
            "document_ai": "not_implemented", 
            "vertex_ai": "not_implemented",
        }
    }