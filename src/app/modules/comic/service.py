import asyncio
import io
import logging
import time

import soundfile as sf
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import GenerationTimeoutError, GPUOutOfMemoryError, UnsupportedLanguageError
from app.engine.registry import engine_registry
from app.modules.tts.service import record_history

logger = logging.getLogger(__name__)


async def generate_comic_audio(
    db: AsyncSession,
    segments: list[dict],
    speaker_refs: dict[str, str],
    language: str,
    **params,
) -> tuple[bytes, int, float, str]:
    """Generate comic dubbing: run each segment with Qwen voice clone, concatenate.

    Args:
        segments: [{"speaker": "narrator", "text": "..."}, ...]
        speaker_refs: {"narrator": "/tmp/narrator.wav", ...}

    Returns: (wav_bytes, sample_rate, duration_sec, history_id)
    """
    engine, semaphore, gpu_idx = engine_registry.pick("qwen")
    meta_engine = engine_registry.get("qwen")

    if not meta_engine.supports_language(language):
        raise UnsupportedLanguageError(language, "qwen", meta_engine.supported_languages)

    segment_speakers = set(seg["speaker"] for seg in segments)
    start = time.perf_counter()

    try:
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.generation_timeout_sec)
        except asyncio.TimeoutError:
            raise GenerationTimeoutError()

        try:
            logger.info("Comic dubbing (qwen): %d segments, %d speakers, gpu %d", len(segments), len(segment_speakers), gpu_idx)
            audio, sr = await asyncio.wait_for(
                engine.generate_dialogue(segments, speaker_refs, language, **params),
                timeout=settings.generation_timeout_sec * len(segments),
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

        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()

        record = await record_history(
            db,
            engine_name="qwen",
            text=f"[comic:{len(segments)}seg:{len(segment_speakers)}spk]",
            language=language,
            voice_id=None,
            parameters={"segments": len(segments), "speakers": list(segment_speakers)},
            status="completed",
            total_time_ms=total_ms,
            audio_duration_sec=duration_sec,
            sample_rate=sr,
        )

        return wav_bytes, sr, duration_sec, record.id

    except asyncio.TimeoutError:
        await record_history(
            db, engine_name="qwen", text=f"[comic:{len(segments)}seg]", language=language,
            voice_id=None, parameters={}, status="failed", error_message="Generation timed out",
        )
        raise GenerationTimeoutError()

    except Exception as e:
        if "CUDA out of memory" in str(e):
            await record_history(
                db, engine_name="qwen", text=f"[comic:{len(segments)}seg]", language=language,
                voice_id=None, parameters={}, status="failed", error_message="GPU out of memory",
            )
            raise GPUOutOfMemoryError()
        await record_history(
            db, engine_name="qwen", text=f"[comic:{len(segments)}seg]", language=language,
            voice_id=None, parameters={}, status="failed", error_message=str(e),
        )
        raise
