"""
Cross-lingual synthesis API endpoints - v3 (CosyVoice3)
Advanced synthesis with instruct2 support and improved multilingual capabilities
"""

import logging
import tempfile
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse

from app.models.synthesis import (
    CrossLingualWithAudioRequest, CrossLingualWithCacheRequest,
    SynthesisResponse, AudioFormat
)
from app.core.voice_manager_v3 import VoiceManagerV3
from app.core.synthesis_engine_v3 import SynthesisEngineV3
from app.core.exceptions import (
    SynthesisError, VoiceNotFoundError, ModelNotReadyError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cross-lingual", tags=["Cross-lingual Voice Cloning (v3)"])


def get_voice_manager_v3(request: Request) -> VoiceManagerV3:
    """Dependency to get voice manager v3 from app state"""
    voice_manager = getattr(request.app.state, 'voice_manager_v3', None)
    if not voice_manager:
        raise HTTPException(status_code=503, detail="CosyVoice3 voice manager not available")
    if not voice_manager.is_ready():
        raise ModelNotReadyError("CosyVoice3 voice manager is not ready")
    return voice_manager


def get_synthesis_engine_v3(voice_manager: VoiceManagerV3 = Depends(get_voice_manager_v3)) -> SynthesisEngineV3:
    """Dependency to get synthesis engine v3"""
    return SynthesisEngineV3(voice_manager)


@router.post("/with-audio", response_model=SynthesisResponse)
async def cross_lingual_with_audio(
    text: str = Form(..., description="Text to synthesize"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    speed: float = Form(1.0, description="Speech speed multiplier"),
    stream: bool = Form(False, description="Enable streaming inference"),
    instruct_text: Optional[str] = Form(None, description="Instruction for voice control (dialect, emotion, speed, etc.)"),
    prompt_audio: UploadFile = File(..., description="Reference audio file"),
    synthesis_engine: SynthesisEngineV3 = Depends(get_synthesis_engine_v3)
):
    """Cross-lingual voice cloning with audio file (CosyVoice3)

    CosyVoice3 supports:
    - 9+ languages (Chinese, English, Japanese, Korean, German, Spanish, French, Italian, Russian)
    - 18+ Chinese dialects
    - Instruction-based control via instruct_text (dialect, emotion, speed, volume)
    - Chinese Pinyin and English CMU phoneme support

    Example instruct_text:
    - "Use Sichuan dialect"
    - "Speak slowly with a happy tone"
    - "Use formal and professional tone"
    """

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            content = await prompt_audio.read()
            temp_file.write(content)
            temp_audio_path = temp_file.name

        try:
            request = CrossLingualWithAudioRequest(
                text=text,
                prompt_text="",
                prompt_audio_url=temp_audio_path,
                instruct_text=instruct_text or "",
                format=format,
                speed=speed,
                stream=stream
            )

            result = await synthesis_engine.synthesize_cross_lingual_with_audio(request)
            logger.info(f"CosyVoice3 cross-lingual synthesis with audio completed")
            return result

        finally:
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)

    except VoiceNotFoundError as e:
        logger.warning(f"Voice not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        logger.error(f"Model not ready: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in CosyVoice3 cross-lingual synthesis with audio: {e}")
        raise HTTPException(status_code=500, detail=f"CosyVoice3 synthesis failed: {str(e)}")


@router.post("/with-cache", response_model=SynthesisResponse)
async def cross_lingual_with_cache(
    request: CrossLingualWithCacheRequest,
    synthesis_engine: SynthesisEngineV3 = Depends(get_synthesis_engine_v3)
):
    """Cross-lingual voice cloning with cached voice (CosyVoice3)

    Use this endpoint for faster synthesis with previously cached voices.
    Supports all CosyVoice3 features including multilingual and instruct control.
    """

    try:
        result = await synthesis_engine.synthesize_cross_lingual_with_cache(request)
        logger.info(f"CosyVoice3 cross-lingual synthesis with cache completed for voice: {request.voice_id}")
        return result
    except VoiceNotFoundError as e:
        logger.warning(f"Voice not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        logger.error(f"Model not ready: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in CosyVoice3 cross-lingual synthesis with cache: {e}")
        raise HTTPException(status_code=500, detail=f"CosyVoice3 synthesis failed: {str(e)}")


@router.post("/instruct", response_model=SynthesisResponse)
async def instruct_synthesis(
    text: str = Form(..., description="Text to synthesize"),
    instruct_text: str = Form(..., description="Instruction for voice control"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    speed: float = Form(1.0, description="Speech speed multiplier"),
    stream: bool = Form(False, description="Enable streaming inference"),
    prompt_audio: UploadFile = File(..., description="Reference audio file"),
    synthesis_engine: SynthesisEngineV3 = Depends(get_synthesis_engine_v3)
):
    """Instruction-based synthesis (CosyVoice3 instruct2)

    This endpoint uses CosyVoice3's instruct2 feature for fine-grained voice control.

    instruct_text examples:
    - "Speak in Cantonese dialect"
    - "Use a sad and melancholic tone"
    - "Speak quickly with excitement"
    - "Use formal business English"
    - "Whisper softly"

    The instruction is formatted with CosyVoice3's system prompt:
    "You are a helpful assistant.<|endofprompt|>{instruct_text}"
    """

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            content = await prompt_audio.read()
            temp_file.write(content)
            temp_audio_path = temp_file.name

        try:
            request = CrossLingualWithAudioRequest(
                text=text,
                prompt_text="",
                prompt_audio_url=temp_audio_path,
                instruct_text=instruct_text,
                format=format,
                speed=speed,
                stream=stream
            )

            result = await synthesis_engine.synthesize_cross_lingual_with_audio(request)
            logger.info(f"CosyVoice3 instruct synthesis completed")
            return result

        finally:
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)

    except VoiceNotFoundError as e:
        logger.warning(f"Voice not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        logger.error(f"Model not ready: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in CosyVoice3 instruct synthesis: {e}")
        raise HTTPException(status_code=500, detail=f"CosyVoice3 instruct synthesis failed: {str(e)}")


@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve generated audio files"""
    from app.utils.file_utils import file_manager

    try:
        file_path = file_manager.get_output_audio_path(filename)
        logger.info(f"Serving audio file (v3): {filename} -> {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            raise HTTPException(status_code=404, detail=f"Audio file not found: {filename}")

        return FileResponse(
            path=file_path,
            media_type="audio/wav",
            filename=filename
        )
    except Exception as e:
        logger.error(f"Error serving audio file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error serving audio file")


@router.get("/capabilities")
async def get_v3_capabilities():
    """Get CosyVoice3 capabilities and supported features"""
    return {
        "version": "3.0",
        "model": "Fun-CosyVoice3-0.5B-2512",
        "features": {
            "languages": [
                "Chinese (Mandarin)",
                "English",
                "Japanese",
                "Korean",
                "German",
                "Spanish",
                "French",
                "Italian",
                "Russian"
            ],
            "chinese_dialects": [
                "Cantonese",
                "Sichuan",
                "Shanghai",
                "Hokkien",
                "Hakka",
                "And 13+ more..."
            ],
            "instruct_support": True,
            "phoneme_support": {
                "chinese_pinyin": True,
                "english_cmu": True
            },
            "streaming": {
                "enabled": True,
                "latency_ms": 150
            }
        },
        "improvements_over_v2": [
            "Better content consistency",
            "Improved speaker similarity",
            "More natural prosody",
            "Enhanced multilingual support",
            "Lower streaming latency"
        ]
    }
