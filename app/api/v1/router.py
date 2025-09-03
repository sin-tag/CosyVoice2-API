"""
Main API router for v1 endpoints
"""

from fastapi import APIRouter

from app.api.v1 import voices, synthesis, async_synthesis

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(voices.router)
api_router.include_router(synthesis.router)
api_router.include_router(async_synthesis.router)
