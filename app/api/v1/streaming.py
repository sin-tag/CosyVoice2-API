"""Streaming API endpoints for CosyVoice2 - Real-time audio streaming"""
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
from app.core.synthesis_engine import SynthesisEngine
from app.dependencies import get_synthesis_engine

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/streaming", tags=["streaming"])

# Global streaming engine instance
_streaming_engine: Optional[StreamingSynthesisEngine] = None

def get_streaming_engine(
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
) -> StreamingSynthesisEngine:
    """Get or create streaming synthesis engine"""
    global _streaming_engine
    if _streaming_engine is None:
        _streaming_engine = StreamingSynthesisEngine(synthesis_engine)
    return _streaming_engine

@router.post("/cross-lingual")
async def stream_cross_lingual_synthesis(
    text: str = Form(..., description="Text to synthesize", max_length=2000),
    voice_id: str = Form(..., description="Voice ID from cache"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Audio format"),
    speed: float = Form(1.0, description="Speech speed multiplier", ge=0.5, le=2.0),
    quality: StreamingQuality = Form(StreamingQuality.MEDIUM, description="Streaming quality"),
    chunk_size: Optional[int] = Form(1024, description="Chunk size in bytes", ge=256, le=8192),
    request: Request = None,
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine)
):
    """Stream cross-lingual synthesis with real-time audio chunks
    
    This endpoint returns audio data as it's generated, providing real-time streaming
    capabilities for voice synthesis. The audio is sent in chunks using HTTP streaming.
    """
    
    logger.info(f"Starting streaming synthesis: text='{text[:50]}...', voice_id='{voice_id}'")
    
    try:
        # Create streaming request
        streaming_request = StreamingSynthesisRequest(
            text=text,
            voice_id=voice_id,
            format=format,
            speed=speed,
            quality=quality,
            chunk_size=chunk_size
        )
        
        # Get appropriate headers
        headers = await streaming_engine.get_streaming_headers(format)
        
        # Create streaming generator
        async def generate_audio_stream():
            """Generate audio stream with proper error handling"""
            try:
                chunk_count = 0
                total_bytes = 0
                start_time = time.time()
                
                async for chunk_bytes, metadata in streaming_engine.stream_cross_lingual_synthesis(streaming_request):
                    # Check if client disconnected
                    if request and await request.is_disconnected():
                        logger.info(f"Client disconnected during streaming, stopping synthesis")
                        break
                    
                    chunk_count += 1
                    total_bytes += len(chunk_bytes)
                    
                    # Yield only pure audio data (no metadata headers in stream)
                    yield chunk_bytes
                    
                    logger.debug(f"Streamed chunk {chunk_count}, {len(chunk_bytes)} bytes")
                
                streaming_time = time.time() - start_time
                logger.info(f"Streaming completed: {chunk_count} chunks, {total_bytes} bytes, {streaming_time:.2f}s")
                
            except StreamingError as e:
                logger.error(f"Streaming error: {e.message}")
                error_response = f"ERROR: {e.error_code} - {e.message}\r\n\r\n"
                yield error_response.encode('utf-8')
            except Exception as e:
                logger.error(f"Unexpected streaming error: {e}")
                error_response = f"ERROR: UNEXPECTED_ERROR - {str(e)}\r\n\r\n"
                yield error_response.encode('utf-8')
        
        # Create background task for cleanup
        def cleanup_task():
            logger.debug("Streaming request completed, cleaning up resources")
        
        # Return streaming response
        return StreamingResponse(
            generate_audio_stream(),
            media_type=headers["Content-Type"],
            headers=headers,
            background=BackgroundTask(cleanup_task)
        )
        
    except Exception as e:
        logger.error(f"Failed to start streaming synthesis: {e}")
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
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine)
):
    """Stream cross-lingual synthesis with chunked transfer encoding
    
    This endpoint uses HTTP chunked transfer encoding to stream audio data
    in real-time. Each chunk contains raw audio data without additional headers.
    """
    
    logger.info(f"Starting chunked streaming: text='{text[:50]}...', voice_id='{voice_id}'")
    
    try:
        # Create streaming request
        streaming_request = StreamingSynthesisRequest(
            text=text,
            voice_id=voice_id,
            format=format,
            speed=speed,
            quality=quality
        )
        
        # Get appropriate headers
        headers = await streaming_engine.get_streaming_headers(format)
        
        # Create chunked streaming generator
        async def generate_chunked_stream():
            """Generate chunked audio stream"""
            try:
                chunk_count = 0
                
                async for chunk_bytes, metadata in streaming_engine.stream_cross_lingual_synthesis(streaming_request):
                    # Check if client disconnected
                    if request and await request.is_disconnected():
                        logger.info("Client disconnected during chunked streaming")
                        break
                    
                    chunk_count += 1
                    
                    # Yield raw audio chunk
                    yield chunk_bytes
                    
                    if metadata.is_final:
                        logger.info(f"Chunked streaming completed: {chunk_count} chunks")
                        break
                
            except Exception as e:
                logger.error(f"Chunked streaming error: {e}")
                # In chunked mode, we can't send error messages easily
                # Just log and stop the stream
                return
        
        # Return chunked streaming response
        return StreamingResponse(
            generate_chunked_stream(),
            media_type=headers["Content-Type"],
            headers=headers
        )
        
    except Exception as e:
        logger.error(f"Failed to start chunked streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start chunked streaming: {str(e)}"
        )

