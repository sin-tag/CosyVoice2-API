import asyncio
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
    """WebSocket endpoint for real-time TTS streaming.

    Protocol:
    1. Client connects
    2. Client sends JSON config: {"text": "...", "language": "en", "voice_id": "uuid", ...params}
    3. Server sends binary PCM16 frames (24kHz, mono, 16-bit LE)
    4. Server sends JSON when done: {"type": "done", "history_id": "uuid", "latency_ms": N, "total_time_ms": N}
    5. Client can send {"type": "stop"} to cancel mid-generation
    """
    await ws.accept()

    # Verify API key from query params or first message
    api_key = ws.query_params.get("api_key")
    if api_key != settings.api_key:
        await ws.close(code=4001, reason="Invalid API key")
        return

    try:
        # Wait for config message
        config_raw = await ws.receive_text()
        config = json.loads(config_raw)

        text = config.get("text", "")
        language = config.get("language", "en")
        voice_id_str = config.get("voice_id")
        voice_id = uuid.UUID(voice_id_str) if voice_id_str else None
        params = {
            "temperature": config.get("temperature", 0.7),
            "top_p": config.get("top_p", 0.9),
            "top_k": config.get("top_k", 50),
            "repetition_penalty": config.get("repetition_penalty", 1.2),
        }

        if not text:
            await ws.send_json({"type": "error", "message": "Text is required"})
            await ws.close()
            return

        engine = engine_registry.get(engine_name)

        if not engine.supports_language(language):
            await ws.send_json({
                "type": "error",
                "message": f"Language '{language}' not supported. Supported: {engine.supported_languages}",
            })
            await ws.close()
            return

        # Resolve voice
        voice_data = None
        if voice_id:
            async with async_session_factory() as db:
                voice_data = await voice_cache.get_or_prepare(voice_id, engine, db)
            if voice_data is None:
                await ws.send_json({"type": "error", "message": f"Voice '{voice_id}' not found or not compatible"})
                await ws.close()
                return

        # Stream audio
        stop_event = threading.Event()
        semaphore = engine_registry.get_semaphore(engine_name)

        start = time.perf_counter()
        first_chunk = True
        latency_ms = 0
        total_samples = 0
        sr = 24000

        # Wait for semaphore with timeout
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.generation_timeout_sec)
        except asyncio.TimeoutError:
            await ws.send_json({"type": "error", "message": "GPU queue full — try again later"})
            await ws.close()
            return

        try:
            try:
                async for chunk in engine.stream_generate(text, language, voice_data, **params):
                    if stop_event.is_set():
                        break

                    pcm_bytes = _audio_to_pcm16_bytes(chunk)
                    total_samples += len(chunk)

                    if first_chunk:
                        latency_ms = int((time.perf_counter() - start) * 1000)
                        await ws.send_json({
                            "type": "metadata",
                            "sample_rate": sr,
                            "latency_ms": latency_ms,
                        })
                        first_chunk = False

                    await ws.send_bytes(pcm_bytes)
            finally:
                semaphore.release()
                # Free fragmented GPU memory
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
                    engine_name=engine_name,
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

        # Send done message
        await ws.send_json({
            "type": "done",
            "history_id": str(history_id) if history_id else None,
            "latency_ms": latency_ms,
            "total_time_ms": total_ms,
            "audio_duration_sec": round(duration_sec, 2),
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except json.JSONDecodeError:
        await ws.send_json({"type": "error", "message": "Invalid JSON"})
        await ws.close()
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        await ws.close()
