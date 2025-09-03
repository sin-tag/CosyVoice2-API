"""
Voice management API endpoints
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import JSONResponse

from app.models.voice import (
    VoiceCreate, VoiceUpdate, VoiceResponse, VoiceListResponse, 
    VoiceStats, VoiceType, AudioFormat
)
from app.core.voice_manager import VoiceManager
from app.core.exceptions import (
    VoiceNotFoundError, VoiceAlreadyExistsError, 
    AudioProcessingError, ModelNotReadyError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voices", tags=["Voice Management"])


def get_voice_manager(request: Request) -> VoiceManager:
    """Dependency to get voice manager from app state"""
    voice_manager = getattr(request.app.state, 'voice_manager', None)
    if not voice_manager:
        raise HTTPException(status_code=503, detail="Voice manager not available")
    if not voice_manager.is_ready():
        raise ModelNotReadyError("Voice manager is not ready")
    return voice_manager


@router.post("/", response_model=VoiceResponse, status_code=201)
async def create_voice(
    voice_id: str = Form(..., description="Unique voice identifier"),
    name: str = Form(..., description="Human-readable voice name"),
    description: Optional[str] = Form(None, description="Voice description"),
    voice_type: VoiceType = Form(..., description="Type of voice"),
    language: Optional[str] = Form(None, description="Primary language of the voice"),
    prompt_text: Optional[str] = Form(None, description="Text that matches the audio sample"),
    audio_format: AudioFormat = Form(AudioFormat.WAV, description="Audio file format"),
    audio_file: UploadFile = File(..., description="Audio file for voice cloning"),
    voice_manager: VoiceManager = Depends(get_voice_manager)
):
    """Create a new voice in the cache"""
    
    try:
        # Validate file format
        if not audio_file.filename:
            raise HTTPException(status_code=400, detail="No audio file provided")
        
        file_ext = audio_file.filename.split('.')[-1].lower()
        if file_ext not in ['wav', 'mp3', 'flac', 'm4a']:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported audio format: {file_ext}"
            )
        
        # Read file content
        audio_content = await audio_file.read()
        if len(audio_content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")
        
        # Create voice object
        voice_create = VoiceCreate(
            voice_id=voice_id,
            name=name,
            description=description,
            voice_type=voice_type,
            language=language,
            prompt_text=prompt_text,
            audio_format=audio_format
        )
        
        # Add voice to manager
        voice = await voice_manager.add_voice(voice_create, audio_content)
        
        logger.info(f"Created voice: {voice_id}")
        return VoiceResponse(**voice.dict())
        
    except VoiceAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except AudioProcessingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating voice {voice_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=VoiceListResponse)
async def list_voices(
    voice_type: Optional[VoiceType] = Query(None, description="Filter by voice type"),
    language: Optional[str] = Query(None, description="Filter by language"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    voice_manager: VoiceManager = Depends(get_voice_manager)
):
    """List all voices with optional filtering and pagination"""
    
    try:
        voices, total = await voice_manager.list_voices(
            voice_type=voice_type,
            language=language,
            page=page,
            page_size=page_size
        )
        
        return VoiceListResponse(
            voices=[VoiceResponse(**voice.dict()) for voice in voices],
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing voices: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{voice_id}", response_model=VoiceResponse)
async def get_voice(
    voice_id: str,
    voice_manager: VoiceManager = Depends(get_voice_manager)
):
    """Get a specific voice by ID"""
    
    try:
        voice = await voice_manager.get_voice(voice_id)
        if not voice:
            raise VoiceNotFoundError(f"Voice with ID '{voice_id}' not found")
        
        return VoiceResponse(**voice.dict())
        
    except VoiceNotFoundError:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")
    except Exception as e:
        logger.error(f"Error getting voice {voice_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{voice_id}", response_model=VoiceResponse)
async def update_voice(
    voice_id: str,
    voice_update: VoiceUpdate,
    voice_manager: VoiceManager = Depends(get_voice_manager)
):
    """Update a voice's information"""
    
    try:
        voice = await voice_manager.update_voice(voice_id, voice_update)
        if not voice:
            raise VoiceNotFoundError(f"Voice with ID '{voice_id}' not found")
        
        logger.info(f"Updated voice: {voice_id}")
        return VoiceResponse(**voice.dict())
        
    except VoiceNotFoundError:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")
    except Exception as e:
        logger.error(f"Error updating voice {voice_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{voice_id}")
async def delete_voice(
    voice_id: str,
    voice_manager: VoiceManager = Depends(get_voice_manager)
):
    """Delete a voice from the cache"""
    
    try:
        success = await voice_manager.delete_voice(voice_id)
        if not success:
            raise VoiceNotFoundError(f"Voice with ID '{voice_id}' not found")
        
        logger.info(f"Deleted voice: {voice_id}")
        return {"message": f"Voice '{voice_id}' deleted successfully"}
        
    except VoiceNotFoundError:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")
    except Exception as e:
        logger.error(f"Error deleting voice {voice_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/summary", response_model=VoiceStats)
async def get_voice_stats(
    voice_manager: VoiceManager = Depends(get_voice_manager)
):
    """Get voice cache statistics"""
    
    try:
        stats = await voice_manager.voice_cache.get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting voice stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pretrained/list")
async def list_pretrained_voices(
    voice_manager: VoiceManager = Depends(get_voice_manager)
):
    """Get list of available pre-trained voices"""
    
    try:
        voices = await voice_manager.get_available_pretrained_voices()
        return {
            "pretrained_voices": voices,
            "total": len(voices)
        }
        
    except Exception as e:
        logger.error(f"Error listing pre-trained voices: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
