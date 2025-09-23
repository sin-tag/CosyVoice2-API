"""Streaming models for CosyVoice2 API - Real-time audio streaming support"""
from typing import Optional, Union, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
from .voice import AudioFormat

class StreamingMode(str, Enum):
    """Streaming modes for different use cases"""
    HTTP_CHUNKS = "http_chunks"  # HTTP streaming with chunked transfer
    WEBSOCKET = "websocket"      # WebSocket bidirectional streaming
    SERVER_SENT_EVENTS = "sse"   # Server-Sent Events for one-way streaming

class StreamingQuality(str, Enum):
    """Audio quality settings for streaming optimization"""
    LOW = "low"        # 16kHz, optimized for speed
    MEDIUM = "medium"  # 22kHz, balanced quality/speed
    HIGH = "high"      # 44kHz, best quality

class WebSocketMessageType(str, Enum):
    """WebSocket message types for bidirectional communication"""
    TEXT_REQUEST = "text_request"           # Client sends text to synthesize
    AUDIO_CHUNK = "audio_chunk"            # Server sends audio chunk
    SYNTHESIS_START = "synthesis_start"     # Server confirms synthesis started
    SYNTHESIS_COMPLETE = "synthesis_complete"  # Server confirms synthesis completed
    ERROR = "error"                        # Error message
    PING = "ping"                          # Keep-alive ping
    PONG = "pong"                          # Keep-alive pong
    STATUS = "status"                      # Status update

# Streaming Request Models
class StreamingSynthesisRequest(BaseModel):
    """Base request for streaming synthesis"""
    text: str = Field(..., description="Text to synthesize", max_length=2000)
    voice_id: str = Field(..., description="Voice ID from cache")
    format: AudioFormat = Field(AudioFormat.WAV, description="Audio format")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    quality: StreamingQuality = Field(StreamingQuality.MEDIUM, description="Streaming quality")
    chunk_size: Optional[int] = Field(1024, description="Audio chunk size in bytes", ge=256, le=8192)
    buffer_size: Optional[int] = Field(3, description="Number of chunks to buffer", ge=1, le=10)

class HTTPStreamingRequest(StreamingSynthesisRequest):
    """HTTP streaming synthesis request"""
    mode: StreamingMode = Field(StreamingMode.HTTP_CHUNKS, description="Streaming mode")
    accept_ranges: bool = Field(True, description="Support HTTP range requests")

class WebSocketSynthesisRequest(BaseModel):
    """WebSocket synthesis request message"""
    message_type: WebSocketMessageType = Field(WebSocketMessageType.TEXT_REQUEST)
    text: str = Field(..., description="Text to synthesize", max_length=2000)
    voice_id: str = Field(..., description="Voice ID from cache")
    format: AudioFormat = Field(AudioFormat.WAV, description="Audio format")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    quality: StreamingQuality = Field(StreamingQuality.MEDIUM, description="Streaming quality")
    request_id: Optional[str] = Field(None, description="Client request ID for tracking")

# Streaming Response Models
class StreamingChunkMetadata(BaseModel):
    """Metadata for each streaming audio chunk"""
    chunk_index: int = Field(..., description="Sequential chunk number")
    chunk_size: int = Field(..., description="Size of this chunk in bytes")
    total_chunks: Optional[int] = Field(None, description="Total expected chunks (if known)")
    timestamp: float = Field(..., description="Timestamp when chunk was generated")
    is_final: bool = Field(False, description="Whether this is the final chunk")
    sample_rate: int = Field(22050, description="Audio sample rate")
    channels: int = Field(1, description="Number of audio channels")

class WebSocketMessage(BaseModel):
    """Base WebSocket message format"""
    message_type: WebSocketMessageType = Field(..., description="Message type")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: float = Field(..., description="Message timestamp")

class WebSocketAudioChunk(WebSocketMessage):
    """WebSocket audio chunk message"""
    message_type: WebSocketMessageType = Field(WebSocketMessageType.AUDIO_CHUNK)
    audio_data: str = Field(..., description="Base64 encoded audio data")
    metadata: StreamingChunkMetadata = Field(..., description="Chunk metadata")

