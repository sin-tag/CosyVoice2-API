# CosyVoice API Documentation

## Overview

CosyVoice API cung cấp dịch vụ Text-to-Speech (TTS) với khả năng clone giọng nói đa ngôn ngữ.

- **Base URL**: `http://localhost:8012`
- **API Versions**: v1, v2 (CosyVoice2), v3 (CosyVoice3 - Recommended)

## API Versions

| Version | Model | Description |
|---------|-------|-------------|
| v1 | CosyVoice2-0.5B | Backward compatibility |
| v2 | CosyVoice2-0.5B | Legacy support |
| v3 | CosyVoice3-0.5B | **Latest - Recommended** |

## CosyVoice3 Features (v3)

- 9+ languages: Chinese, English, Japanese, Korean, German, Spanish, French, Italian, Russian
- 18+ Chinese dialects
- Instruction-based voice control
- ~150ms streaming latency
- Better content consistency & speaker similarity

---

## Authentication

Hiện tại API không yêu cầu authentication.

---

## Common Response Format

### Success Response
```json
{
  "success": true,
  "message": "Operation completed",
  "data": { ... }
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

---

# API Endpoints

## Health Check

### GET /health
Kiểm tra trạng thái server và các model.

**Response:**
```json
{
  "status": "healthy",
  "v2": {
    "ready": true,
    "model": "CosyVoice2-0.5B"
  },
  "v3": {
    "ready": true,
    "model": "CosyVoice3-0.5B"
  }
}
```

---

## Voice Management

### POST /api/v3/voices/
Tạo voice mới từ audio sample.

**Content-Type:** `multipart/form-data`

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| voice_id | string | Yes | Unique voice identifier |
| name | string | Yes | Human-readable voice name |
| description | string | No | Voice description |
| voice_type | enum | Yes | `sft`, `zero_shot`, `cross_lingual`, `instruct` |
| language | string | No | Primary language (e.g., "zh", "en", "ja") |
| prompt_text | string | No | Text matching the audio sample |
| audio_format | enum | No | `wav`, `mp3`, `flac` (default: `wav`) |
| audio_file | file | Yes | Audio file for voice cloning |

**Response:**
```json
{
  "voice_id": "my_voice_01",
  "name": "My Custom Voice",
  "description": "A custom voice for testing",
  "voice_type": "cross_lingual",
  "language": "zh",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "audio_format": "wav",
  "file_size": 245760,
  "duration": 5.2,
  "sample_rate": 22050,
  "is_active": true
}
```

### GET /api/v3/voices/
Liệt kê tất cả voices.

**Query Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| voice_type | enum | No | Filter by voice type |
| language | string | No | Filter by language |
| page | int | No | Page number (default: 1) |
| page_size | int | No | Items per page (default: 50, max: 100) |

**Response:**
```json
{
  "voices": [...],
  "total": 10,
  "page": 1,
  "page_size": 50
}
```

### GET /api/v3/voices/{voice_id}
Lấy thông tin voice theo ID.

### PUT /api/v3/voices/{voice_id}
Cập nhật thông tin voice.

### DELETE /api/v3/voices/{voice_id}
Xóa voice.

---

## Cross-lingual Synthesis

### POST /api/v3/cross-lingual/with-audio
Tổng hợp giọng nói với audio file tham chiếu.

**Content-Type:** `multipart/form-data`

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| text | string | Yes | Text to synthesize (max 2000 chars) |
| format | enum | No | Output format: `wav`, `mp3`, `flac` (default: `wav`) |
| speed | float | No | Speech speed 0.5-2.0 (default: 1.0) |
| stream | bool | No | Enable streaming (default: false) |
| instruct_text | string | No | **V3 only**: Instruction for voice control |
| prompt_audio | file | Yes | Reference audio file |

**instruct_text Examples (v3):**
- `"Use Cantonese dialect"`
- `"Speak slowly with a happy tone"`
- `"Use formal and professional tone"`
- `"Whisper softly"`

**Response:**
```json
{
  "success": true,
  "message": "CosyVoice3 synthesis completed",
  "audio_url": "/api/v3/audio/v3_cross_lingual_abc12345.wav",
  "file_path": "outputs/v3_cross_lingual_abc12345.wav",
  "duration": 3.5,
  "format": "wav",
  "synthesis_time": 1.2
}
```

### POST /api/v3/cross-lingual/with-cache
Tổng hợp giọng nói với cached voice.

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "text": "Hello, this is a test.",
  "voice_id": "my_voice_01",
  "format": "wav",
  "speed": 1.0,
  "stream": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "CosyVoice3 synthesis completed",
  "audio_url": "/api/v3/audio/v3_cache_abc12345.wav",
  "file_path": "outputs/v3_cache_abc12345.wav",
  "duration": 2.8,
  "format": "wav",
  "synthesis_time": 0.9
}
```

