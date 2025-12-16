"""
Main API router for v2 endpoints - CosyVoice2 (Legacy Support)
Simplified API focused on cross-lingual voice cloning functionality
"""

from fastapi import APIRouter

from app.api.v2 import voices, synthesis, tasks, streaming, websocket

# Create main API router
api_router_v2 = APIRouter()

# Include sub-routers
api_router_v2.include_router(voices.router)  # Voice management (upload, list, delete)
api_router_v2.include_router(synthesis.router)  # Cross-lingual synthesis
api_router_v2.include_router(tasks.router)  # Task-based synthesis
api_router_v2.include_router(streaming.router)  # Real-time streaming synthesis
api_router_v2.include_router(websocket.router)  # WebSocket bidirectional streaming
