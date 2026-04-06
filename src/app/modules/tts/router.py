import asyncio
import base64
import json
import logging
import time

import numpy as np
from fastapi import APIRouter
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.dependencies import DB, ApiKey
from app.core.exceptions import UnsupportedLanguageError, VoiceNotCompatibleError
from app.engine.registry import engine_registry
from app.engine.voice_cache import voice_cache
from app.modules.tts import service
from app.modules.tts.schemas import (
    EngineInfoResponse,
    LanguageListResponse,
    SynthesisResponse,
    TTSGenerateRequest,
    TTSStreamRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


def _audio_to_pcm16(audio: np.ndarray) -> bytes:
    """Convert float32 audio to PCM16 bytes."""
    audio_clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (audio_clipped * 32767).astype(np.int16)
    return pcm16.tobytes()


# ──── Engine Info ────


@router.get("/engines", response_model=list[EngineInfoResponse])
async def list_engines(_: ApiKey):
    return engine_registry.list_engines()


@router.get("/xtts/languages", response_model=LanguageListResponse)
@router.get("/omni/languages", response_model=LanguageListResponse, include_in_schema=False)
async def xtts_languages(_: ApiKey):
    engine = engine_registry.get("xtts")
    return LanguageListResponse(engine="xtts", languages=engine.supported_languages)


# ──── Sync Generate ────


async def _generate(engine_name: str, body: TTSGenerateRequest, db):
    """Shared generate logic — returns SynthesisResponse + wav bytes."""
    start = time.perf_counter()
    wav_bytes, sr, history_id = await service.generate_speech(
        db, engine_name, body.text, body.language, body.voice_id,
        speed=body.speed, temperature=body.temperature, top_p=body.top_p, top_k=body.top_k,
        repetition_penalty=body.repetition_penalty,
    )
    synthesis_time = round(time.perf_counter() - start, 3)

    # Audio duration from WAV size: wav_bytes includes header, but we can compute from samples
    import struct
    # PCM16 mono: 2 bytes per sample, WAV header is 44 bytes
    num_samples = (len(wav_bytes) - 44) // 2
    duration = round(num_samples / sr, 2) if sr > 0 else 0

    slots = engine_registry.gpu_slots(engine_name)

    return wav_bytes, sr, SynthesisResponse(
        success=True,
        message="Synthesis completed",
        audio_url=f"/api/v1/tts/audio/{history_id}",
        duration=duration,
        format=body.output_format,
        synthesis_time=synthesis_time,
        sample_rate=sr,
        history_id=str(history_id),
        gpu_slots_free=slots["free"],
        gpu_slots_total=slots["total"],
    )


@router.post("/xtts/generate", response_model=SynthesisResponse)
@router.post("/omni/generate", response_model=SynthesisResponse, include_in_schema=False)
async def generate_xtts(body: TTSGenerateRequest, db: DB, _: ApiKey):
    wav_bytes, sr, resp = await _generate("xtts", body, db)
    return resp


@router.post("/xtts/generate/audio")
@router.post("/omni/generate/audio", include_in_schema=False)
async def generate_xtts_audio(body: TTSGenerateRequest, db: DB, _: ApiKey):
    """Return raw WAV audio bytes (for direct playback)."""
    wav_bytes, sr, resp = await _generate("xtts", body, db)
    return Response(
        content=wav_bytes,
        media_type="audio/mpeg",
        headers={
            "X-History-Id": resp.history_id or "",
            "X-Sample-Rate": str(sr),
            "X-GPU-Slots-Free": str(resp.gpu_slots_free),
            "X-GPU-Slots-Total": str(resp.gpu_slots_total),
        },
    )


@router.api_route("/audio/{history_id}", methods=["GET", "HEAD"])
async def download_audio(db: DB, history_id: str):
    """Download previously generated TTS audio by history_id. No auth required."""
    import os
    import aiofiles
    from app.core.exceptions import AppError
    from app.models.generation import GenerationHistory

    record = await db.get(GenerationHistory, history_id)
    if record is None or not record.audio_path:
        raise AppError(404, f"Audio not found for '{history_id}'", error_code="audio_not_found")
    if not os.path.exists(record.audio_path):
        raise AppError(404, "Audio file missing from disk", error_code="audio_not_found")

    async with aiofiles.open(record.audio_path, "rb") as f:
        content = await f.read()

    return Response(
        content=content,
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(len(content)),
            "X-History-Id": history_id,
            "X-Sample-Rate": str(record.sample_rate or 24000),
        },
    )


