# CosyVoice2 Streaming API Documentation

## Overview

The CosyVoice2 Streaming API provides real-time voice synthesis capabilities with support for HTTP streaming and WebSocket bidirectional communication. This enables low-latency voice generation perfect for real-time applications, chatbots, and interactive voice systems.

## Features

- **Real-time HTTP Streaming**: Stream audio chunks as they're generated
- **WebSocket Support**: Bidirectional real-time communication
- **Multiple Concurrent Streams**: Handle multiple synthesis requests simultaneously
- **Multiple Audio Formats**: Support for WAV, MP3, FLAC, and M4A
- **Quality Optimization**: Configurable streaming quality (Low/Medium/High)
- **Comprehensive Error Handling**: Robust error recovery and graceful degradation
- **Async Task Processing**: Non-blocking synthesis with proper resource management

## Quick Start

### 1. HTTP Streaming

Stream audio synthesis with chunked transfer encoding:

```python
import aiohttp
import asyncio

async def stream_synthesis():
    url = "http://localhost:8000/api/v1/streaming/cross-lingual"
    data = {
        "text": "Hello, this is streaming synthesis!",
        "voice_id": "your_voice_id",
        "format": "wav",
        "quality": "medium"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            async for chunk in response.content.iter_chunked(1024):
                # Process audio chunk
                print(f"Received {len(chunk)} bytes")

asyncio.run(stream_synthesis())
```

### 2. WebSocket Streaming

Real-time bidirectional streaming:

```python
import websockets
import json
import base64
import asyncio

async def websocket_synthesis():
    uri = "ws://localhost:8000/api/v1/ws/stream"
    
    async with websockets.connect(uri) as websocket:
        # Send synthesis request
        request = {
            "message_type": "text_request",
            "text": "Hello WebSocket streaming!",
            "voice_id": "your_voice_id",
            "format": "wav",
            "quality": "high"
        }
        
        await websocket.send(json.dumps(request))
        
        # Receive streaming audio
        while True:
            response = await websocket.recv()
            message = json.loads(response)
            
            if message["message_type"] == "audio_chunk":
                audio_data = base64.b64decode(message["audio_data"])
                # Process audio chunk
                print(f"Received audio chunk: {len(audio_data)} bytes")
                
                if message["metadata"]["is_final"]:
                    break

asyncio.run(websocket_synthesis())
```

## API Endpoints

### HTTP Streaming Endpoints

#### POST `/api/v1/streaming/cross-lingual`
Stream cross-lingual synthesis with metadata headers.

**Parameters:**
- `text` (string): Text to synthesize (max 2000 chars)
- `voice_id` (string): Voice ID from cache
- `format` (string): Audio format (wav, mp3, flac, m4a)
- `speed` (float): Speech speed (0.5-2.0)
- `quality` (string): Streaming quality (low, medium, high)
- `chunk_size` (int): Chunk size in bytes (256-8192)

**Response:**
- Content-Type: `audio/wav` (or specified format)
- Transfer-Encoding: `chunked`
- Custom headers with chunk metadata

#### POST `/api/v1/streaming/cross-lingual/chunked`
Stream synthesis with pure chunked transfer encoding.

**Parameters:** Same as above

**Response:**
- Raw audio chunks without metadata headers
- Optimized for minimal latency

### WebSocket Endpoints

#### WebSocket `/api/v1/ws/stream`
Bidirectional streaming synthesis.

**Message Types:**

**Client → Server:**
```json
{
  "message_type": "text_request",
  "text": "Text to synthesize",
  "voice_id": "voice_id",
  "format": "wav",
  "speed": 1.0,
  "quality": "medium",
  "request_id": "optional_request_id"
}
```

**Server → Client:**
```json
{
  "message_type": "audio_chunk",
  "audio_data": "base64_encoded_audio",
  "metadata": {
    "chunk_index": 0,
    "chunk_size": 1024,
    "is_final": false,
    "sample_rate": 22050
  },
  "request_id": "request_id",
  "timestamp": 1234567890.123
}
```

### Health and Monitoring

#### GET `/api/v1/streaming/health`
Check streaming service health.

#### GET `/api/v1/streaming/stats`
Get streaming performance statistics.

#### GET `/api/v1/ws/sessions`
List active WebSocket sessions.

## Streaming Quality Settings

