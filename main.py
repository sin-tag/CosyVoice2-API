"""
CosyVoice2 FastAPI Application - Auto Setup Version
Main entry point for the CosyVoice2 API server
"""

import os
import sys
import subprocess

def setup_cosyvoice():
    """Auto setup CosyVoice if not exists"""
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    cosyvoice_dir = os.path.join(ROOT_DIR, 'cosyvoice_original')

    if not os.path.exists(cosyvoice_dir):
        print("🔄 CosyVoice not found, cloning...")
        try:
            subprocess.check_call([
                'git', 'clone',
                'https://github.com/FunAudioLLM/CosyVoice.git',
                'cosyvoice_original'
            ], cwd=ROOT_DIR)
            print("✓ CosyVoice cloned successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to clone CosyVoice: {e}")
            return False

    # Update submodules (Matcha-TTS)
    matcha_dir = os.path.join(cosyvoice_dir, 'third_party', 'Matcha-TTS')
    if not os.path.exists(matcha_dir) or not os.listdir(matcha_dir):
        print("🔄 Updating submodules (Matcha-TTS)...")
        try:
            subprocess.check_call([
                'git', 'submodule', 'update', '--init', '--recursive'
            ], cwd=cosyvoice_dir)
            print("✓ Submodules updated successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to update submodules: {e}")
            return False

    return True

def check_torch_cuda():
    """Check torch and CUDA availability"""
    print("� Checking PyTorch and CUDA...")

    try:
        import torch
        print(f"✓ PyTorch version: {torch.__version__}")

        if torch.cuda.is_available():
            print(f"✓ CUDA available: {torch.cuda.get_device_name(0)}")
            print(f"✓ CUDA version: {torch.version.cuda}")
        else:
            print("⚠️  CUDA not available, using CPU")

    except ImportError:
        print("❌ PyTorch not found! Please install PyTorch first.")
        print("   pip install torch torchaudio")
        return False

    return True

def setup_python_path():
    """Setup Python path for imports"""
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

    # Ensure we're in the right directory
    if os.getcwd() != ROOT_DIR:
        os.chdir(ROOT_DIR)

    # Setup paths - only add what we absolutely need
    paths = [
        ROOT_DIR,  # Our project root should come first
        os.path.join(ROOT_DIR, 'cosyvoice_original'),
    ]

    # Insert paths - ROOT_DIR first to ensure our app module takes precedence
    for path in paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)

    # Set PYTHONPATH
    os.environ['PYTHONPATH'] = os.pathsep.join([p for p in paths if os.path.exists(p)])

    return ROOT_DIR

