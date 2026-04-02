import asyncio
import base64
import json
import logging
import struct
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


@router.get("/moss/languages", response_model=LanguageListResponse)
async def moss_languages(_: ApiKey):
    engine = engine_registry.get("moss")
    return LanguageListResponse(engine="moss", languages=engine.supported_languages)


@router.get("/qwen/languages", response_model=LanguageListResponse)
async def qwen_languages(_: ApiKey):
    engine = engine_registry.get("qwen")
    return LanguageListResponse(engine="qwen", languages=engine.supported_languages)


# ──── Sync Generate ────


def _slot_headers(engine_name: str) -> dict[str, str]:
    """Return GPU slot info as response headers."""
    slots = engine_registry.gpu_slots(engine_name)
    return {
        "X-GPU-Slots-Free": str(slots["free"]),
        "X-GPU-Slots-Total": str(slots["total"]),
        "X-GPU-Slots-Busy": str(slots["busy"]),
    }


@router.post("/moss/generate")
async def generate_moss(body: TTSGenerateRequest, db: DB, _: ApiKey):
    wav_bytes, sr, history_id = await service.generate_speech(
        db, "moss", body.text, body.language, body.voice_id,
        temperature=body.temperature, top_p=body.top_p, top_k=body.top_k,
        repetition_penalty=body.repetition_penalty,
    )
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"X-History-Id": str(history_id), "X-Sample-Rate": str(sr), **_slot_headers("moss")},
    )


@router.post("/qwen/generate")
async def generate_qwen(body: TTSGenerateRequest, db: DB, _: ApiKey):
    wav_bytes, sr, history_id = await service.generate_speech(
        db, "qwen", body.text, body.language, body.voice_id,
        temperature=body.temperature, top_p=body.top_p, top_k=body.top_k,
        repetition_penalty=body.repetition_penalty,
    )
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"X-History-Id": str(history_id), "X-Sample-Rate": str(sr), **_slot_headers("qwen")},
    )


# ──── SSE Stream ────


async def _stream_tts(engine_name: str, body: TTSStreamRequest, db):
    """SSE streaming for TTS generation."""
    engine = engine_registry.get(engine_name)

    if not engine.supports_language(body.language):
        raise UnsupportedLanguageError(body.language, engine_name, engine.supported_languages)

    voice_data = None
    if body.voice_id:
        voice_data = await voice_cache.get_or_prepare(body.voice_id, engine, db)
        if voice_data is None:
            raise VoiceNotCompatibleError(str(body.voice_id), engine_name)

    params = body.generation_params()
    semaphore = engine_registry.get_semaphore(engine_name)

    async def event_generator():
        start = time.perf_counter()
        first_chunk = True
        total_samples = 0
        sr = 24000
        latency_ms = 0

        try:
            # Wait for semaphore with timeout so users don't queue forever
            try:
                await asyncio.wait_for(semaphore.acquire(), timeout=settings.generation_timeout_sec)
            except asyncio.TimeoutError:
                logger.warning("Stream semaphore wait timed out for engine '%s'", engine_name)
                yield {
                    "event": "error",
                    "data": json.dumps({"message": "GPU queue full — try again later"}),
                }
                return

            try:
                async for chunk in engine.stream_generate(body.text, body.language, voice_data, **params):
                    pcm_bytes = _audio_to_pcm16(chunk)
                    total_samples += len(chunk)

                    if first_chunk:
                        latency_ms = int((time.perf_counter() - start) * 1000)
                        slots = engine_registry.gpu_slots(engine_name)
                        yield {
                            "event": "metadata",
                            "data": json.dumps({
                                "sample_rate": sr,
                                "latency_ms": latency_ms,
                                "gpu_slots_free": slots["free"],
                                "gpu_slots_total": slots["total"],
                            }),
                        }
                        first_chunk = False

                    yield {
                        "event": "audio",
                        "data": base64.b64encode(pcm_bytes).decode(),
                    }
            finally:
                semaphore.release()
                # Free fragmented GPU memory after streaming
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass

            total_ms = int((time.perf_counter() - start) * 1000)
            duration_sec = total_samples / sr if sr > 0 else 0

            # Record history after semaphore is released
            record = await service.record_history(
                db,
                engine_name=engine_name,
                text=body.text,
                language=body.language,
                voice_id=body.voice_id,
                parameters=params,
                status="completed",
                latency_ms=latency_ms if not first_chunk else None,
                total_time_ms=total_ms,
                audio_duration_sec=duration_sec,
                sample_rate=sr,
            )

            done_slots = engine_registry.gpu_slots(engine_name)
            yield {
                "event": "done",
                "data": json.dumps({
                    "total_time_ms": total_ms,
                    "audio_duration_sec": round(duration_sec, 2),
                    "history_id": str(record.id),
                    "gpu_slots_free": done_slots["free"],
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
                "data": json.dumps({"message": "Internal server error"}),
            }

    return EventSourceResponse(event_generator())


@router.post("/moss/stream")
async def stream_moss(body: TTSStreamRequest, db: DB, _: ApiKey):
    return await _stream_tts("moss", body, db)


@router.post("/qwen/stream")
async def stream_qwen(body: TTSStreamRequest, db: DB, _: ApiKey):
    return await _stream_tts("qwen", body, db)