| Quality | Sample Rate | Bitrate | Latency | Use Case |
|---------|-------------|---------|---------|----------|
| Low     | 16kHz       | 64kbps  | ~50ms   | Real-time chat |
| Medium  | 22kHz       | 128kbps | ~100ms  | General streaming |
| High    | 44kHz       | 256kbps | ~200ms  | High-quality audio |

## Error Handling

The streaming API provides comprehensive error handling:

### HTTP Streaming Errors
- **500**: Synthesis engine error
- **503**: Service unavailable
- **429**: Too many concurrent requests

### WebSocket Error Messages
```json
{
  "message_type": "error",
  "error_code": "SYNTHESIS_ERROR",
  "error_message": "Detailed error description",
  "recoverable": true,
  "retry_after": 5
}
```

### Common Error Types
- `CONNECTION_ERROR`: Client disconnected
- `SYNTHESIS_ERROR`: Voice generation failed
- `ENCODING_ERROR`: Audio format encoding failed
- `RESOURCE_ERROR`: Server resource limits exceeded
- `TIMEOUT_ERROR`: Request timeout
- `VALIDATION_ERROR`: Invalid request parameters

## Performance Optimization

### Concurrent Streaming
The API supports multiple concurrent streams:

```python
# Configure maximum concurrent streams
config = {
    "max_concurrent_streams": 10,
    "max_sessions": 100,
    "chunk_timeout": 5.0,
    "session_timeout": 300.0
}
```

### Chunk Size Optimization
Optimal chunk sizes by format:
- **WAV**: 2048 samples (low latency)
- **MP3**: 4096 samples (compression efficiency)
- **FLAC**: 4096 samples (compression balance)

### Network Optimization
- Use `quality=low` for real-time applications
- Use `quality=high` for offline processing
- Implement client-side buffering for smooth playback

## Example Applications

### Real-time Chat Bot
```python
async def chatbot_streaming(user_message, voice_id):
    # Generate response text
    response_text = await generate_response(user_message)
    
    # Stream synthesis
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/api/v1/streaming/cross-lingual/chunked",
            data={
                "text": response_text,
                "voice_id": voice_id,
                "quality": "low"  # Low latency for real-time
            }
        ) as response:
            async for chunk in response.content.iter_any():
                await play_audio_chunk(chunk)
```

### Interactive Voice Assistant
```python
async def voice_assistant():
    uri = "ws://localhost:8000/api/v1/ws/stream"
    
    async with websockets.connect(uri) as websocket:
        while True:
            # Listen for user input
            user_text = await get_user_input()
            
            # Send synthesis request
            await websocket.send(json.dumps({
                "message_type": "text_request",
                "text": user_text,
                "voice_id": "assistant_voice",
                "quality": "medium"
            }))
            
            # Stream response
            await stream_websocket_audio(websocket)
```

## Testing

Run the comprehensive streaming demo:

```bash
python examples/streaming_demo.py --voice-id your_voice_id --concurrent 5
```

Run streaming tests:

```bash
pytest tests/test_streaming.py -v
```

## Troubleshooting

### Common Issues

1. **High Latency**: Use lower quality settings or smaller chunk sizes
2. **Connection Drops**: Implement reconnection logic with exponential backoff
3. **Memory Usage**: Monitor concurrent stream limits
4. **Audio Artifacts**: Check network stability and buffer sizes

### Debug Mode
Enable detailed logging:

```python
import logging
logging.getLogger("app.core.streaming").setLevel(logging.DEBUG)
```

### Performance Monitoring
Monitor streaming statistics:

```bash
curl http://localhost:8000/api/v1/streaming/stats
```

## Advanced Configuration

### Custom Streaming Engine
```python
from app.core.streaming_synthesis_engine import StreamingSynthesisEngine
from app.models.streaming import StreamingConfig

config = StreamingConfig(
    max_concurrent_streams=20,
    chunk_timeout=10.0,
    quality_settings={
        "custom": {"sample_rate": 32000, "bitrate": 192000}
    }
)

engine = StreamingSynthesisEngine(synthesis_engine, config)
```

### Custom Error Handling
```python
from app.core.streaming_error_handler import StreamingErrorHandler

error_handler = StreamingErrorHandler()

# Custom error handler
async def custom_synthesis_error_handler(error, context, streaming_error):
    # Implement custom recovery logic
    pass

error_handler.error_handlers[StreamingErrorType.SYNTHESIS_ERROR] = custom_synthesis_error_handler
```

## Support

For issues and questions:
- Check the [main README](../README.md) for general setup
- Review [API Examples](API_EXAMPLES.md) for more usage patterns
- Run the streaming demo for testing your setup