@router.post("/cross-lingual/progressive")
async def stream_cross_lingual_progressive(
    text: str = Form(..., description="Text to synthesize", max_length=2000),
    voice_id: str = Form(..., description="Voice ID from cache"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Audio format"),
    speed: float = Form(1.0, description="Speech speed multiplier", ge=0.5, le=2.0),
    quality: StreamingQuality = Form(StreamingQuality.MEDIUM, description="Streaming quality"),
    request: Request = None,
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine)
):
    """Stream cross-lingual synthesis with progressive audio playback support

    This endpoint provides proper WAV streaming with header first, then raw PCM data.
    Designed for progressive audio playback in browsers.
    """

    logger.info(f"Starting progressive streaming: text='{text[:50]}...', voice_id='{voice_id}'")

    try:
        # Create streaming request
        streaming_request = StreamingSynthesisRequest(
            text=text,
            voice_id=voice_id,
            format=format,
            speed=speed,
            quality=quality
        )

        # Get appropriate headers optimized for progressive playback
        headers = await streaming_engine.get_streaming_headers(format)
        headers.update({
            "Accept-Ranges": "bytes",
            "X-Progressive-Audio": "true",
            "Access-Control-Expose-Headers": "Content-Length,Accept-Ranges,X-Progressive-Audio"
        })

        # Create progressive streaming generator
        async def generate_progressive_stream():
            """Generate progressive audio stream with proper WAV structure"""
            try:
                chunk_count = 0
                total_bytes = 0
                start_time = time.time()

                async for chunk_bytes, metadata in streaming_engine.stream_cross_lingual_synthesis(streaming_request):
                    # Check if client disconnected
                    if request and await request.is_disconnected():
                        logger.info("Client disconnected during progressive streaming")
                        break

                    chunk_count += 1
                    total_bytes += len(chunk_bytes)

                    # Yield audio chunk
                    yield chunk_bytes

                    # Log progress for first chunk and every 10th chunk
                    if chunk_count == 1 or chunk_count % 10 == 0:
                        elapsed = time.time() - start_time
                        logger.info(f"Progressive stream: {chunk_count} chunks, {total_bytes} bytes in {elapsed:.2f}s")

                    if metadata.is_final:
                        logger.info(f"Progressive streaming completed: {chunk_count} chunks, {total_bytes} bytes")
                        break

            except Exception as e:
                logger.error(f"Progressive streaming failed: {e}")
                # Don't yield error in progressive mode as it might corrupt audio
                raise

        # Return progressive streaming response
        return StreamingResponse(
            generate_progressive_stream(),
            media_type=headers["Content-Type"],
            headers=headers
        )

    except Exception as e:
        logger.error(f"Failed to start progressive streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start progressive streaming: {str(e)}"
        )

