"""
Voice synthesis API endpoints
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse

from app.models.synthesis import (
    SFTSynthesisRequest, ZeroShotSynthesisRequest, 
    CrossLingualSynthesisRequest, InstructSynthesisRequest,
    SynthesisResponse, AudioFormat
)
from app.core.voice_manager import VoiceManager
from app.core.synthesis_engine import SynthesisEngine
from app.core.exceptions import (
    SynthesisError, VoiceNotFoundError, ModelNotReadyError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/synthesize", tags=["Voice Synthesis"])


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


@router.post("/sft", response_model=SynthesisResponse)
async def synthesize_sft(
    request: SFTSynthesisRequest,
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
):
    """Synthesize speech using pre-trained voice (SFT mode)"""
    
    try:
        result = await synthesis_engine.synthesize_sft(request)
        logger.info(f"SFT synthesis completed for voice: {request.voice_id}")
        return result
        
    except VoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in SFT synthesis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/zero-shot", response_model=SynthesisResponse)
async def synthesize_zero_shot(
    text: str = Form(..., description="Text to synthesize"),
    speed: float = Form(1.0, description="Synthesis speed", ge=0.5, le=2.0),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    stream: bool = Form(False, description="Enable streaming synthesis"),
    voice_id: Optional[str] = Form(None, description="Cached voice ID (if using cached voice)"),
    prompt_text: Optional[str] = Form(None, description="Text that matches the prompt audio"),
    prompt_audio: Optional[UploadFile] = File(None, description="Prompt audio file for voice cloning"),
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
):
    """Synthesize speech using zero-shot voice cloning"""
    
    try:
        # Validate inputs
        if not voice_id and not prompt_audio:
            raise HTTPException(
                status_code=400, 
                detail="Either voice_id or prompt_audio must be provided"
            )
        
        if not voice_id and not prompt_text:
            raise HTTPException(
                status_code=400,
                detail="prompt_text is required when using prompt_audio"
            )
        
        # Create request object
        request = ZeroShotSynthesisRequest(
            text=text,
            speed=speed,
            format=format,
            stream=stream,
            voice_id=voice_id,
            prompt_text=prompt_text
        )
        
        # Read prompt audio if provided
        prompt_audio_content = None
        if prompt_audio:
            prompt_audio_content = await prompt_audio.read()
            if len(prompt_audio_content) == 0:
                raise HTTPException(status_code=400, detail="Empty audio file")
        
        result = await synthesis_engine.synthesize_zero_shot(request, prompt_audio_content)
        logger.info(f"Zero-shot synthesis completed")
        return result
        
    except VoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in zero-shot synthesis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cross-lingual", response_model=SynthesisResponse)
async def synthesize_cross_lingual(
    text: str = Form(..., description="Text to synthesize"),
    speed: float = Form(1.0, description="Synthesis speed", ge=0.5, le=2.0),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    stream: bool = Form(False, description="Enable streaming synthesis"),
    voice_id: Optional[str] = Form(None, description="Cached voice ID (if using cached voice)"),
    prompt_audio: Optional[UploadFile] = File(None, description="Prompt audio file for voice cloning"),
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
):
    """Synthesize speech using cross-lingual voice cloning"""
    
    try:
        # Validate inputs
        if not voice_id and not prompt_audio:
            raise HTTPException(
                status_code=400, 
                detail="Either voice_id or prompt_audio must be provided"
            )
        
        # Create request object
        request = CrossLingualSynthesisRequest(
            text=text,
            speed=speed,
            format=format,
            stream=stream,
            voice_id=voice_id
        )
        
        # Read prompt audio if provided
        prompt_audio_content = None
        if prompt_audio:
            prompt_audio_content = await prompt_audio.read()
            if len(prompt_audio_content) == 0:
                raise HTTPException(status_code=400, detail="Empty audio file")
        
        result = await synthesis_engine.synthesize_cross_lingual(request, prompt_audio_content)
        logger.info(f"Cross-lingual synthesis completed")
        return result
        
    except VoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in cross-lingual synthesis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/instruct", response_model=SynthesisResponse)
async def synthesize_instruct(
    request: InstructSynthesisRequest,
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
):
    """Synthesize speech using natural language control (instruct mode)"""
    
    try:
        result = await synthesis_engine.synthesize_instruct(request)
        logger.info(f"Instruct synthesis completed for voice: {request.voice_id}")
        return result
        
    except VoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in instruct synthesis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Audio file serving endpoint
@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve generated audio files"""
    
    try:
        from app.utils.file_utils import file_manager
        file_path = file_manager.get_output_audio_path(filename)
        
        if not file_manager.file_exists(file_path):
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        # Determine media type based on file extension
        file_ext = filename.split('.')[-1].lower()
        media_type_map = {
            'wav': 'audio/wav',
            'mp3': 'audio/mpeg',
            'flac': 'audio/flac',
            'm4a': 'audio/mp4'
        }
        media_type = media_type_map.get(file_ext, 'application/octet-stream')
        
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename
        )
        
    except Exception as e:
        logger.error(f"Error serving audio file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