### POST /api/v3/cross-lingual/instruct (v3 only)
Tổng hợp với instruction control.

**Content-Type:** `multipart/form-data`

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| text | string | Yes | Text to synthesize |
| instruct_text | string | Yes | Instruction for voice control |
| format | enum | No | Output format (default: `wav`) |
| speed | float | No | Speech speed (default: 1.0) |
| stream | bool | No | Enable streaming (default: false) |
| prompt_audio | file | Yes | Reference audio file |

### GET /api/v3/cross-lingual/capabilities (v3 only)
Lấy thông tin capabilities của CosyVoice3.

**Response:**
```json
{
  "version": "3.0",
  "model": "Fun-CosyVoice3-0.5B-2512",
  "features": {
    "languages": ["Chinese (Mandarin)", "English", "Japanese", "Korean", "German", "Spanish", "French", "Italian", "Russian"],
    "chinese_dialects": ["Cantonese", "Sichuan", "Shanghai", "Hokkien", "Hakka", "..."],
    "instruct_support": true,
    "phoneme_support": {
      "chinese_pinyin": true,
      "english_cmu": true
    },
    "streaming": {
      "enabled": true,
      "latency_ms": 150
    }
  }
}
```

---

## Task-based Synthesis

### POST /api/v3/cross-lingual/task
Tạo synthesis task chạy background.

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "text": "Text to synthesize",
  "voice_id": "my_voice_01",
  "format": "wav",
  "speed": 1.0,
  "instruct_text": "Optional instruction"
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "registered",
  "file_path": "outputs/v3_task_abc12345.wav",
  "audio_url": "/api/v3/audio/v3_task_abc12345.wav",
  "estimated_duration": 1.8,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### GET /api/v3/cross-lingual/task/{task_id}
Lấy trạng thái task.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "file_path": "outputs/v3_task_abc12345.wav",
  "audio_url": "/api/v3/audio/v3_task_abc12345.wav",
  "progress": 1.0,
  "duration": 3.2,
  "synthesis_time": 1.1,
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:02Z",
  "error_message": null
}
```

**Task Status Values:**
- `registered`: Task created, waiting to process
- `processing`: Currently synthesizing
- `completed`: Done, audio ready
- `failed`: Error occurred

### GET /api/v3/cross-lingual/tasks
List all tasks.

### DELETE /api/v3/cross-lingual/task/{task_id}
Delete a task.

---

## Scheduled Background Rendering (v3 only)

The scheduled rendering API allows you to register tasks for later background processing.
This is useful for batch processing or when you want to control when the rendering starts.

### Workflow

```
1. POST /api/v3/schedule/register    → Returns task_id (status: pending)
2. POST /api/v3/schedule/render/{id} → Starts background rendering (status: processing)
3. GET /api/v3/schedule/status/{id}  → Check status, get audio_url when completed
```

### POST /api/v3/schedule/register
Register a new task for background rendering (does NOT start rendering).

**Content-Type:** `application/json`

**Request Body:**
```json
{
  "text": "Text to synthesize",
  "voice_id": "my_voice_01",
  "format": "wav",
  "speed": 1.0,
  "instruct_text": "Optional instruction for voice control",
  "priority": "normal",
  "callback_url": "https://your-server.com/webhook",
  "metadata": {"custom_field": "custom_value"}
}
```

**Priority Values:** `low`, `normal`, `high`, `urgent`

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Task registered successfully. Call POST /schedule/render/{task_id} to start rendering.",
  "queue_position": 1,
  "estimated_wait_time": 2.4,
  "created_at": "2024-01-15T10:30:00Z",
  "priority": "normal"
}
```

