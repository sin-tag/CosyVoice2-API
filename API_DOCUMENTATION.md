# Voice Fast Service — API Documentation

> Base URL: `http://your-server:8010`
> Authentication: `X-Api-Key` header on all endpoints (except `/health`)

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Health & Status](#2-health--status)
3. [TTS — Synchronous Generation](#3-tts--synchronous-generation)
4. [TTS — SSE Streaming](#4-tts--sse-streaming)
5. [TTS — Async Task Queue](#5-tts--async-task-queue)
6. [Comic Dubbing](#6-comic-dubbing)
7. [Voice Management](#7-voice-management)
8. [Generation History](#8-generation-history)
9. [WebSocket Real-Time TTS](#9-websocket-real-time-tts)
10. [Error Format](#10-error-format)
11. [Generation Parameters](#11-generation-parameters)

---

## 1. Authentication

All endpoints (except `GET /health`) require an API key via header:

```
X-Api-Key: your-api-key
```

WebSocket uses query parameter:

```
ws://host:8010/ws/tts/qwen?api_key=your-api-key
```

**Error on invalid key:**
```json
{"error": "http_error", "message": "Invalid API key"}
```

---

## 2. Health & Status

### `GET /health`

No authentication required. Returns server status, engine info, GPU slots, and task queue state.

```bash
curl http://localhost:8010/health
```

**Response:**
```json
{
  "status": "ok",
  "engines": [
    {
      "name": "qwen",
      "loaded": true,
      "languages": ["zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"],
      "cached_voices": 3,
      "gpu_slots": {
        "free": 4, "total": 4, "busy": 0, "gpus": 2,
        "per_gpu": [
          {"device": "cuda:0", "free": 2, "total": 2},
          {"device": "cuda:1", "free": 2, "total": 2}
        ]
      }
    }
  ],
  "concurrency": {
    "max_requests": 50,
    "gpu_slots": { "qwen": { "free": 4, "total": 4, "busy": 0, "gpus": 2 } }
  },
  "queue": {
    "pending": 3,
    "processing": 2,
    "max_queue_size": 100,
    "gpus": [
      {"gpu_id": 0, "device": "cuda:0", "active_tasks": 1, "total_completed": 142},
      {"gpu_id": 1, "device": "cuda:1", "active_tasks": 1, "total_completed": 138}
    ]
  }
}
```

---

## 3. TTS — Synchronous Generation

### `POST /api/v1/tts/qwen/generate`

Returns JSON metadata with synthesis info.

```bash
curl -X POST http://localhost:8010/api/v1/tts/qwen/generate \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, world! This is a voice cloning test.",
    "language": "en",
    "voice_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | — | Text to synthesize (max 5000 chars) |
| `language` | string | Yes | — | ISO code: en, zh, ja, ko, de, fr, ru, pt, es, it |
| `voice_id` | UUID | No | null | Reference voice for cloning |
| `temperature` | float | No | 0.7 | Creativity (0.0–2.0) |
| `top_p` | float | No | 0.9 | Nucleus sampling (0.0–1.0) |
| `top_k` | int | No | 50 | Top-K sampling (1–500) |
| `repetition_penalty` | float | No | 1.2 | Repetition penalty (1.0–3.0) |
| `output_format` | string | No | "wav" | "wav" or "pcm" |

**Response:**
```json
{
  "success": true,
  "message": "Synthesis completed",
  "audio_url": "/api/v1/tts/audio/history-uuid",
  "duration": 3.25,
  "format": "wav",
  "synthesis_time": 1.234,
  "sample_rate": 24000,
  "history_id": "history-uuid",
  "gpu_slots_free": 3,
  "gpu_slots_total": 4
}
```

### `POST /api/v1/tts/qwen/generate/audio`

Same request body. Returns **raw WAV bytes** for direct playback.

```bash
curl -X POST http://localhost:8010/api/v1/tts/qwen/generate/audio \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "language": "en", "voice_id": "uuid"}' \
  --output output.wav
```

**Response Headers:**
```
Content-Type: audio/wav
X-History-Id: history-uuid
X-Sample-Rate: 24000
X-GPU-Slots-Free: 3
X-GPU-Slots-Total: 4
```

### `GET /api/v1/tts/engines`

List all loaded engines.

```bash
curl -H "X-Api-Key: your-key" http://localhost:8010/api/v1/tts/engines
```

### `GET /api/v1/tts/qwen/languages`

```json
{"engine": "qwen", "languages": ["zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"]}
```

---

## 4. TTS — SSE Streaming

### `POST /api/v1/tts/qwen/stream`

Server-Sent Events stream. Audio delivered in real-time chunks.

```bash
curl -N -X POST http://localhost:8010/api/v1/tts/qwen/stream \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Streaming audio test", "language": "en", "voice_id": "uuid"}'
```

**SSE Event Sequence:**

1. `synthesis_start` — Confirms generation started
```json
{"text": "Streaming audio...", "voice_id": "uuid", "language": "en", "sample_rate": 24000}
```

2. `audio_chunk` — Repeats for each chunk (base64 PCM16)
```json
{
  "audio_data": "base64_pcm16...",
  "chunk_index": 0,
  "chunk_size": 4096,
  "sample_rate": 24000,
  "is_final": false
}
```

3. `synthesis_complete` — Final summary
```json
{
  "history_id": "uuid",
  "total_chunks": 12,
  "duration": 3.25,
  "synthesis_time": 2.145,
  "latency_ms": 97,
  "gpu_slots_free": 3,
  "gpu_slots_total": 4
}
```

4. `error` — On failure
```json
{"error": "gpu_queue_full", "message": "GPU queue full — try again later"}
```

---

## 5. TTS — Async Task Queue

When GPU is busy, tasks queue as `pending` and process when a GPU frees up.

### `POST /api/v1/tasks/tts/qwen` — Submit task

```bash
curl -X POST http://localhost:8010/api/v1/tasks/tts/qwen \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Queued task", "language": "en", "voice_id": "uuid"}'
```

**Response:**
```json
{
  "task_id": "task_a1b2c3d4e5f6",
  "status": "pending",
  "queue_position": 2,
  "message": "Queued (position 2)",
  "gpu_id": null,
  "check_status_url": "/api/v1/tasks/task_a1b2c3d4e5f6"
}
```

### `GET /api/v1/tasks/{task_id}` — Poll status

```bash
curl -H "X-Api-Key: your-key" http://localhost:8010/api/v1/tasks/task_a1b2c3d4e5f6
```

**Pending:**
```json
{"task_id": "task_abc", "status": "pending", "queue_position": 1, "gpu_id": null}
```

**Processing:**
```json
{"task_id": "task_abc", "status": "processing", "gpu_id": 0, "message": "Processing on cuda:0..."}
```

**Completed:**
```json
{
  "task_id": "task_abc",
  "status": "completed",
  "gpu_id": 1,
  "message": "Completed on cuda:1",
  "audio_url": "/api/v1/tasks/task_abc/audio",
  "history_id": "uuid",
  "duration": 3.25,
  "sample_rate": 24000
}
```

**Failed:**
```json
{"task_id": "task_abc", "status": "failed", "gpu_id": 0, "error_message": "Generation timed out"}
```

### `GET /api/v1/tasks/{task_id}/audio` — Download result

```bash
curl -H "X-Api-Key: your-key" \
  http://localhost:8010/api/v1/tasks/task_a1b2c3d4e5f6/audio \
  --output result.wav
```

Returns WAV bytes. Only available when `status = "completed"`.

### `GET /api/v1/tasks` — List all tasks

```bash
curl -H "X-Api-Key: your-key" "http://localhost:8010/api/v1/tasks?status=pending&limit=20"
```

| Query Param | Type | Default | Description |
|-------------|------|---------|-------------|
| `status` | string | null | Filter: pending, processing, completed, failed |
| `limit` | int | 50 | Max results (1–200) |

---

## 6. Comic Dubbing

Generate multi-speaker dubbed audio for comics/stories. Upload voice reference audio for each speaker. Each segment is synthesized individually with voice cloning, then concatenated.

### `POST /api/v1/comic/dub` — JSON response

```bash
curl -X POST http://localhost:8010/api/v1/comic/dub \
  -H "X-Api-Key: your-key" \
  -F 'script=[
    {"speaker":"narrator","text":"In a dark night, a figure appeared..."},
    {"speaker":"char1","text":"Stop! Who goes there?"},
    {"speaker":"char2","text":"Just a traveler, nothing more."},
    {"speaker":"narrator","text":"The stranger stepped into the light..."},
    {"speaker":"char1","text":"State your name!"}
  ]' \
  -F language=en \
  -F temperature=0.7 \
  -F narrator=@narrator_voice.wav \
  -F char1=@hero_voice.wav \
  -F char2=@villain_voice.wav
```

**Form Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `script` | JSON string | Yes | — | Array of `{speaker, text}` segments |
| `language` | string | No | "en" | Language code |
| `temperature` | float | No | 0.7 | Creativity |
| `top_p` | float | No | 0.9 | Nucleus sampling |
| `top_k` | int | No | 50 | Top-K sampling |
| `repetition_penalty` | float | No | 1.2 | Repetition penalty |
| `narrator` | file | If used | — | Narrator voice reference WAV |
| `char1` | file | If used | — | Character 1 voice reference WAV |
| `char2` | file | If used | — | Character 2 voice reference WAV |
| `char3` | file | If used | — | Character 3 voice reference WAV |
| `char4` | file | If used | — | Character 4 voice reference WAV |

**Script format:**
```json
[
  {"speaker": "narrator", "text": "Narration text (max 2000 chars)"},
  {"speaker": "char1", "text": "Character dialogue"}
]
```

> Speaker names must match uploaded file field names. Max 5 speakers.

**Response:**
```json
{
  "success": true,
  "message": "Comic dubbing completed: 5 segments, 3 speakers",
  "audio_url": "/api/v1/comic/audio/history-uuid",
  "duration": 18.5,
  "synthesis_time": 12.3,
  "sample_rate": 24000,
  "history_id": "history-uuid",
  "speakers": ["narrator", "char1", "char2"],
  "segments_count": 5,
  "gpu_slots_free": 3,
  "gpu_slots_total": 4
}
```

### `POST /api/v1/comic/dub/audio` — Raw WAV response

Same form fields. Returns raw WAV bytes directly.

```bash
curl -X POST http://localhost:8010/api/v1/comic/dub/audio \
  -H "X-Api-Key: your-key" \
  -F 'script=[{"speaker":"narrator","text":"Once upon a time..."}]' \
  -F language=en \
  -F narrator=@voice.wav \
  --output comic_output.wav
```

---

## 7. Voice Management

Upload and manage voice profiles for voice cloning.

### `POST /api/v1/voices` — Upload voice

```bash
curl -X POST http://localhost:8010/api/v1/voices \
  -H "X-Api-Key: your-key" \
  -F "name=Hero Voice" \
  -F "language=en" \
  -F "description=Male hero character" \
  -F "reference_text=Sample text spoken in the audio" \
  -F "reference_audio=@voice_sample.wav"
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Hero Voice",
  "description": "Male hero character",
  "language": "en",
  "reference_text": "Sample text spoken in the audio",
  "audio_duration_sec": 5.2,
  "moss_compatible": true,
  "qwen_compatible": true,
  "moss_cached": false,
  "qwen_cached": true,
  "is_default": false,
  "created_at": "2026-03-23T10:30:00Z",
  "updated_at": "2026-03-23T10:30:00Z"
}
```

> Audio must be 1–30 seconds. Qwen requires minimum 3 seconds.

### `GET /api/v1/voices` — List voices

```bash
curl -H "X-Api-Key: your-key" "http://localhost:8010/api/v1/voices?page=1&page_size=20&language=en"
```

| Query Param | Type | Default | Description |
|-------------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (1–100) |
| `language` | string | null | Filter by language |
| `engine` | string | null | Filter by engine compatibility |

### `GET /api/v1/voices/{voice_id}` — Get voice details

### `PUT /api/v1/voices/{voice_id}` — Update voice metadata

```bash
curl -X PUT http://localhost:8010/api/v1/voices/uuid \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Name", "description": "New description"}'
```

### `DELETE /api/v1/voices/{voice_id}` — Delete voice

Returns `204 No Content`.

---

## 8. Generation History

### `GET /api/v1/history` — List history

```bash
curl -H "X-Api-Key: your-key" "http://localhost:8010/api/v1/history?engine=qwen&page=1"
```

| Query Param | Type | Default | Description |
|-------------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (1–100) |
| `engine` | string | null | Filter by engine |
| `voice_id` | UUID | null | Filter by voice |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "voice_id": "voice-uuid",
      "engine": "qwen",
      "text": "Hello world",
      "language": "en",
      "parameters": {"temperature": 0.7, "top_p": 0.9},
      "audio_duration_sec": 3.25,
      "latency_ms": 97,
      "total_time_ms": 1234,
      "sample_rate": 24000,
      "status": "completed",
      "error_message": null,
      "created_at": "2026-03-23T10:30:00Z"
    }
  ],
  "total": 245,
  "page": 1,
  "page_size": 20
}
```

### `GET /api/v1/history/{history_id}` — Get record

### `DELETE /api/v1/history/{history_id}` — Delete record (204)

---

## 9. WebSocket Real-Time TTS

Full-duplex streaming with binary PCM16 audio frames.

### `WS /ws/tts/qwen?api_key=your-key`

**Step 1: Connect**
```javascript
const ws = new WebSocket("ws://localhost:8010/ws/tts/qwen?api_key=your-key");
```

**Step 2: Send config**
```json
{
  "text": "Hello, streaming world!",
  "language": "en",
  "voice_id": "uuid-or-null",
  "request_id": "req-001",
  "temperature": 0.7,
  "top_p": 0.9,
  "top_k": 50,
  "repetition_penalty": 1.2
}
```

**Step 3: Receive messages**

| message_type | Format | Description |
|-------------|--------|-------------|
| `synthesis_start` | JSON | Confirms synthesis began |
| `audio_chunk` | JSON + Binary | Metadata then PCM16 bytes |
| `synthesis_complete` | JSON | Final summary with history_id, duration |
| `error` | JSON | Error with error_code + error_message |

**audio_chunk flow:** Server sends JSON metadata, then binary PCM16 frame.

```
← JSON: {"message_type": "audio_chunk", "chunk_index": 0, "chunk_size": 4096, ...}
← Binary: <4096 bytes PCM16 little-endian mono 24kHz>
← JSON: {"message_type": "audio_chunk", "chunk_index": 1, ...}
← Binary: <PCM16 bytes>
...
← JSON: {"message_type": "synthesis_complete", "duration": 3.25, ...}
```

**JavaScript Example:**
```javascript
const ws = new WebSocket("ws://localhost:8010/ws/tts/qwen?api_key=my-key");
const audioChunks = [];

ws.onopen = () => {
  ws.send(JSON.stringify({
    text: "Generate this audio in real time",
    language: "en",
    voice_id: "voice-uuid"
  }));
};

ws.onmessage = (event) => {
  if (event.data instanceof Blob) {
    // Binary PCM16 audio frame
    audioChunks.push(event.data);
  } else {
    const msg = JSON.parse(event.data);
    switch (msg.message_type) {
      case "synthesis_start":
        console.log("Started, sample_rate:", msg.sample_rate);
        break;
      case "audio_chunk":
        console.log("Chunk", msg.chunk_index, "size:", msg.chunk_size);
        break;
      case "synthesis_complete":
        console.log("Done!", msg.duration, "seconds");
        break;
      case "error":
        console.error(msg.error_code, msg.error_message);
        break;
    }
  }
};
```

**Python Example:**
```python
import asyncio
import json
import websockets

async def stream_tts():
    uri = "ws://localhost:8010/ws/tts/qwen?api_key=my-key"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "text": "Hello from Python",
            "language": "en",
            "voice_id": "voice-uuid",
        }))

        audio_data = bytearray()
        async for message in ws:
            if isinstance(message, bytes):
                audio_data.extend(message)
            else:
                msg = json.loads(message)
                if msg["message_type"] == "synthesis_complete":
                    print(f"Done: {msg['duration']}s")
                    break

        # Save raw PCM16 (24kHz, mono, 16-bit LE)
        with open("output.pcm", "wb") as f:
            f.write(audio_data)

asyncio.run(stream_tts())
```

---

## 10. Error Format

All errors follow a consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": { ... }
}
```

**Common Error Codes:**

| Code | HTTP Status | Description |
|------|------------|-------------|
| `validation_error` | 422 | Invalid request parameters |
| `http_error` | 401 | Invalid API key |
| `voice_not_found` | 404 | Voice ID doesn't exist |
| `voice_not_compatible` | 400 | Voice incompatible with engine |
| `unsupported_language` | 400 | Language not supported |
| `engine_not_loaded` | 503 | Engine not available |
| `generation_timeout` | 504 | Generation took too long |
| `gpu_oom` | 503 | GPU out of memory |
| `access_denied` | 403 | IP not whitelisted |
| `server_busy` | 503 | Too many concurrent requests |
| `task_not_found` | 404 | Task ID doesn't exist |
| `missing_voice_file` | 400 | Comic dub: missing speaker audio |
| `invalid_script` | 400 | Comic dub: malformed script JSON |

---

## 11. Generation Parameters

All TTS endpoints accept these optional parameters:

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `temperature` | 0.7 | 0.0–2.0 | Higher = more variation, lower = more stable |
| `top_p` | 0.9 | 0.0–1.0 | Nucleus sampling cutoff |
| `top_k` | 50 | 1–500 | Top-K sampling limit |
| `repetition_penalty` | 1.2 | 1.0–3.0 | Penalize repeated patterns |

**Audio Output:**
- Sample rate: 24000 Hz
- Format: PCM16 (16-bit signed, little-endian)
- Channels: Mono
- Supported languages: zh, en, ja, ko, de, fr, ru, pt, es, it
