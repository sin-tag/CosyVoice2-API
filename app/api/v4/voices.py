"""
Voice management endpoints for Chatterbox TTS (v4)
Supports shared voice cache - can use voices from any TTS engine
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Query, Request

from app.models.voice import (
    VoiceCreate, VoiceUpdate, VoiceResponse, VoiceListResponse,
    VoiceType, AudioFormat
)
from app.core.voice_manager_chatterbox import VoiceManagerChatterbox
from app.core.exceptions import VoiceNotFoundError

router = APIRouter(prefix="/voices", tags=["Chatterbox Voices (v4)"])


def get_voice_manager_chatterbox(request: Request) -> VoiceManagerChatterbox:
    """Get Chatterbox voice manager from app state"""
    if not hasattr(request.app.state, 'voice_manager_chatterbox'):
        raise HTTPException(status_code=503, detail="Chatterbox voice manager not ready")
    return request.app.state.voice_manager_chatterbox


@router.post("/", response_model=VoiceResponse, summary="Create a new voice")
async def create_voice(
    voice_id: str = Form(..., description="Unique voice identifier"),
    name: str = Form(..., description="Human-readable voice name"),
    description: Optional[str] = Form(None, description="Voice description"),
    language: Optional[str] = Form("en", description="Primary language"),
    prompt_text: Optional[str] = Form(None, description="Text matching the audio sample"),
    audio_format: AudioFormat = Form(AudioFormat.WAV, description="Audio format"),
    audio_file: UploadFile = File(..., description="Voice sample audio file"),
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """
    Create a new voice from an audio sample.

    Upload a reference audio file to create a new voice that can be used for synthesis.
    The audio should be clear speech, ideally 3-15 seconds long.
    """
    try:
        audio_content = await audio_file.read()

        voice_create = VoiceCreate(
            voice_id=voice_id,
            name=name,
            description=description,
            voice_type=VoiceType.CROSS_LINGUAL,
            language=language,
            prompt_text=prompt_text,
            audio_format=audio_format
        )

        voice = await voice_manager.add_voice(voice_create, audio_content)

        return VoiceResponse(
            voice_id=voice.voice_id,
            name=voice.name,
            description=voice.description,
            voice_type=voice.voice_type,
            language=voice.language,
            created_at=voice.created_at,
            updated_at=voice.updated_at,
            audio_format=voice.audio_format,
            file_size=voice.file_size,
            duration=voice.duration,
            sample_rate=voice.sample_rate,
            is_active=voice.is_active
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create voice: {str(e)}")


@router.get("/", response_model=VoiceListResponse, summary="List all voices")
async def list_voices(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    language: Optional[str] = Query(None, description="Filter by language"),
    all_engines: bool = Query(False, description="Include voices from all TTS engines"),
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """
    List all voices compatible with Chatterbox.

    By default, shows voices that can be used with Chatterbox (any voice with audio file).
    Set `all_engines=true` to see all voices in the shared cache.

    Chatterbox can use voices created by CosyVoice2, CosyVoice3, or directly uploaded.
    """
    try:
        if all_engines:
            voices, total = await voice_manager.list_all_shared_voices(
                page=page,
                page_size=per_page,
                language=language
            )
        else:
            voices, total = await voice_manager.list_voices(
                page=page,
                page_size=per_page,
                language=language
            )

        return VoiceListResponse(
            voices=[
                VoiceResponse(
                    voice_id=v.voice_id,
                    name=v.name,
                    description=v.description,
                    voice_type=v.voice_type,
                    language=v.language,
                    created_at=v.created_at,
                    updated_at=v.updated_at,
                    audio_format=v.audio_format,
                    file_size=v.file_size,
                    duration=v.duration,
                    sample_rate=v.sample_rate,
                    is_active=v.is_active
                )
                for v in voices
            ],
            total=total,
            page=page,
            per_page=per_page
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(e)}")


@router.get("/{voice_id}", response_model=VoiceResponse, summary="Get voice details")
async def get_voice(
    voice_id: str,
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """Get details of a specific voice."""
    voice = await voice_manager.get_voice(voice_id)

    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")

    return VoiceResponse(
        voice_id=voice.voice_id,
        name=voice.name,
        description=voice.description,
        voice_type=voice.voice_type,
        language=voice.language,
        created_at=voice.created_at,
        updated_at=voice.updated_at,
        audio_format=voice.audio_format,
        file_size=voice.file_size,
        duration=voice.duration,
        sample_rate=voice.sample_rate,
        is_active=voice.is_active
    )


@router.put("/{voice_id}", response_model=VoiceResponse, summary="Update voice")
async def update_voice(
    voice_id: str,
    voice_update: VoiceUpdate,
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """Update a voice's metadata."""
    voice = await voice_manager.update_voice(voice_id, voice_update)

    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")

    return VoiceResponse(
        voice_id=voice.voice_id,
        name=voice.name,
        description=voice.description,
        voice_type=voice.voice_type,
        language=voice.language,
        created_at=voice.created_at,
        updated_at=voice.updated_at,
        audio_format=voice.audio_format,
        file_size=voice.file_size,
        duration=voice.duration,
        sample_rate=voice.sample_rate,
        is_active=voice.is_active
    )


@router.delete("/{voice_id}", summary="Delete voice")
async def delete_voice(
    voice_id: str,
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """Delete a voice from the cache."""
    success = await voice_manager.delete_voice(voice_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")

    return {"message": f"Voice '{voice_id}' deleted successfully"}


@router.get("/languages/supported", summary="Get supported languages")
async def get_supported_languages(
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """
    Get list of supported languages for the loaded Chatterbox model.

    For Chatterbox-Multilingual, supports 30+ languages including:
    - European: English, Spanish, French, German, Italian, Portuguese, Dutch, Polish, etc.
    - Asian: Chinese (Mandarin), Japanese, Korean, Vietnamese, Thai, Indonesian, etc.
    - Middle Eastern: Arabic, Turkish, Hebrew
    - Others: Hindi, Ukrainian, Greek, etc.
    """
    languages = voice_manager.get_supported_languages()
    return {
        "model_type": voice_manager.model_type,
        "total_languages": len(languages),
        "languages": languages,
        "language_codes": list(languages.keys()) if isinstance(languages, dict) else languages
    }


@router.get("/{voice_id}/engines", summary="Get compatible engines for a voice")
async def get_voice_engines(
    voice_id: str,
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """
    Get list of TTS engines compatible with a specific voice.

    Chatterbox can use any voice that has an audio file, regardless of which engine created it.
    """
    voice = await voice_manager.voice_cache.get_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")

    engines = await voice_manager.get_compatible_engines(voice_id)

    return {
        "voice_id": voice_id,
        "compatible_engines": engines,
        "has_audio_file": voice.audio_file_path is not None,
        "note": "Chatterbox can use any voice with an audio file"
    }


@router.get("/shared/stats", summary="Get shared voice cache statistics")
async def get_shared_stats(
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """Get statistics about the shared voice cache."""
    stats = await voice_manager.voice_cache.get_stats()
    chatterbox_stats = await voice_manager.voice_cache.get_stats(engine="chatterbox")

    return {
        "total_voices": stats.total_voices,
        "chatterbox_compatible": chatterbox_stats.total_voices,
        "by_type": stats.by_type,
        "by_language": stats.by_language,
        "total_storage_size_mb": round(stats.total_storage_size / (1024 * 1024), 2) if stats.total_storage_size else 0,
        "average_duration_seconds": round(stats.average_duration, 2) if stats.average_duration else None
    }
