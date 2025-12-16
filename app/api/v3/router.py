"""
Main API router for v3 endpoints - CosyVoice3 (Latest)
Advanced API with CosyVoice3 features including instruct2 and improved multilingual support
"""

from fastapi import APIRouter

from app.api.v3 import voices, synthesis, tasks, streaming, websocket

# Create main API router
api_router_v3 = APIRouter()

# Include sub-routers
api_router_v3.include_router(voices.router)  # Voice management (upload, list, delete)
api_router_v3.include_router(synthesis.router)  # Cross-lingual synthesis with CosyVoice3
api_router_v3.include_router(tasks.router)  # Task-based synthesis
api_router_v3.include_router(streaming.router)  # Real-time streaming synthesis
api_router_v3.include_router(websocket.router)  # WebSocket bidirectional streaming