### POST /api/v3/schedule/render/{task_id}
Start background rendering for a registered task.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "scheduled",
  "message": "Background rendering started. Use GET /schedule/status/{task_id} to check progress."
}
```

### GET /api/v3/schedule/status/{task_id}
Get status of a scheduled task.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "file_path": "outputs/v3_task_abc12345.wav",
  "audio_url": "/api/v3/audio/v3_task_abc12345.wav",
  "progress": 1.0,
  "duration": 3.2,
  "synthesis_time": 1.1,
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:01Z",
  "completed_at": "2024-01-15T10:30:02Z",
  "priority": "normal"
}
```

**Status Values:**
- `pending`: Task registered, waiting for render to start
- `scheduled`: Task added to render queue
- `processing`: Currently rendering
- `completed`: Rendering done, audio ready for download
- `failed`: Rendering failed (check error_message)
- `cancelled`: Task was cancelled

### GET /api/v3/schedule/tasks
List all scheduled tasks with optional filters.

**Query Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| limit | int | No | Max tasks to return (default: 50) |
| status | string | No | Filter by status |
| priority | string | No | Filter by priority |

### DELETE /api/v3/schedule/task/{task_id}
Cancel or delete a scheduled task.

### POST /api/v3/schedule/render-all
Start rendering for all pending tasks (batch processing).

**Query Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| max_tasks | int | No | Max tasks to render (default: 10) |

### GET /api/v3/schedule/queue-stats
Get queue statistics.

**Response:**
```json
{
  "total_tasks": 15,
  "status_counts": {
    "pending": 5,
    "processing": 2,
    "completed": 8
  },
  "priority_counts": {
    "normal": 10,
    "high": 5
  },
  "average_synthesis_time": 1.234,
  "completed_tasks": 8
}
```

---

## Streaming Synthesis

### POST /api/v3/streaming/cross-lingual
HTTP streaming synthesis.

**Content-Type:** `multipart/form-data`

**Request Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| text | string | Yes | Text to synthesize |
| voice_id | string | Yes | Cached voice ID |
| format | enum | No | Audio format (default: `wav`) |
| speed | float | No | Speech speed (default: 1.0) |
| quality | enum | No | `low`, `medium`, `high` (default: `medium`) |
| chunk_size | int | No | Chunk size 256-8192 bytes (default: 1024) |

**Response:** Streaming audio data with chunked transfer encoding.

**Quality Settings:**

| Quality | Sample Rate | Chunk Duration |
|---------|-------------|----------------|
| low | 16000 Hz | 0.5s |
| medium | 22050 Hz | 0.3s |
| high | 44100 Hz | 0.2s |

### GET /api/v3/streaming/cross-lingual/sse
Server-Sent Events streaming.

**Query Parameters:** Same as above

**Response:** SSE stream with events:
- `start`: Synthesis started
- `audio_chunk`: Audio data (base64 encoded)
- `complete`: Synthesis finished
- `error`: Error occurred

### GET /api/v3/streaming/health
Streaming service health check.

---

## WebSocket Streaming

### WS /api/v3/ws/stream
Bidirectional WebSocket streaming.

**Connection URL:** `ws://localhost:8012/api/v3/ws/stream?client_id=optional_id`

**Message Types:**

#### Client → Server: Text Request
```json
{
  "message_type": "text_request",
  "request_id": "unique_id",
  "text": "Text to synthesize",
  "voice_id": "my_voice_01",
  "format": "wav",
  "speed": 1.0,
  "quality": "medium"
}
```

#### Server → Client: Synthesis Start
```json
{
  "message_type": "synthesis_start",
  "request_id": "unique_id",
  "timestamp": 1705312200.123,
  "text": "Text to synthesize",
  "voice_id": "my_voice_01"
}
```

#### Server → Client: Audio Chunk
```json
{
  "message_type": "audio_chunk",
  "request_id": "unique_id",
  "timestamp": 1705312200.456,
  "audio_data": "base64_encoded_audio_data",
  "metadata": {
    "chunk_index": 1,
    "chunk_size": 1024,
    "sample_rate": 22050,
    "channels": 1,
    "is_final": false
  }
}
```