# ──── SSE Stream ────


async def _stream_tts(engine_name: str, body: TTSStreamRequest, db):
    """SSE streaming for TTS generation.

    Events (aligned with chatterbox):
      - synthesis_start: {text, voice_id, language, sample_rate}
      - audio_chunk:     base64 PCM16 data + metadata
      - synthesis_complete: {history_id, duration, synthesis_time, gpu_slots_free}
      - error:           {error, message}
    """
    meta_engine = engine_registry.get(engine_name)

    if not meta_engine.supports_language(body.language):
        raise UnsupportedLanguageError(body.language, engine_name, meta_engine.supported_languages)

    voice_data = None
    if body.voice_id:
        voice_data = await voice_cache.get_or_prepare(body.voice_id, meta_engine, db)
        if voice_data is None:
            raise VoiceNotCompatibleError(str(body.voice_id), engine_name)

    params = body.generation_params()
    # Pick least-busy GPU for streaming
    engine, semaphore, gpu_idx = engine_registry.pick(engine_name)

    async def event_generator():
        start = time.perf_counter()
        chunk_index = 0
        total_samples = 0
        sr = 24000
        latency_ms = 0

        try:
            try:
                await asyncio.wait_for(semaphore.acquire(), timeout=settings.generation_timeout_sec)
            except asyncio.TimeoutError:
                logger.warning("Stream semaphore wait timed out for engine '%s'", engine_name)
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "gpu_queue_full", "message": "GPU queue full — try again later"}),
                }
                return

            # synthesis_start event
            yield {
                "event": "synthesis_start",
                "data": json.dumps({
                    "text": body.text[:100],
                    "voice_id": str(body.voice_id) if body.voice_id else None,
                    "language": body.language,
                    "sample_rate": sr,
                }),
            }

            try:
                async for chunk in engine.stream_generate(body.text, body.language, voice_data, **params):
                    pcm_bytes = _audio_to_pcm16(chunk)
                    total_samples += len(chunk)

                    if chunk_index == 0:
                        latency_ms = int((time.perf_counter() - start) * 1000)

                    yield {
                        "event": "audio_chunk",
                        "data": json.dumps({
                            "audio_data": base64.b64encode(pcm_bytes).decode(),
                            "chunk_index": chunk_index,
                            "chunk_size": len(pcm_bytes),
                            "sample_rate": sr,
                            "is_final": False,
                        }),
                    }
                    chunk_index += 1
            finally:
                semaphore.release()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass

            total_ms = int((time.perf_counter() - start) * 1000)
            duration_sec = total_samples / sr if sr > 0 else 0

            record = await service.record_history(
                db,
                engine_name=engine_name,
                text=body.text,
                language=body.language,
                voice_id=body.voice_id,
                parameters=params,
                status="completed",
                latency_ms=latency_ms if chunk_index > 0 else None,
                total_time_ms=total_ms,
                audio_duration_sec=duration_sec,
                sample_rate=sr,
            )

            slots = engine_registry.gpu_slots(engine_name)
            yield {
                "event": "synthesis_complete",
                "data": json.dumps({
                    "history_id": str(record.id),
                    "total_chunks": chunk_index,
                    "duration": round(duration_sec, 2),
                    "synthesis_time": round(total_ms / 1000, 3),
                    "latency_ms": latency_ms,
                    "gpu_slots_free": slots["free"],
                    "gpu_slots_total": slots["total"],
                }),
            }

        except Exception as e:
            logger.error("Stream error for engine '%s': %s", engine_name, e, exc_info=True)
            await service.record_history(
                db,
                engine_name=engine_name,
                text=body.text,
                language=body.language,
                voice_id=body.voice_id,
                parameters=params,
                status="failed",
                error_message=str(e),
            )
            yield {
                "event": "error",
                "data": json.dumps({"error": "synthesis_error", "message": "Internal server error"}),
            }

    return EventSourceResponse(event_generator())


@router.post("/xtts/stream")
@router.post("/omni/stream", include_in_schema=False)
async def stream_xtts(body: TTSStreamRequest, db: DB, _: ApiKey):
    return await _stream_tts("xtts", body, db)
