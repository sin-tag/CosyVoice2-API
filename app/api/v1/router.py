"""
Main API router for v1 endpoints - 跨语种复刻 (Cross-lingual Voice Cloning)
Simplified API focused on cross-lingual voice cloning functionality
"""

from fastapi import APIRouter

from app.api.v1 import voices, synthesis, tasks

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(voices.router)  # Voice management (upload, list, delete)
api_router.include_router(synthesis.router)  # Cross-lingual synthesis
api_router.include_router(tasks.router)  # Task-based synthesis
