import asyncio
import io
import logging
import time
import uuid

import numpy as np
import soundfile as sf
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    EngineNotLoadedError,
    GenerationTimeoutError,
    GPUOutOfMemoryError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from app.engine.registry import engine_registry
from app.models.voice import Voice
from app.modules.tts.service import record_history

logger = logging.getLogger(__name__)


async def generate_comic_audio(
    db: AsyncSession,
    segments: list[dict],
    voice_ids: dict[str, uuid.UUID],
    language: str,
    **params,
) -> tuple[bytes, int, float, uuid.UUID]:
    """Generate comic dubbing audio.

    Returns: (wav_bytes, sample_rate, duration_sec, history_id)
    """
    # Validate engine
    engine, semaphore, gpu_idx = engine_registry.pick("moss")
    meta_engine = engine_registry.get("moss")

    if not meta_engine.supports_language(language):
        raise UnsupportedLanguageError(language, "moss", meta_engine.supported_languages)

    # Resolve voice_id → audio file path for each speaker
    speaker_refs: dict[str, str] = {}
    for speaker_name, vid in voice_ids.items():
        voice = await db.get(Voice, str(vid))
        if voice is None:
            raise VoiceNotFoundError(str(vid))
        speaker_refs[speaker_name] = voice.reference_audio_path

    # Validate all speakers in segments have a voice
    segment_speakers = set(seg["speaker"] for seg in segments)
    missing = segment_speakers - set(voice_ids.keys())
    if missing:
        from app.core.exceptions import AppError
        raise AppError(400, f"Missing voice for speakers: {', '.join(missing)}", error_code="missing_voice")

    if len(segment_speakers) > settings.moss_max_speakers:
        from app.core.exceptions import AppError
        raise AppError(
            400,
            f"Too many speakers: {len(segment_speakers)} (max {settings.moss_max_speakers})",
            error_code="too_many_speakers",
        )

    start = time.perf_counter()

    try:
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.generation_timeout_sec)
        except asyncio.TimeoutError:
            raise GenerationTimeoutError()

        try:
            logger.info("Comic dubbing: %d segments, %d speakers, gpu %d", len(segments), len(segment_speakers), gpu_idx)
            audio, sr = await asyncio.wait_for(
                engine.generate_dialogue(segments, speaker_refs, language, **params),
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

        # Convert to WAV
        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()

        # Record history
        record = await record_history(
            db,
            engine_name="moss",
            text=f"[comic:{len(segments)}seg:{len(segment_speakers)}spk]",
            language=language,
            voice_id=None,
            parameters={"segments": len(segments), "speakers": list(segment_speakers), **params},
            status="completed",
            total_time_ms=total_ms,
            audio_duration_sec=duration_sec,
            sample_rate=sr,
        )

        return wav_bytes, sr, duration_sec, record.id

    except asyncio.TimeoutError:
        await record_history(
            db, engine_name="moss", text=f"[comic:{len(segments)}seg]", language=language,
            voice_id=None, parameters=params, status="failed", error_message="Generation timed out",
        )
        raise GenerationTimeoutError()

    except Exception as e:
        if "CUDA out of memory" in str(e):
            await record_history(
                db, engine_name="moss", text=f"[comic:{len(segments)}seg]", language=language,
                voice_id=None, parameters=params, status="failed", error_message="GPU out of memory",
            )
            raise GPUOutOfMemoryError()
        await record_history(
            db, engine_name="moss", text=f"[comic:{len(segments)}seg]", language=language,
            voice_id=None, parameters=params, status="failed", error_message=str(e),
        )
        raise
