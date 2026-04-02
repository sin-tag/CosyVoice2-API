import os
import uuid

import aiofiles
import soundfile as sf
from fastapi import APIRouter, Form, Query, UploadFile

from app.core.config import settings
from app.core.dependencies import DB, ApiKey
from app.modules.voices import service
from app.modules.voices.schemas import VoiceCreate, VoiceListResponse, VoiceResponse, VoiceUpdate

router = APIRouter(prefix="/api/v1/voices", tags=["voices"])


def _voice_to_response(voice) -> VoiceResponse:
    return VoiceResponse(
        id=voice.id,
        name=voice.name,
        description=voice.description,
        language=voice.language,
        reference_text=voice.reference_text,
        audio_duration_sec=voice.audio_duration_sec,
        moss_compatible=voice.moss_compatible,
        qwen_compatible=voice.qwen_compatible,
        moss_cached=voice.moss_cached_data is not None,
        qwen_cached=voice.qwen_cached_data is not None,
        is_default=voice.is_default,
        created_at=voice.created_at,
        updated_at=voice.updated_at,
    )


@router.post("", response_model=VoiceResponse, status_code=201)
async def create_voice(
    db: DB,
    _: ApiKey,
    name: str = Form(...),
    language: str = Form(...),
    reference_audio: UploadFile = ...,
    description: str | None = Form(None),
    reference_text: str | None = Form(None),
):
    """Upload reference audio and create a new voice profile."""
    voice_id = uuid.uuid4()
    ext = os.path.splitext(reference_audio.filename or "audio.wav")[1] or ".wav"
    audio_path = f"{settings.voices_storage_path}/{voice_id}{ext}"

    os.makedirs(settings.voices_storage_path, exist_ok=True)
    async with aiofiles.open(audio_path, "wb") as f:
        content = await reference_audio.read()
        await f.write(content)

    # Get audio duration
    info = sf.info(audio_path)
    audio_duration = info.duration

    if audio_duration < settings.min_reference_audio_duration_sec:
        os.remove(audio_path)
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"Audio too short: {audio_duration:.1f}s (minimum {settings.min_reference_audio_duration_sec}s)",
        )

    if audio_duration > settings.max_reference_audio_duration_sec:
        os.remove(audio_path)
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"Audio too long: {audio_duration:.1f}s (maximum {settings.max_reference_audio_duration_sec}s)",
        )

    data = VoiceCreate(name=name, description=description, language=language, reference_text=reference_text)
    voice = await service.create_voice(db, data, audio_path, audio_duration)
    return _voice_to_response(voice)


@router.get("", response_model=VoiceListResponse)
async def list_voices(
    db: DB,
    _: ApiKey,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    language: str | None = None,
    engine: str | None = None,
):
    """List all voices with pagination and filtering."""
    voices, total = await service.list_voices(db, page, page_size, language, engine)
    return VoiceListResponse(
        items=[_voice_to_response(v) for v in voices],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{voice_id}", response_model=VoiceResponse)
async def get_voice(db: DB, _: ApiKey, voice_id: uuid.UUID):
    voice = await service.get_voice(db, voice_id)
    return _voice_to_response(voice)


@router.put("/{voice_id}", response_model=VoiceResponse)
async def update_voice(db: DB, _: ApiKey, voice_id: uuid.UUID, data: VoiceUpdate):
    voice = await service.update_voice(db, voice_id, data)
    return _voice_to_response(voice)


@router.delete("/{voice_id}", status_code=204)
async def delete_voice(db: DB, _: ApiKey, voice_id: uuid.UUID):
    await service.delete_voice(db, voice_id)
