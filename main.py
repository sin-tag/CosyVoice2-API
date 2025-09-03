"""
CosyVoice2 FastAPI Application
Main entry point for the CosyVoice2 API server
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add the project root to Python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT_DIR)
sys.path.append(f'{ROOT_DIR}/cosyvoice_original')
sys.path.append(f'{ROOT_DIR}/cosyvoice_original/third_party/Matcha-TTS')

from app.core.config import settings
from app.core.voice_manager import VoiceManager
from app.api.v1.router import api_router
from app.core.exceptions import setup_exception_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global voice manager instance
voice_manager: VoiceManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global voice_manager
    
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
        
        # Store in app state for access in routes
        app.state.voice_manager = voice_manager
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        logger.info("Shutting down CosyVoice2 API server...")
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
            "voice_manager_ready": voice_manager is not None and voice_manager.is_ready()
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