#### Server → Client: Synthesis Complete
```json
{
  "message_type": "synthesis_complete",
  "request_id": "unique_id",
  "timestamp": 1705312201.789,
  "total_chunks": 15,
  "total_duration": 3.2,
  "synthesis_time": 1.1
}
```

#### Ping/Pong
```json
// Client sends
{"message_type": "ping", "request_id": "ping_1"}

// Server responds
{"message_type": "pong", "request_id": "ping_1", "timestamp": 1705312200.123}
```

### GET /api/v3/ws/sessions
Liệt kê active WebSocket sessions.

---

## Audio Files

### GET /api/v3/audio/{filename}
Download generated audio file.

**Response:** Audio file with appropriate Content-Type.

---

## Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Voice/Task not found |
| 409 | Conflict - Voice already exists |
| 422 | Unprocessable Entity - Invalid audio file |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Model not ready |

---

## Integration Examples

### Python
```python
import requests

# Create voice
files = {'audio_file': open('sample.wav', 'rb')}
data = {
    'voice_id': 'my_voice',
    'name': 'My Voice',
    'voice_type': 'cross_lingual'
}
response = requests.post('http://localhost:8012/api/v3/voices/', files=files, data=data)

# Synthesize with cached voice
response = requests.post('http://localhost:8012/api/v3/cross-lingual/with-cache', json={
    'text': 'Hello world',
    'voice_id': 'my_voice'
})
audio_url = response.json()['audio_url']

# Download audio
audio = requests.get(f'http://localhost:8012{audio_url}')
with open('output.wav', 'wb') as f:
    f.write(audio.content)
```

### JavaScript/TypeScript
```typescript
// Create voice
const formData = new FormData();
formData.append('voice_id', 'my_voice');
formData.append('name', 'My Voice');
formData.append('voice_type', 'cross_lingual');
formData.append('audio_file', audioFile);

const response = await fetch('http://localhost:8012/api/v3/voices/', {
  method: 'POST',
  body: formData
});

// Synthesize
const synthesisResponse = await fetch('http://localhost:8012/api/v3/cross-lingual/with-cache', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: 'Hello world',
    voice_id: 'my_voice'
  })
});

const { audio_url } = await synthesisResponse.json();

// WebSocket streaming
const ws = new WebSocket('ws://localhost:8012/api/v3/ws/stream');
ws.onopen = () => {
  ws.send(JSON.stringify({
    message_type: 'text_request',
    request_id: 'req_1',
    text: 'Hello world',
    voice_id: 'my_voice'
  }));
};
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.message_type === 'audio_chunk') {
    // Process audio chunk
  }
};
```

### cURL
```bash
# Health check
curl http://localhost:8012/health

# Create voice
curl -X POST http://localhost:8012/api/v3/voices/ \
  -F "voice_id=my_voice" \
  -F "name=My Voice" \
  -F "voice_type=cross_lingual" \
  -F "audio_file=@sample.wav"

# Synthesize
curl -X POST http://localhost:8012/api/v3/cross-lingual/with-cache \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice_id": "my_voice"}'

# Download audio
curl -O http://localhost:8012/api/v3/audio/v3_cache_abc12345.wav
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| HOST | 0.0.0.0 | Server host |
| PORT | 8012 | Server port |
| DEBUG | false | Debug mode |
| MODEL_DIR | models/CosyVoice2-0.5B | CosyVoice2 model path |
| MODEL_DIR_V3 | models/Fun-CosyVoice3-0.5B | CosyVoice3 model path |
| AUTO_DOWNLOAD_MODELS | true | Auto-download from HuggingFace |
| VOICE_CACHE_DIR | voice_cache | Voice cache directory |
| MAX_TEXT_LENGTH | 1000 | Max text length |
| MAX_AUDIO_DURATION | 30 | Max audio duration (seconds) |
| SAMPLE_RATE | 22050 | Default sample rate |

---

## OpenAPI Schema

Full OpenAPI 3.0 schema available at:
- **Swagger UI**: http://localhost:8012/docs
- **ReDoc**: http://localhost:8012/redoc
- **OpenAPI JSON**: http://localhost:8012/openapi.json