def create_models_if_missing(root_dir):
    """Create app/models directory if missing"""
    models_dir = os.path.join(root_dir, 'app', 'models')
    if not os.path.exists(models_dir):
        print("🔄 Creating app/models directory...")
        os.makedirs(models_dir, exist_ok=True)

        # Create __init__.py
        with open(os.path.join(models_dir, '__init__.py'), 'w') as f:
            f.write('''# Models package - 跨语种复刻 (Cross-lingual Voice Cloning)
from .voice import VoiceType, AudioFormat, VoiceCreate, VoiceUpdate, VoiceInDB, VoiceResponse, VoiceListResponse, VoiceStats
from .synthesis import CrossLingualWithAudioRequest, CrossLingualWithCacheRequest, SynthesisResponse
''')

        # Create voice.py
        with open(os.path.join(models_dir, 'voice.py'), 'w') as f:
            f.write('''"""Voice models for CosyVoice2 API"""
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
            f.write('''"""Synthesis models for CosyVoice2 API"""
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum
from .voice import AudioFormat

class SynthesisMode(str, Enum):
    SFT = "sft"
    ZERO_SHOT = "zero_shot"
    CROSS_LINGUAL = "cross_lingual"
    INSTRUCT = "instruct"

class SynthesisRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize", max_length=1000)
    speed: float = Field(1.0, description="Synthesis speed", ge=0.5, le=2.0)
    format: AudioFormat = Field(AudioFormat.WAV, description="Output audio format")
    stream: bool = Field(False, description="Enable streaming synthesis")

class SFTSynthesisRequest(SynthesisRequest):
    voice_id: str = Field(..., description="Pre-trained voice ID")

class ZeroShotSynthesisRequest(SynthesisRequest):
    voice_id: Optional[str] = Field(None, description="Cached voice ID (if using cached voice)")
    prompt_text: Optional[str] = Field(None, description="Text that matches the prompt audio")

class CrossLingualSynthesisRequest(ZeroShotSynthesisRequest):
    target_language: str = Field(..., description="Target language for synthesis")

class InstructSynthesisRequest(SynthesisRequest):
    voice_id: str = Field(..., description="Pre-trained voice ID")
    instruct_text: str = Field(..., description="Natural language instruction for synthesis control")

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

        print("✓ app/models directory and files created")

# CRITICAL: Setup everything before any other imports
print("🚀 CosyVoice2 API - Starting Server")
setup_cosyvoice()
if not check_torch_cuda():
    print("❌ PyTorch check failed. Please install dependencies first.")
    sys.exit(1)
ROOT_DIR = setup_python_path()
create_models_if_missing(ROOT_DIR)

# Now import everything else
import asyncio
import concurrent.futures
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.voice_manager import VoiceManager
from app.core.voice_manager_v3 import VoiceManagerV3
from app.core.synthesis_engine import SynthesisEngine
from app.core.async_synthesis_manager import AsyncSynthesisManager
from app.core.model_downloader import ensure_cosyvoice3_model
from app.api.v1.router import api_router  # Keep v1 for backward compatibility
from app.api.v2.router import api_router_v2
from app.api.v3.router import api_router_v3
from app.core.exceptions import setup_exception_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
voice_manager: VoiceManager = None
voice_manager_v3: VoiceManagerV3 = None
async_synthesis_manager: AsyncSynthesisManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global voice_manager, voice_manager_v3, async_synthesis_manager

    logger.info("Starting CosyVoice API server (v2 + v3)...")

    # Configure thread pool for MAXIMUM parallelism
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=16,  # High thread count for true parallelism
        thread_name_prefix="synthesis_"
    )
    loop.set_default_executor(executor)
    logger.info(f"Thread pool configured with {executor._max_workers} workers for unlimited parallel processing")

    try:
        # ===============================
        # Initialize CosyVoice2 (v2) - Legacy
        # ===============================
        voice_manager = VoiceManager(
            model_dir=settings.MODEL_DIR,
            cache_dir=settings.VOICE_CACHE_DIR
        )

        await voice_manager.initialize()
        logger.info("CosyVoice2 voice manager initialized successfully")

        # Initialize async synthesis manager for v2
        logger.info("Initializing async synthesis manager (v2)...")
        synthesis_engine = SynthesisEngine(voice_manager)
        async_synthesis_manager = AsyncSynthesisManager(synthesis_engine, max_concurrent=999)
        await async_synthesis_manager.start()
        logger.info("Async synthesis manager (v2) initialized for unlimited parallel processing")

        # Set dependencies for task-based API (v2)
        from app.dependencies import set_synthesis_engine, set_voice_manager
        set_synthesis_engine(synthesis_engine)
        set_voice_manager(voice_manager)

        # Store v2 in app state
        app.state.voice_manager = voice_manager
        app.state.async_synthesis_manager = async_synthesis_manager

        # ===============================
        # Initialize CosyVoice3 (v3) - Latest
        # ===============================
        logger.info("Initializing CosyVoice3 (v3)...")

        # Auto-download CosyVoice3 model if enabled
        if settings.AUTO_DOWNLOAD_MODELS:
            logger.info("Checking CosyVoice3 model availability...")
            model_ready = ensure_cosyvoice3_model(
                settings.MODEL_DIR_V3,
                settings.COSYVOICE3_HF_REPO,
                auto_download=True
            )
            if model_ready:
                logger.info("CosyVoice3 model is ready")
            else:
                logger.warning("CosyVoice3 model not available - v3 API will be disabled")

        # Initialize CosyVoice3 voice manager
        try:
            voice_manager_v3 = VoiceManagerV3(
                model_dir=settings.MODEL_DIR_V3,
                cache_dir=settings.VOICE_CACHE_DIR
            )
            await voice_manager_v3.initialize()
            logger.info("CosyVoice3 voice manager initialized successfully")

            # Store v3 in app state
            app.state.voice_manager_v3 = voice_manager_v3
        except Exception as e:
            logger.warning(f"CosyVoice3 initialization failed (v3 API disabled): {e}")
            voice_manager_v3 = None

        yield

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        logger.info("Shutting down CosyVoice API server...")
        if async_synthesis_manager:
            await async_synthesis_manager.stop()
        if voice_manager:
            await voice_manager.cleanup()
        if voice_manager_v3:
            await voice_manager_v3.cleanup()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title="CosyVoice API (v2 + v3)",
        description="""
# CosyVoice Cross-lingual Voice Cloning API

This API provides both CosyVoice2 (v2) and CosyVoice3 (v3) endpoints.

## API Versions

- **v1/v2**: CosyVoice2-0.5B (Legacy support)
- **v3**: CosyVoice3-0.5B (Latest - Improved quality, 9+ languages, instruct support)

## CosyVoice3 Features

- 9+ languages: Chinese, English, Japanese, Korean, German, Spanish, French, Italian, Russian
- 18+ Chinese dialects
- Instruction-based voice control (dialect, emotion, speed, volume)
- ~150ms streaming latency
- Better content consistency and speaker similarity
        """,
        version="3.0.0",
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

    # Include API routes - v1 (backward compatibility, same as v2)
    app.include_router(api_router, prefix="/api/v1")

    # Include API routes - v2 (CosyVoice2)
    app.include_router(api_router_v2, prefix="/api/v2")

    # Include API routes - v3 (CosyVoice3)
    app.include_router(api_router_v3, prefix="/api/v3")

    # Mount static files for audio serving
    app.mount("/api/v1/audio", StaticFiles(directory="outputs"), name="audio_v1")
    app.mount("/api/v2/audio", StaticFiles(directory="outputs"), name="audio_v2")
    app.mount("/api/v3/audio", StaticFiles(directory="outputs"), name="audio_v3")

    @app.get("/")
    async def root():
        return {
            "message": "CosyVoice API Server (v2 + v3)",
            "description": "Cross-lingual Voice Cloning with CosyVoice2 and CosyVoice3",
            "version": "3.0.0",
            "docs": "/docs",
            "api_versions": {
                "v1": "CosyVoice2 (backward compatibility)",
                "v2": "CosyVoice2-0.5B (Legacy)",
                "v3": "CosyVoice3-0.5B (Latest - Recommended)"
            },
            "v2_endpoints": {
                "voice_management": "/api/v2/voices/",
                "cross_lingual_with_audio": "/api/v2/cross-lingual/with-audio",
                "cross_lingual_with_cache": "/api/v2/cross-lingual/with-cache",
                "streaming_synthesis": "/api/v2/streaming/cross-lingual",
                "websocket_streaming": "/api/v2/ws/stream"
            },
            "v3_endpoints": {
                "voice_management": "/api/v3/voices/",
                "cross_lingual_with_audio": "/api/v3/cross-lingual/with-audio",
                "cross_lingual_with_cache": "/api/v3/cross-lingual/with-cache",
                "instruct_synthesis": "/api/v3/cross-lingual/instruct",
                "streaming_synthesis": "/api/v3/streaming/cross-lingual",
                "websocket_streaming": "/api/v3/ws/stream",
                "capabilities": "/api/v3/cross-lingual/capabilities"
            },
            "v3_features": [
                "9+ languages support",
                "18+ Chinese dialects",
                "Instruction-based voice control",
                "~150ms streaming latency",
                "Better content consistency",
                "Improved speaker similarity",
                "More natural prosody"
            ]
        }

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        v3_ready = voice_manager_v3 is not None and voice_manager_v3.is_ready() if voice_manager_v3 else False
        return {
            "status": "healthy",
            "v2": {
                "ready": voice_manager is not None and voice_manager.is_ready(),
                "model": "CosyVoice2-0.5B"
            },
            "v3": {
                "ready": v3_ready,
                "model": "CosyVoice3-0.5B" if v3_ready else "Not loaded"
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
