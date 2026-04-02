import logging
import os
import uuid

import soundfile as sf
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import VoiceNotFoundError
from app.engine.registry import engine_registry
from app.engine.voice_cache import voice_cache
from app.models.voice import Voice
from app.modules.voices.schemas import VoiceCreate, VoiceUpdate

logger = logging.getLogger(__name__)

MIN_QWEN_DURATION = 3.0


async def create_voice(db: AsyncSession, data: VoiceCreate, audio_path: str, audio_duration: float) -> Voice:
    """Create a new voice profile and pre-compute engine caches."""
    voice_id = str(uuid.uuid4())

    # Determine engine compatibility
    qwen_compatible = audio_duration >= MIN_QWEN_DURATION

    voice = Voice(
        id=voice_id,
        name=data.name,
        description=data.description,
        language=data.language,
        reference_audio_path=audio_path,
        reference_text=data.reference_text,
        audio_duration_sec=audio_duration,
        moss_compatible=True,
        qwen_compatible=qwen_compatible,
    )
    db.add(voice)
    await db.flush()

    # Pre-compute and cache voice embeddings for each available engine
    for engine_name in engine_registry.available_engines:
        try:
            engine = engine_registry.get(engine_name)

            if engine_name == "qwen" and not qwen_compatible:
                continue

            voice_data = await engine.prepare_voice(audio_path, data.reference_text)

            cache_file = f"{settings.voices_storage_path}/{voice_id}_{engine_name}.pt"
            await engine.save_voice_cache(voice_data, cache_file)

            if engine_name == "moss":
                voice.moss_cached_data = cache_file
            else:
                voice.qwen_cached_data = cache_file

            voice_cache.add(voice_id, engine_name, voice_data)
            logger.info("Cached voice %s for engine '%s'", voice_id, engine_name)
        except Exception:
            logger.warning("Failed to cache voice %s for engine '%s'", voice_id, engine_name, exc_info=True)

    await db.commit()
    await db.refresh(voice)
    return voice


async def list_voices(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    language: str | None = None,
    engine: str | None = None,
) -> tuple[list[Voice], int]:
    """List voices with pagination and filtering."""
    query = select(Voice)

    if language:
        query = query.where(Voice.language == language)
    if engine == "moss":
        query = query.where(Voice.moss_compatible.is_(True))
    elif engine == "qwen":
        query = query.where(Voice.qwen_compatible.is_(True))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(Voice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    voices = list(result.scalars().all())

    return voices, total


async def get_voice(db: AsyncSession, voice_id: uuid.UUID) -> Voice:
    voice = await db.get(Voice, str(voice_id))
    if voice is None:
        raise VoiceNotFoundError(str(voice_id))
    return voice


async def update_voice(db: AsyncSession, voice_id: uuid.UUID, data: VoiceUpdate) -> Voice:
    voice = await get_voice(db, voice_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(voice, field, value)

    await db.commit()
    await db.refresh(voice)
    return voice


async def delete_voice(db: AsyncSession, voice_id: uuid.UUID) -> None:
    voice = await get_voice(db, voice_id)

    # Remove from cache
    voice_cache.remove(voice_id)

    # Cleanup files
    for path in [voice.reference_audio_path, voice.moss_cached_data, voice.qwen_cached_data]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                logger.warning("Failed to delete file: %s", path)

    await db.delete(voice)
    await db.commit()
