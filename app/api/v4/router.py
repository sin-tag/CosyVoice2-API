"""
Main API router for v4 endpoints - Chatterbox TTS
Advanced voice cloning API with Chatterbox features including paralinguistic tags
"""

from fastapi import APIRouter

from app.api.v4 import voices, synthesis

# Create main API router
api_router_v4 = APIRouter()

# Include sub-routers
api_router_v4.include_router(voices.router)  # Voice management (upload, list, delete)
api_router_v4.include_router(synthesis.router)  # Voice cloning synthesis with Chatterbox
