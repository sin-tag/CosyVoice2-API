import asyncio
import base64
import json
import logging
import threading
import time
import uuid

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.database import async_session_factory
from app.engine.registry import engine_registry
from app.engine.voice_cache import voice_cache

logger = logging.getLogger(__name__)
router = APIRouter()


def _audio_to_pcm16_bytes(audio: np.ndarray) -> bytes:
    """Convert float32 audio to PCM16 little-endian bytes."""
    audio_clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (audio_clipped * 32767).astype(np.int16)
    return pcm16.tobytes()


@router.websocket("/ws/tts/{engine_name}")
async def websocket_tts(ws: WebSocket, engine_name: str):
    """WebSocket TTS streaming — aligned with chatterbox message types.

    Message types (server → client):
      - synthesis_start:    Confirms synthesis has begun
      - audio_chunk:        Binary PCM16 frame + JSON metadata
      - synthesis_complete: Summary when done
      - error:              Error with code + message
      - status:             Status updates (e.g. queued)

    Message types (client → server):
      - text_request:  {"message_type": "text_request", "text": "...", ...}
      - stop:          {"message_type": "stop"}
      - ping:          {"message_type": "ping"}
    """
    await ws.accept()

    # Verify API key from query params
    api_key = ws.query_params.get("api_key")
    if api_key != settings.api_key:
        await ws.send_json({
            "message_type": "error",
            "error_code": "auth_failed",
            "error_message": "Invalid API key",
        })
        await ws.close(code=4001)
        return

    try:
        # Wait for config message
        config_raw = await ws.receive_text()
        config = json.loads(config_raw)

        text = config.get("text", "")
        language = config.get("language", "en")
        voice_id_str = config.get("voice_id")
        voice_id = uuid.UUID(voice_id_str) if voice_id_str else None
        request_id = config.get("request_id", str(uuid.uuid4())[:12])
        params = {
            "temperature": config.get("temperature", 0.7),
            "top_p": config.get("top_p", 0.9),
            "top_k": config.get("top_k", 50),
            "repetition_penalty": config.get("repetition_penalty", 1.2),
        }

        if not text:
            await ws.send_json({
                "message_type": "error",
                "request_id": request_id,
                "error_code": "validation_error",
                "error_message": "Text is required",
            })
            await ws.close()
            return

        # Alias: omni → xtts for backward compat
        resolved_engine = "xtts" if engine_name == "omni" else engine_name
        meta_engine = engine_registry.get(resolved_engine)

        if not meta_engine.supports_language(language):
            await ws.send_json({
                "message_type": "error",
                "request_id": request_id,
                "error_code": "unsupported_language",
                "error_message": f"Language '{language}' not supported. Supported: {meta_engine.supported_languages}",
            })
            await ws.close()
            return

        # Resolve voice
        voice_data = None
        if voice_id:
            async with async_session_factory() as db:
                voice_data = await voice_cache.get_or_prepare(voice_id, meta_engine, db)
            if voice_data is None:
                await ws.send_json({
                    "message_type": "error",
                    "request_id": request_id,
                    "error_code": "voice_not_compatible",
                    "error_message": f"Voice '{voice_id}' not found or not compatible",
                })
                await ws.close()
                return

        # Pick least-busy GPU replica
        engine, semaphore, gpu_idx = engine_registry.pick(resolved_engine)
        stop_event = threading.Event()

        start = time.perf_counter()
        chunk_index = 0
        latency_ms = 0
        total_samples = 0
        sr = 24000

        # Wait for semaphore with timeout
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.generation_timeout_sec)
        except asyncio.TimeoutError:
            await ws.send_json({
                "message_type": "error",
                "request_id": request_id,
                "error_code": "gpu_queue_full",
                "error_message": "GPU queue full — try again later",
            })
            await ws.close()
            return

        # synthesis_start
        await ws.send_json({
            "message_type": "synthesis_start",
            "request_id": request_id,
            "text": text[:100],
            "voice_id": str(voice_id) if voice_id else None,
            "language": language,
            "sample_rate": sr,
            "timestamp": time.time(),
        })

        try:
            try:
                async for chunk in engine.stream_generate(text, language, voice_data, **params):
                    if stop_event.is_set():
                        break

                    pcm_bytes = _audio_to_pcm16_bytes(chunk)
                    total_samples += len(chunk)

                    if chunk_index == 0:
                        latency_ms = int((time.perf_counter() - start) * 1000)

                    # Send audio_chunk metadata as JSON, then binary data
                    await ws.send_json({
                        "message_type": "audio_chunk",
                        "request_id": request_id,
                        "chunk_index": chunk_index,
                        "chunk_size": len(pcm_bytes),
                        "sample_rate": sr,
                        "is_final": False,
                        "timestamp": time.time(),
                    })
                    await ws.send_bytes(pcm_bytes)
                    chunk_index += 1
            finally:
                semaphore.release()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass

        except WebSocketDisconnect:
            stop_event.set()
            logger.info("WebSocket client disconnected during streaming")
            return

        total_ms = int((time.perf_counter() - start) * 1000)
        duration_sec = total_samples / sr if sr > 0 else 0

        # Record history
        history_id = None
        try:
            async with async_session_factory() as db:
                from app.modules.tts.service import record_history

                record = await record_history(
                    db,
                    engine_name=resolved_engine,
                    text=text,
                    language=language,
                    voice_id=voice_id,
                    parameters=params,
                    status="completed",
                    latency_ms=latency_ms,
                    total_time_ms=total_ms,
                    audio_duration_sec=duration_sec,
                    sample_rate=sr,
                )
                history_id = record.id
        except Exception:
            logger.warning("Failed to record history for WebSocket generation", exc_info=True)

        # synthesis_complete
        slots = engine_registry.gpu_slots(resolved_engine)
        await ws.send_json({
            "message_type": "synthesis_complete",
            "request_id": request_id,
            "history_id": str(history_id) if history_id else None,
            "total_chunks": chunk_index,
            "duration": round(duration_sec, 2),
            "synthesis_time": round(total_ms / 1000, 3),
            "latency_ms": latency_ms,
            "gpu_slots_free": slots["free"],
            "gpu_slots_total": slots["total"],
            "timestamp": time.time(),
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except json.JSONDecodeError:
        await ws.send_json({
            "message_type": "error",
            "error_code": "invalid_json",
            "error_message": "Invalid JSON",
        })
        await ws.close()
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await ws.send_json({
                "message_type": "error",
                "error_code": "internal_error",
                "error_message": "Internal server error",
            })
        except Exception:
            pass
        await ws.close()
