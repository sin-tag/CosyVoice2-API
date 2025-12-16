"""Streaming API endpoints for CosyVoice3 - v3 Real-time audio streaming with low latency"""
import logging
import asyncio
import time
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.models.streaming import (
    StreamingSynthesisRequest, HTTPStreamingRequest, StreamingQuality,
    StreamingError, StreamingChunkMetadata
)
from app.models.voice import AudioFormat
from app.core.streaming_synthesis_engine import StreamingSynthesisEngine
from app.core.synthesis_engine_v3 import SynthesisEngineV3
from app.core.voice_manager_v3 import VoiceManagerV3

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaming", tags=["Streaming (v3)"])

_streaming_engine_v3: Optional[StreamingSynthesisEngine] = None


def get_voice_manager_v3(request: Request) -> VoiceManagerV3:
    """Dependency to get voice manager v3 from app state"""
    voice_manager = getattr(request.app.state, 'voice_manager_v3', None)
    if not voice_manager:
        raise HTTPException(status_code=503, detail="CosyVoice3 voice manager not available")
    if not voice_manager.is_ready():
        raise HTTPException(status_code=503, detail="CosyVoice3 voice manager is not ready")
    return voice_manager


def get_streaming_engine_v3(
    voice_manager: VoiceManagerV3 = Depends(get_voice_manager_v3)
) -> StreamingSynthesisEngine:
    """Get or create streaming synthesis engine for v3"""
    global _streaming_engine_v3

    # Create a synthesis engine adapter for v3
    from app.core.synthesis_engine import SynthesisEngine

    # Create a wrapper that uses v3's voice manager
    class SynthesisEngineV3Adapter(SynthesisEngine):
        def __init__(self, voice_manager_v3):
            self.voice_manager = voice_manager_v3

    if _streaming_engine_v3 is None:
        synthesis_engine = SynthesisEngineV3Adapter(voice_manager)
        _streaming_engine_v3 = StreamingSynthesisEngine(synthesis_engine)

    return _streaming_engine_v3


@router.post("/cross-lingual")
async def stream_cross_lingual_synthesis(
    text: str = Form(..., description="Text to synthesize", max_length=2000),
    voice_id: str = Form(..., description="Voice ID from cache"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Audio format"),
    speed: float = Form(1.0, description="Speech speed multiplier", ge=0.5, le=2.0),
    quality: StreamingQuality = Form(StreamingQuality.MEDIUM, description="Streaming quality"),
    chunk_size: Optional[int] = Form(1024, description="Chunk size in bytes", ge=256, le=8192),
    request: Request = None,
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine_v3)
):
    """Stream cross-lingual synthesis with real-time audio chunks (CosyVoice3)

    CosyVoice3 provides ~150ms latency for streaming synthesis.
    """

    logger.info(f"Starting streaming synthesis (v3): text='{text[:50]}...', voice_id='{voice_id}'")

    try:
        streaming_request = StreamingSynthesisRequest(
            text=text,
            voice_id=voice_id,
            format=format,
            speed=speed,
            quality=quality,
            chunk_size=chunk_size
        )

        headers = await streaming_engine.get_streaming_headers(format)
        headers["X-CosyVoice-Version"] = "3"

        async def generate_audio_stream():
            try:
                chunk_count = 0
                total_bytes = 0
                start_time = time.time()

                async for chunk_bytes, metadata in streaming_engine.stream_cross_lingual_synthesis(streaming_request):
                    if request and await request.is_disconnected():
                        logger.info(f"Client disconnected during streaming (v3)")
                        break

                    chunk_count += 1
                    total_bytes += len(chunk_bytes)
                    yield chunk_bytes

                    logger.debug(f"Streamed chunk (v3) {chunk_count}, {len(chunk_bytes)} bytes")

                streaming_time = time.time() - start_time
                logger.info(f"Streaming (v3) completed: {chunk_count} chunks, {total_bytes} bytes, {streaming_time:.2f}s")

            except StreamingError as e:
                logger.error(f"Streaming error (v3): {e.message}")
                error_response = f"ERROR: {e.error_code} - {e.message}\r\n\r\n"
                yield error_response.encode('utf-8')
            except Exception as e:
                logger.error(f"Unexpected streaming error (v3): {e}")
                error_response = f"ERROR: UNEXPECTED_ERROR - {str(e)}\r\n\r\n"
                yield error_response.encode('utf-8')

        def cleanup_task():
            logger.debug("Streaming request (v3) completed, cleaning up resources")

        return StreamingResponse(
            generate_audio_stream(),
            media_type=headers["Content-Type"],
            headers=headers,
            background=BackgroundTask(cleanup_task)
        )

    except Exception as e:
        logger.error(f"Failed to start streaming synthesis (v3): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start streaming synthesis: {str(e)}"
        )


