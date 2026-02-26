"""
Chatterbox TTS FastAPI Application
Main entry point for the Chatterbox TTS API server
"""

import os
import sys

def check_torch_cuda():
    """Check torch and CUDA availability"""
    print("[*] Checking PyTorch and CUDA...")

    try:
        import torch
        print(f"[OK] PyTorch version: {torch.__version__}")

        if torch.cuda.is_available():
            print(f"[OK] CUDA available: {torch.cuda.get_device_name(0)}")
            print(f"[OK] CUDA version: {torch.version.cuda}")
        else:
            print("[!] CUDA not available, using CPU")

    except ImportError:
        print("[X] PyTorch not found! Please install PyTorch first.")
        print("   pip install torch torchaudio")
        return False

    return True

def setup_python_path():
    """Setup Python path for imports"""
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

    # Ensure we're in the right directory
    if os.getcwd() != ROOT_DIR:
        os.chdir(ROOT_DIR)

    # Insert ROOT_DIR so it has highest priority (index 0)
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)

    return ROOT_DIR

def create_models_if_missing(root_dir):
    """Create app/models directory if missing"""
    models_dir = os.path.join(root_dir, 'app', 'models')
    if not os.path.exists(models_dir):
        print("Creating app/models directory...")
        os.makedirs(models_dir, exist_ok=True)

        # Create __init__.py
        with open(os.path.join(models_dir, '__init__.py'), 'w') as f:
            f.write('''# Models package - Chatterbox TTS
from .voice import VoiceType, AudioFormat, VoiceCreate, VoiceUpdate, VoiceInDB, VoiceResponse, VoiceListResponse, VoiceStats
from .synthesis import SynthesisResponse
''')

        # Create voice.py
        with open(os.path.join(models_dir, 'voice.py'), 'w') as f:
            f.write('''"""Voice models for Chatterbox TTS API"""
from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class VoiceType(str, Enum):
    SFT = "sft"
    ZERO_SHOT = "zero_shot"
    CROSS_LINGUAL = "cross_lingual"
    INSTRUCT = "instruct"

class AudioFormat(str, Enum):
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"

class VoiceBase(BaseModel):
    voice_id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Human-readable voice name")
    description: Optional[str] = Field(None, description="Voice description")
    voice_type: VoiceType = Field(..., description="Type of voice")
    language: Optional[str] = Field(None, description="Primary language of the voice")

class VoiceCreate(VoiceBase):
    prompt_text: Optional[str] = Field(None, description="Text that matches the audio sample")
    audio_format: AudioFormat = Field(AudioFormat.WAV, description="Audio file format")

class VoiceUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Human-readable voice name")
    description: Optional[str] = Field(None, description="Voice description")
    language: Optional[str] = Field(None, description="Primary language of the voice")

class VoiceInDB(VoiceBase):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    audio_file_path: Optional[str] = Field(None, description="Path to audio file")
    prompt_text: Optional[str] = Field(None, description="Text that matches the audio sample")
    audio_format: AudioFormat = Field(AudioFormat.WAV, description="Audio file format")
    file_size: Optional[int] = Field(None, description="Audio file size in bytes")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    sample_rate: Optional[int] = Field(None, description="Audio sample rate")
    is_active: bool = Field(True, description="Whether the voice is active")

class VoiceResponse(VoiceBase):
    created_at: datetime
    updated_at: datetime
    audio_format: AudioFormat
    file_size: Optional[int] = None
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    is_active: bool = True

class VoiceListResponse(BaseModel):
    voices: List[VoiceResponse]
    total: int
    page: int = 1
    per_page: int = 10

class VoiceStats(BaseModel):
    total_voices: int = 0
    active_voices: int = 0
    voice_types: dict = Field(default_factory=dict)
    languages: dict = Field(default_factory=dict)
    total_duration: float = 0.0
    total_size: int = 0
''')

        # Create synthesis.py
        with open(os.path.join(models_dir, 'synthesis.py'), 'w') as f:
            f.write('''"""Synthesis models for Chatterbox TTS API"""
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum
from .voice import AudioFormat

class SynthesisMode(str, Enum):
    ZERO_SHOT = "zero_shot"
    CROSS_LINGUAL = "cross_lingual"

class SynthesisRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize", max_length=1000)
    speed: float = Field(1.0, description="Synthesis speed", ge=0.5, le=2.0)
    format: AudioFormat = Field(AudioFormat.WAV, description="Output audio format")
    stream: bool = Field(False, description="Enable streaming synthesis")

class SynthesisResponse(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Synthesis status")
    audio_url: Optional[str] = Field(None, description="URL to download the generated audio")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    format: AudioFormat = Field(..., description="Audio format")
    created_at: str = Field(..., description="Task creation timestamp")
    completed_at: Optional[str] = Field(None, description="Task completion timestamp")
    error: Optional[str] = Field(None, description="Error message if synthesis failed")
''')

        print("[OK] app/models directory and files created")

# CRITICAL: Setup everything before any other imports
print("[*] Chatterbox TTS API - Starting Server")
if not check_torch_cuda():
    print("[X] PyTorch check failed. Please install dependencies first.")
    sys.exit(1)
ROOT_DIR = setup_python_path()
create_models_if_missing(ROOT_DIR)

