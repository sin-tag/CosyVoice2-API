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

def install_dependencies():
    """Install required dependencies"""
    print("🔄 Installing dependencies...")

    # Check Python version
    if sys.version_info < (3, 10):
        print(f"⚠️  Python {sys.version_info.major}.{sys.version_info.minor} detected. Python 3.10+ recommended.")

    # Core dependencies that must be installed
    core_deps = [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-multipart>=0.0.6",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "transformers>=4.37.0",
        "torch>=2.0.0",
        "torchaudio>=2.0.0",
        "librosa>=0.10.0",
        "soundfile>=0.12.0",
        "numpy<2",  # Use compatible numpy version
        "scipy>=1.11.0",
        "openai-whisper>=20231117",
        "modelscope>=1.9.0",
        "hyperpyyaml>=1.2.0",
        "onnxruntime>=1.16.0",
        "pypinyin>=0.50.0",
        "jieba>=0.42.0",
        "aiofiles>=23.0.0"
    ]

    # Optional dependencies that may fail
    optional_deps = [
        "WeTextProcessing>=1.0.3",
        "pynini",
        "openfst-python"
    ]

    # Install core dependencies
    for dep in core_deps:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print(f"⚠️  Failed to install {dep}")

    # Install optional dependencies (don't fail if they don't work)
    for dep in optional_deps:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print(f"⚠️  Failed to install {dep}")

    print("✓ Dependencies installation completed")

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
print("🚀 CosyVoice2 API - Auto Setup")
setup_cosyvoice()
install_dependencies()
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

from app.core.config import settings
from app.core.voice_manager import VoiceManager
from app.core.synthesis_engine import SynthesisEngine
from app.core.async_synthesis_manager import AsyncSynthesisManager
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

        # Initialize async synthesis manager
        logger.info("Initializing async synthesis manager...")
        synthesis_engine = SynthesisEngine(voice_manager)
        async_synthesis_manager = AsyncSynthesisManager(synthesis_engine, max_concurrent=4)
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
        title="CosyVoice2 跨语种复刻 API",
        description="跨语种复刻 API - Cross-lingual Voice Cloning with CosyVoice2-0.5B",
        version="2.0.0",
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
            "message": "CosyVoice2 跨语种复刻 API Server",
            "description": "Cross-lingual Voice Cloning with CosyVoice2-0.5B",
            "version": "2.0.0",
            "docs": "/docs",
            "endpoints": {
                "voice_management": "/api/v1/voices/",
                "cross_lingual_with_audio": "/api/v1/cross-lingual/with-audio",
                "cross_lingual_with_cache": "/api/v1/cross-lingual/with-cache"
            }
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "voice_manager_ready": voice_manager is not None and voice_manager.is_ready(),
            "api_mode": "跨语种复刻 (Cross-lingual Voice Cloning)"
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