@router.post("/cross-lingual/chunked")
async def stream_cross_lingual_chunked(
    text: str = Form(..., description="Text to synthesize", max_length=2000),
    voice_id: str = Form(..., description="Voice ID from cache"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Audio format"),
    speed: float = Form(1.0, description="Speech speed multiplier", ge=0.5, le=2.0),
    quality: StreamingQuality = Form(StreamingQuality.MEDIUM, description="Streaming quality"),
    request: Request = None,
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine_v3)
):
    """Stream cross-lingual synthesis with chunked transfer encoding (CosyVoice3)"""

    logger.info(f"Starting chunked streaming (v3): text='{text[:50]}...', voice_id='{voice_id}'")

    try:
        streaming_request = StreamingSynthesisRequest(
            text=text,
            voice_id=voice_id,
            format=format,
            speed=speed,
            quality=quality
        )

        headers = await streaming_engine.get_streaming_headers(format)
        headers["X-CosyVoice-Version"] = "3"

        async def generate_chunked_stream():
            try:
                chunk_count = 0

                async for chunk_bytes, metadata in streaming_engine.stream_cross_lingual_synthesis(streaming_request):
                    if request and await request.is_disconnected():
                        logger.info("Client disconnected during chunked streaming (v3)")
                        break

                    chunk_count += 1
                    yield chunk_bytes

                    if metadata.is_final:
                        logger.info(f"Chunked streaming (v3) completed: {chunk_count} chunks")
                        break

            except Exception as e:
                logger.error(f"Chunked streaming error (v3): {e}")
                return

        return StreamingResponse(
            generate_chunked_stream(),
            media_type=headers["Content-Type"],
            headers=headers
        )

    except Exception as e:
        logger.error(f"Failed to start chunked streaming (v3): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start chunked streaming: {str(e)}"
        )


@router.get("/cross-lingual/sse")
async def stream_cross_lingual_sse(
    text: str,
    voice_id: str,
    format: AudioFormat = AudioFormat.WAV,
    speed: float = 1.0,
    quality: StreamingQuality = StreamingQuality.MEDIUM,
    request: Request = None,
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine_v3)
):
    """Stream cross-lingual synthesis using Server-Sent Events (CosyVoice3)"""

    logger.info(f"Starting SSE streaming (v3): text='{text[:50]}...', voice_id='{voice_id}'")

    try:
        streaming_request = StreamingSynthesisRequest(
            text=text,
            voice_id=voice_id,
            format=format,
            speed=speed,
            quality=quality
        )

        async def generate_sse_stream():
            try:
                chunk_count = 0
                total_bytes = 0
                start_time = time.time()

                yield f"event: start\ndata: {{\"message\": \"Starting CosyVoice3 synthesis\", \"version\": \"v3\", \"timestamp\": {time.time()}}}\n\n"

                async for chunk_bytes, metadata in streaming_engine.stream_cross_lingual_synthesis(streaming_request):
                    if request and await request.is_disconnected():
                        logger.info("Client disconnected during SSE streaming (v3)")
                        break

                    chunk_count += 1
                    total_bytes += len(chunk_bytes)

                    import base64
                    chunk_b64 = base64.b64encode(chunk_bytes).decode('utf-8')

                    event_data = {
                        "chunk_index": chunk_count,
                        "chunk_size": len(chunk_bytes),
                        "total_bytes": total_bytes,
                        "audio_data": chunk_b64,
                        "is_final": metadata.is_final,
                        "timestamp": time.time(),
                        "sample_rate": metadata.sample_rate,
                        "channels": metadata.channels,
                        "version": "v3"
                    }

                    yield f"event: audio_chunk\ndata: {json.dumps(event_data)}\n\n"

                    if metadata.is_final:
                        break

                completion_data = {
                    "total_chunks": chunk_count,
                    "total_bytes": total_bytes,
                    "duration": time.time() - start_time,
                    "message": "CosyVoice3 synthesis completed",
                    "version": "v3"
                }
                yield f"event: complete\ndata: {json.dumps(completion_data)}\n\n"

                logger.info(f"SSE streaming (v3) completed: {chunk_count} chunks, {total_bytes} bytes")

            except Exception as e:
                logger.error(f"SSE streaming (v3) failed: {e}")
                error_data = {"error": str(e), "timestamp": time.time(), "version": "v3"}
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            generate_sse_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-CosyVoice-Version": "3"
            }
        )

    except Exception as e:
        logger.error(f"Failed to start SSE streaming (v3): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start SSE streaming: {str(e)}"
        )


@router.get("/health")
async def streaming_health_check(
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine_v3)
):
    """Health check for streaming functionality (CosyVoice3)"""
    try:
        return {
            "status": "healthy",
            "version": "v3",
            "model": "CosyVoice3",
            "streaming_engine": "available",
            "supported_formats": [format.value for format in AudioFormat],
            "supported_qualities": [quality.value for quality in StreamingQuality],
            "latency_ms": 150,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Streaming health check (v3) failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"CosyVoice3 streaming service unavailable: {str(e)}"
        )
