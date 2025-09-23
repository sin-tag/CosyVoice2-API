"""Streaming API endpoints for CosyVoice2 - Real-time audio streaming"""
import logging
import asyncio
import time
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
                    
                    # Yield chunk with metadata header
                    metadata_header = f"X-Chunk-Index: {metadata.chunk_index}\r\n"
                    metadata_header += f"X-Chunk-Size: {metadata.chunk_size}\r\n"
                    metadata_header += f"X-Is-Final: {metadata.is_final}\r\n"
                    metadata_header += f"X-Sample-Rate: {metadata.sample_rate}\r\n"
                    
                    if metadata.is_final:
                        metadata_header += f"X-Total-Chunks: {metadata.total_chunks}\r\n"
                    
                    metadata_header += "\r\n"
                    
                    # Yield metadata header followed by audio data
                    yield metadata_header.encode('utf-8')
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