# Now import everything else
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v4.router import api_router_v4  # Chatterbox TTS
from app.core.exceptions import setup_exception_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
voice_manager_chatterbox = None  # VoiceManagerChatterbox
shared_voice_cache = None  # SharedVoiceCache


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global voice_manager_chatterbox, shared_voice_cache

    logger.info("Starting Chatterbox TTS API server...")

    # NOTE: Synthesis uses its own dedicated executor (1 thread) in synthesis_engine_chatterbox.py
    # The default asyncio executor handles general I/O (file ops, voice uploads, etc.)
    # Do NOT override the default executor - it must remain available for non-synthesis tasks

    try:
        # ===============================
        # Initialize Shared Voice Cache
        # ===============================
        logger.info("Initializing shared voice cache...")
        from app.core.shared_voice_cache import initialize_shared_cache
        shared_voice_cache = await initialize_shared_cache()
        logger.info("Shared voice cache initialized")

        cache_dir = os.path.abspath(settings.VOICE_CACHE_DIR)

        # ===============================
        # Initialize Chatterbox (v4)
        # ===============================
        logger.info("Initializing Chatterbox TTS...")
        try:
            from app.core.voice_manager_chatterbox import VoiceManagerChatterbox
            from app.core.synthesis_engine_chatterbox import SynthesisEngineChatterbox

            chatterbox_model_dir = os.path.abspath("models/chatterbox")
            voice_manager_chatterbox = VoiceManagerChatterbox(
                model_dir=chatterbox_model_dir,
                cache_dir=cache_dir,
                shared_cache=shared_voice_cache
            )
            await voice_manager_chatterbox.initialize(model_type=settings.CHATTERBOX_MODEL_TYPE)
            logger.info(f"Chatterbox voice manager initialized (model: {settings.CHATTERBOX_MODEL_TYPE})")

            # Create synthesis engine
            synthesis_engine_chatterbox = SynthesisEngineChatterbox(voice_manager_chatterbox)

            # Store in app state
            app.state.voice_manager_chatterbox = voice_manager_chatterbox
            app.state.synthesis_engine_chatterbox = synthesis_engine_chatterbox
            logger.info("Chatterbox TTS initialized successfully")

        except ImportError as e:
            logger.error(f"Chatterbox not installed: {e}")
            logger.info("Install with: pip install chatterbox-tts")
            raise
        except Exception as e:
            logger.error(f"Chatterbox initialization failed: {e}")
            raise

        yield

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        logger.info("Shutting down Chatterbox TTS API server...")
        if voice_manager_chatterbox:
            await voice_manager_chatterbox.cleanup()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title="Chatterbox TTS API",
        description="""
# Chatterbox TTS API

Fast voice cloning with paralinguistic tags support.

## Features

- 3 model types: Turbo (fast), Multilingual (23+ languages), Original (CFG control)
- Paralinguistic tags: [laugh], [cough], [sigh], [gasp], [clear throat]
- Voice exaggeration control
- Perth watermarking for AI detection

## Endpoints

- `/api/v4/voices/` - Voice management
- `/api/v4/synthesis/with-audio` - Synthesis with audio reference
- `/api/v4/synthesis/with-cache` - Synthesis with cached voice
- `/api/v4/synthesis/multilingual` - Multilingual synthesis
- `/api/v4/synthesis/capabilities` - Model capabilities
- `/api/v4/synthesis/tags` - Supported paralinguistic tags
        """,
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

    # Middleware to handle body parsing errors gracefully
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse as StarletteJSONResponse

    class BodyParsingErrorMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            try:
                response = await call_next(request)
                return response
            except Exception as e:
                error_msg = str(e).lower()
                if "parsing" in error_msg or "multipart" in error_msg or "content-type" in error_msg:
                    logger.warning(f"Body parsing error on {request.url.path}: {e}")
                    return StarletteJSONResponse(
                        status_code=400,
                        content={
                            "error": "invalid_request_body",
                            "message": "Failed to parse request body. Ensure Content-Type is multipart/form-data for endpoints that accept file uploads or form data.",
                            "details": {"path": str(request.url)}
                        }
                    )
                raise

    app.add_middleware(BodyParsingErrorMiddleware)

    # Setup exception handlers
    setup_exception_handlers(app)

    # Include API routes - v4 (Chatterbox)
    app.include_router(api_router_v4, prefix="/api/v4")

    # Mount static files for audio serving
    app.mount("/api/v4/audio", StaticFiles(directory="outputs"), name="audio_v4")

    @app.get("/")
    async def root():
        return {
            "message": "Chatterbox TTS API Server",
            "description": "Fast voice cloning with paralinguistic tags",
            "version": "1.0.0",
            "docs": "/docs",
            "endpoints": {
                "voice_management": "/api/v4/voices/",
                "synthesis_with_audio": "/api/v4/synthesis/with-audio",
                "synthesis_with_cache": "/api/v4/synthesis/with-cache",
                "multilingual_synthesis": "/api/v4/synthesis/multilingual",
                "capabilities": "/api/v4/synthesis/capabilities",
                "supported_tags": "/api/v4/synthesis/tags"
            },
            "features": [
                "3 model types: Turbo, Multilingual, Original",
                "Paralinguistic tags: [laugh], [cough], [sigh], etc.",
                "Voice exaggeration control",
                "23+ languages (multilingual model)",
                "CFG control (original model)",
                "Perth watermarking"
            ]
        }

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        v4_ready = voice_manager_chatterbox is not None and voice_manager_chatterbox.is_ready() if voice_manager_chatterbox else False
        return {
            "status": "healthy" if v4_ready else "unhealthy",
            "chatterbox": {
                "ready": v4_ready,
                "model": f"Chatterbox-{voice_manager_chatterbox.model_type}" if v4_ready else "Not loaded"
            }
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
