"""
跨语种复刻 API endpoints (Cross-lingual Voice Cloning)
Simplified API focused on cross-lingual voice cloning functionality
"""

import logging
import tempfile
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse

from app.models.synthesis import (
    CrossLingualWithAudioRequest, CrossLingualWithCacheRequest,
    SynthesisResponse, AudioFormat
)
from app.core.voice_manager import VoiceManager
from app.core.synthesis_engine import SynthesisEngine
from app.core.exceptions import (
    SynthesisError, VoiceNotFoundError, ModelNotReadyError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cross-lingual", tags=["跨语种复刻 (Cross-lingual Voice Cloning)"])


def get_voice_manager(request: Request) -> VoiceManager:
    """Dependency to get voice manager from app state"""
    voice_manager = getattr(request.app.state, 'voice_manager', None)
    if not voice_manager:
        raise HTTPException(status_code=503, detail="Voice manager not available")
    if not voice_manager.is_ready():
        raise ModelNotReadyError("Voice manager is not ready")
    return voice_manager


def get_synthesis_engine(voice_manager: VoiceManager = Depends(get_voice_manager)) -> SynthesisEngine:
    """Dependency to get synthesis engine"""
    return SynthesisEngine(voice_manager)


@router.post("/with-audio", response_model=SynthesisResponse)
async def cross_lingual_with_audio(
    text: str = Form(..., description="要合成的文本 (Text to synthesize)"),
    prompt_text: str = Form(..., description="输入prompt文本 (Reference text that matches the prompt audio)"),
    instruct_text: Optional[str] = Form(None, description="输入instruct文本 (Optional instruction for voice style/emotion)"),
    format: AudioFormat = Form(AudioFormat.WAV, description="输出音频格式"),
    speed: float = Form(1.0, description="语速倍数"),
    stream: bool = Form(False, description="是否流式推理 (默认: 否)"),
    prompt_audio: UploadFile = File(..., description="参考音频文件 (Reference audio file)"),
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
):
    """跨语种复刻 - 带音频文件 (Cross-lingual voice cloning with audio file)"""
    
    try:
        # Save uploaded audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            content = await prompt_audio.read()
            temp_file.write(content)
            temp_audio_path = temp_file.name
        
        try:
            # Create request object
            request = CrossLingualWithAudioRequest(
                text=text,
                prompt_text=prompt_text,
                prompt_audio_url=temp_audio_path,
                instruct_text=instruct_text,
                format=format,
                speed=speed,
                stream=stream
            )
            
            result = await synthesis_engine.synthesize_cross_lingual_with_audio(request)
            logger.info(f"跨语种复刻合成完成 (Cross-lingual synthesis with audio completed)")
            return result
            
        finally:
            # Clean up temporary file
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
        logger.error(f"Unexpected error in cross-lingual synthesis with audio: {e}")
        raise HTTPException(status_code=500, detail=f"Cross-lingual synthesis failed: {str(e)}")


@router.post("/with-cache", response_model=SynthesisResponse)
async def cross_lingual_with_cache(
    request: CrossLingualWithCacheRequest,
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
):
    """跨语种复刻 - 使用缓存语音 (Cross-lingual voice cloning with cached voice)"""
    
    try:
        result = await synthesis_engine.synthesize_cross_lingual_with_cache(request)
        logger.info(f"跨语种复刻合成完成 (Cross-lingual synthesis with cache completed) for voice: {request.voice_id}")
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
        logger.error(f"Unexpected error in cross-lingual synthesis with cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cross-lingual synthesis failed: {str(e)}")


# Keep audio serving endpoint
@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve generated audio files"""
    from app.core.file_manager import file_manager
    
    try:
        file_path = file_manager.get_output_audio_path(filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        return FileResponse(
            path=file_path,
            media_type="audio/wav",
            filename=filename
        )
    except Exception as e:
        logger.error(f"Error serving audio file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Error serving audio file")
