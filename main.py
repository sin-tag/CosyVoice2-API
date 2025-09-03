"""
CosyVoice2 FastAPI Application
Main entry point for the CosyVoice2 API server
"""

import os
import sys

# CRITICAL: Set up Python path FIRST - BULLETPROOF VERSION
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure we're in the right directory (the project root)
if os.getcwd() != ROOT_DIR:
    os.chdir(ROOT_DIR)

# Auto-detect CosyVoice directory
cosyvoice_dir = None
for dirname in ['cosyvoice', 'cosyvoice_original']:
    test_dir = os.path.join(ROOT_DIR, dirname)
    if os.path.exists(test_dir):
        cosyvoice_dir = test_dir
        print(f"DEBUG: Found CosyVoice directory: {dirname}")
        break

# Add all necessary paths
PATHS_TO_ADD = [ROOT_DIR]
if cosyvoice_dir:
    PATHS_TO_ADD.extend([
        cosyvoice_dir,
        os.path.join(cosyvoice_dir, 'third_party', 'Matcha-TTS')
    ])
else:
    print("DEBUG: No CosyVoice directory found")

# Insert paths at the very beginning
for path in PATHS_TO_ADD:
    if os.path.exists(path):
        if path in sys.path:
            sys.path.remove(path)  # Remove if exists
        sys.path.insert(0, path)  # Add at beginning

# Special handling for Matcha-TTS matcha module
if cosyvoice_dir:
    matcha_tts_dir = os.path.join(cosyvoice_dir, 'third_party', 'Matcha-TTS')
    if os.path.exists(matcha_tts_dir):
        # Also add the matcha source directory specifically
        matcha_src_dir = os.path.join(matcha_tts_dir, 'matcha')
        if os.path.exists(matcha_src_dir):
            if matcha_src_dir in sys.path:
                sys.path.remove(matcha_src_dir)
            sys.path.insert(0, matcha_src_dir)
            print(f"DEBUG: Added Matcha source directory: {matcha_src_dir}")

# Set PYTHONPATH environment variable
os.environ['PYTHONPATH'] = os.pathsep.join([p for p in PATHS_TO_ADD if os.path.exists(p)])

# Debug info for troubleshooting
print(f"DEBUG: Working directory: {os.getcwd()}")
print(f"DEBUG: Root directory: {ROOT_DIR}")
print(f"DEBUG: Python path (first 3): {sys.path[:3]}")

# Test critical import immediately
try:
    import app.models.voice
    print("DEBUG: app.models.voice import successful")
except ImportError as e:
    print(f"DEBUG: app.models.voice import failed: {e}")
    # List contents of app directory
    app_dir = os.path.join(ROOT_DIR, 'app')
    if os.path.exists(app_dir):
        print(f"DEBUG: Contents of {app_dir}: {os.listdir(app_dir)}")
        models_dir = os.path.join(app_dir, 'models')
        if os.path.exists(models_dir):
            print(f"DEBUG: Contents of {models_dir}: {os.listdir(models_dir)}")
    raise

# Now import everything else
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.voice_manager import VoiceManager
from app.core.async_synthesis import AsyncSynthesisManager
from app.core.synthesis_engine import SynthesisEngine
from app.api.v1.router import api_router
from app.core.exceptions import setup_exception_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
voice_manager: VoiceManager = None
async_synthesis_manager: AsyncSynthesisManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global voice_manager, async_synthesis_manager

    logger.info("Starting CosyVoice2 API server...")

    try:
        # Initialize voice manager
        voice_manager = VoiceManager(
            model_dir=settings.MODEL_DIR,
            cache_dir=settings.VOICE_CACHE_DIR
        )

        # Load cached voices on startup
        await voice_manager.initialize()
        logger.info("Voice manager initialized successfully")

        # Initialize synthesis engine and async manager
        synthesis_engine = SynthesisEngine(voice_manager)
        async_synthesis_manager = AsyncSynthesisManager(synthesis_engine)
        await async_synthesis_manager.start()
        logger.info("Async synthesis manager initialized successfully")

        # Store in app state for access in routes
        app.state.voice_manager = voice_manager
        app.state.async_synthesis_manager = async_synthesis_manager

        yield

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        logger.info("Shutting down CosyVoice2 API server...")
        if async_synthesis_manager:
            await async_synthesis_manager.stop()
        if voice_manager:
            await voice_manager.cleanup()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="CosyVoice2 API",
        description="FastAPI server for CosyVoice2 voice cloning and synthesis",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Setup exception handlers
    setup_exception_handlers(app)
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
    @app.get("/")
    async def root():
        return {
            "message": "CosyVoice2 API Server",
            "version": "1.0.0",
            "docs": "/docs"
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "voice_manager_ready": voice_manager is not None and voice_manager.is_ready(),
            "async_synthesis_ready": async_synthesis_manager is not None
        }
    
    return app


# Create the FastAPI app
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