class WebSocketSynthesisStart(WebSocketMessage):
    """WebSocket synthesis start confirmation"""
    message_type: WebSocketMessageType = Field(WebSocketMessageType.SYNTHESIS_START)
    text: str = Field(..., description="Text being synthesized")
    voice_id: str = Field(..., description="Voice ID being used")
    estimated_duration: Optional[float] = Field(None, description="Estimated audio duration")

class WebSocketSynthesisComplete(WebSocketMessage):
    """WebSocket synthesis completion message"""
    message_type: WebSocketMessageType = Field(WebSocketMessageType.SYNTHESIS_COMPLETE)
    total_chunks: int = Field(..., description="Total chunks sent")
    total_duration: float = Field(..., description="Total audio duration")
    synthesis_time: float = Field(..., description="Time taken for synthesis")

class WebSocketError(WebSocketMessage):
    """WebSocket error message"""
    message_type: WebSocketMessageType = Field(WebSocketMessageType.ERROR)
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

class WebSocketStatus(WebSocketMessage):
    """WebSocket status update message"""
    message_type: WebSocketMessageType = Field(WebSocketMessageType.STATUS)
    status: str = Field(..., description="Current status")
    progress: Optional[float] = Field(None, description="Progress percentage (0.0-1.0)")
    message: Optional[str] = Field(None, description="Status message")

# Streaming Session Management
class StreamingSession(BaseModel):
    """Streaming session information"""
    session_id: str = Field(..., description="Unique session identifier")
    client_id: Optional[str] = Field(None, description="Client identifier")
    created_at: float = Field(..., description="Session creation timestamp")
    last_activity: float = Field(..., description="Last activity timestamp")
    active_requests: int = Field(0, description="Number of active synthesis requests")
    total_requests: int = Field(0, description="Total requests in this session")
    connection_type: StreamingMode = Field(..., description="Connection type")
    client_info: Optional[Dict[str, Any]] = Field(None, description="Client information")

class StreamingStats(BaseModel):
    """Streaming performance statistics"""
    active_sessions: int = Field(0, description="Number of active streaming sessions")
    total_sessions: int = Field(0, description="Total sessions created")
    active_streams: int = Field(0, description="Number of active audio streams")
    total_chunks_sent: int = Field(0, description="Total audio chunks sent")
    average_chunk_size: float = Field(0.0, description="Average chunk size in bytes")
    average_latency: float = Field(0.0, description="Average streaming latency in ms")
    error_rate: float = Field(0.0, description="Error rate percentage")

# Error Models for Streaming
class StreamingError(Exception):
    """Streaming-specific error exception"""
    def __init__(self, message: str, error_type: str = "streaming_error", error_code: str = "STREAMING_ERROR", session_id: Optional[str] = None):
        super().__init__(message)
        self.error_type = error_type
        self.error_code = error_code
        self.message = message
        self.session_id = session_id

class StreamingErrorInfo(BaseModel):
    """Streaming error information for API responses"""
    error_type: str = Field(..., description="Type of streaming error")
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    session_id: Optional[str] = Field(None, description="Session ID where error occurred")
    request_id: Optional[str] = Field(None, description="Request ID where error occurred")
    timestamp: float = Field(..., description="Error timestamp")
    recoverable: bool = Field(False, description="Whether the error is recoverable")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")

# Configuration Models
class StreamingConfig(BaseModel):
    """Configuration for streaming functionality"""
    max_concurrent_streams: int = Field(10, description="Maximum concurrent streams per session")
    max_sessions: int = Field(100, description="Maximum total active sessions")
    chunk_timeout: float = Field(5.0, description="Timeout for chunk generation in seconds")
    session_timeout: float = Field(300.0, description="Session timeout in seconds")
    websocket_ping_interval: float = Field(30.0, description="WebSocket ping interval in seconds")
    buffer_size: int = Field(3, description="Default buffer size for streaming")
    quality_settings: Dict[StreamingQuality, Dict[str, Any]] = Field(
        default_factory=lambda: {
            StreamingQuality.LOW: {"sample_rate": 16000, "bitrate": 64000},
            StreamingQuality.MEDIUM: {"sample_rate": 22050, "bitrate": 128000},
            StreamingQuality.HIGH: {"sample_rate": 44100, "bitrate": 256000}
        }
    )