@router.get("/cross-lingual/sse")
async def stream_cross_lingual_sse(
    text: str,
    voice_id: str,
    format: AudioFormat = AudioFormat.WAV,
    speed: float = 1.0,
    quality: StreamingQuality = StreamingQuality.MEDIUM,
    request: Request = None,
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine)
):
    """Stream cross-lingual synthesis using Server-Sent Events for true progressive playback

    This endpoint uses SSE to send audio chunks as separate events, enabling
    true progressive audio playback in browsers.
    """

    logger.info(f"Starting SSE streaming: text='{text[:50]}...', voice_id='{voice_id}'")

    try:
        # Create streaming request
        streaming_request = StreamingSynthesisRequest(
            text=text,
            voice_id=voice_id,
            format=format,
            speed=speed,
            quality=quality
        )

        # SSE streaming generator
        async def generate_sse_stream():
            """Generate Server-Sent Events stream for progressive audio"""
            try:
                chunk_count = 0
                total_bytes = 0
                start_time = time.time()

                # Send initial event
                yield f"event: start\ndata: {{\"message\": \"Starting synthesis\", \"timestamp\": {time.time()}}}\n\n"

                async for chunk_bytes, metadata in streaming_engine.stream_cross_lingual_synthesis(streaming_request):
                    # Check if client disconnected
                    if request and await request.is_disconnected():
                        logger.info("Client disconnected during SSE streaming")
                        break

                    chunk_count += 1
                    total_bytes += len(chunk_bytes)

                    # Encode audio chunk as base64 for SSE transmission
                    import base64
                    chunk_b64 = base64.b64encode(chunk_bytes).decode('utf-8')

                    # Send audio chunk event
                    event_data = {
                        "chunk_index": chunk_count,
                        "chunk_size": len(chunk_bytes),
                        "total_bytes": total_bytes,
                        "audio_data": chunk_b64,
                        "is_final": metadata.is_final,
                        "timestamp": time.time(),
                        "sample_rate": metadata.sample_rate,
                        "channels": metadata.channels
                    }

                    yield f"event: audio_chunk\ndata: {json.dumps(event_data)}\n\n"

                    # Log progress
                    if chunk_count == 1 or chunk_count % 5 == 0:
                        elapsed = time.time() - start_time
                        logger.info(f"SSE stream: {chunk_count} chunks, {total_bytes} bytes in {elapsed:.2f}s")

                    if metadata.is_final:
                        break

                # Send completion event
                completion_data = {
                    "total_chunks": chunk_count,
                    "total_bytes": total_bytes,
                    "duration": time.time() - start_time,
                    "message": "Synthesis completed"
                }
                yield f"event: complete\ndata: {json.dumps(completion_data)}\n\n"

                logger.info(f"SSE streaming completed: {chunk_count} chunks, {total_bytes} bytes")

            except Exception as e:
                logger.error(f"SSE streaming failed: {e}")
                error_data = {
                    "error": str(e),
                    "timestamp": time.time()
                }
                yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

        # Return SSE response
        return StreamingResponse(
            generate_sse_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )

    except Exception as e:
        logger.error(f"Failed to start SSE streaming: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start SSE streaming: {str(e)}"
        )

@router.get("/health")
async def streaming_health_check(
    streaming_engine: StreamingSynthesisEngine = Depends(get_streaming_engine)
):
    """Health check for streaming functionality"""
    try:
        # Basic health check
        return {
            "status": "healthy",
            "streaming_engine": "available",
            "supported_formats": [format.value for format in AudioFormat],
            "supported_qualities": [quality.value for quality in StreamingQuality],
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Streaming health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Streaming service unavailable: {str(e)}"
        )

@router.get("/stats")
async def streaming_stats():
    """Get streaming performance statistics"""
    # This would be implemented with actual metrics collection
    # For now, return basic placeholder stats
    return {
        "active_streams": 0,
        "total_streams": 0,
        "average_latency_ms": 0.0,
        "error_rate": 0.0,
        "supported_concurrent_streams": 10,
        "timestamp": time.time()
    }
