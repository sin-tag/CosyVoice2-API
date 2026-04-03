import asyncio
import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.registry import engine_registry
from app.engine.voice_cache import voice_cache
from app.models.generation import GenerationHistory

logger = logging.getLogger(__name__)


async def record_history(
    db: AsyncSession,
    *,
    engine_name: str,
    text: str,
    language: str,
    voice_id: uuid.UUID | str | None,
    parameters: dict,
    status: str,
    latency_ms: int | None = None,
    total_time_ms: int | None = None,
    audio_duration_sec: float | None = None,
    sample_rate: int = 24000,
    error_message: str | None = None,
    audio_path: str | None = None,
) -> GenerationHistory:
    """Record a generation in history."""
    record = GenerationHistory(
        voice_id=str(voice_id) if voice_id else None,
        engine=engine_name,
        text=text,
        language=language,
        parameters=parameters,
        status=status,
        latency_ms=latency_ms,
        total_time_ms=total_time_ms,
        audio_duration_sec=audio_duration_sec,
        sample_rate=sample_rate,
        error_message=error_message,
        audio_path=audio_path,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def generate_speech(
    db: AsyncSession,
    engine_name: str,
    text: str,
    language: str,
    voice_id: uuid.UUID | None = None,
    **params,
) -> tuple[bytes, int, uuid.UUID]:
    """Generate speech synchronously. Returns (wav_bytes, sample_rate, history_id)."""
    import io
    import soundfile as sf
    import numpy as np

    # Use first replica for validation
    meta_engine = engine_registry.get(engine_name)

    from app.core.exceptions import UnsupportedLanguageError
    if not meta_engine.supports_language(language):
        raise UnsupportedLanguageError(language, engine_name, meta_engine.supported_languages)

    # Get voice data from cache (uses first replica)
    voice_data = None
    if voice_id:
        from app.core.exceptions import VoiceNotCompatibleError
        voice_data = await voice_cache.get_or_prepare(voice_id, meta_engine, db)
        if voice_data is None:
            raise VoiceNotCompatibleError(str(voice_id), engine_name)

    # Pick least-busy GPU replica
    engine, semaphore, gpu_idx = engine_registry.pick(engine_name)
    from app.core.config import settings
    start = time.perf_counter()

    try:
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.generation_timeout_sec)
        except asyncio.TimeoutError:
            logger.warning("Semaphore wait timed out for engine '%s' gpu %d — GPU queue full", engine_name, gpu_idx)
            from app.core.exceptions import GenerationTimeoutError
            raise GenerationTimeoutError()

        try:
            logger.debug("Generating on %s gpu %d", engine_name, gpu_idx)
            audio, sr = await asyncio.wait_for(
                engine.generate(text, language, voice_data, **params),
                timeout=settings.generation_timeout_sec,
            )
        finally:
            semaphore.release()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

        total_ms = int((time.perf_counter() - start) * 1000)
        duration_sec = len(audio) / sr

        # Convert to WAV bytes
        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()

        # Save to disk for download via audio_url
        import os
        history_id = str(uuid.uuid4())
        audio_dir = settings.history_storage_path
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, f"{history_id}.wav")
        with open(audio_path, "wb") as f:
            f.write(wav_bytes)

        # Record history
        record = await record_history(
            db,
            engine_name=engine_name,
            text=text,
            language=language,
            voice_id=voice_id,
            parameters=params,
            status="completed",
            total_time_ms=total_ms,
            audio_duration_sec=duration_sec,
            sample_rate=sr,
            audio_path=audio_path,
        )

        return wav_bytes, sr, record.id

    except asyncio.TimeoutError:
        await record_history(
            db, engine_name=engine_name, text=text, language=language, voice_id=voice_id,
            parameters=params, status="failed", error_message="Generation timed out",
        )
        from app.core.exceptions import GenerationTimeoutError
        raise GenerationTimeoutError()

    except Exception as e:
        if "CUDA out of memory" in str(e):
            await record_history(
                db, engine_name=engine_name, text=text, language=language, voice_id=voice_id,
                parameters=params, status="failed", error_message="GPU out of memory",
            )
            from app.core.exceptions import GPUOutOfMemoryError
            raise GPUOutOfMemoryError()
        await record_history(
            db, engine_name=engine_name, text=text, language=language, voice_id=voice_id,
            parameters=params, status="failed", error_message=str(e),
        )
        raise
