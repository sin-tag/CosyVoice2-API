# Voice Fast Service — API Documentation (OmniVoice)

> **Engine:** [k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) — 600+ languages, zero-shot voice cloning, RTF ~0.15
> **Base URL:** `http://your-server:8010`
> **Auth:** `X-Api-Key` header on all endpoints (except `/health`)
> **Audio Output:** WAV, 24kHz, mono, PCM16

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Health & Status](#2-health--status)
3. [TTS — Synchronous Generation](#3-tts--synchronous-generation)
4. [TTS — Async Task Queue](#4-tts--async-task-queue)
5. [Comic Dubbing (Multi-Speaker)](#5-comic-dubbing-multi-speaker)
6. [Voice Management](#6-voice-management)
7. [Generation History](#7-generation-history)
8. [WebSocket Real-Time TTS](#8-websocket-real-time-tts)
9. [SSE Streaming](#9-sse-streaming)
10. [Error Codes](#10-error-codes)

---

## 1. Authentication

**HTTP endpoints** — header:
```
X-Api-Key: your-api-key
```

**WebSocket** — query parameter:
```
ws://host:8010/ws/tts/omni?api_key=your-api-key
```

---

## 2. Health & Status

### `GET /health`

No auth required. Check server status, GPU load, and task queue.

```bash
curl http://localhost:8010/health
```

```json
{
  "status": "ok",
  "engines": [{
    "name": "omni",
    "loaded": true,
    "languages": ["en", "zh", "ja", "ko", "de", "fr", "ru", "pt", "es", "it", ...],
    "cached_voices": 3,
    "gpu_slots": {
      "free": 2, "total": 2, "busy": 0, "gpus": 1,
      "per_gpu": [{"device": "cuda:0", "free": 2, "total": 2}]
    }
  }],
  "concurrency": {"max_requests": 50, "gpu_slots": {"omni": {"free": 2, "total": 2}}},
  "queue": {
    "pending": 0, "processing": 0, "max_queue_size": 100,
    "gpus": [{"gpu_id": 0, "device": "cuda:0", "active_tasks": 0, "total_completed": 42}]
  }
}
```

---

## 3. TTS — Synchronous Generation

### `POST /api/v1/tts/omni/generate` — JSON response

```bash
curl -X POST http://localhost:8010/api/v1/tts/omni/generate \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world, this is a voice cloning test.",
    "language": "en",
    "voice_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | — | Text to synthesize (max 5000 chars) |
| `language` | string | Yes | — | ISO code: en, zh, ja, ko, de, fr, ru, pt, es, it, vi, th, ar, hi, ... (600+ supported) |
| `voice_id` | UUID | Yes | — | Voice ID from `/api/v1/voices` |
| `temperature` | float | No | 0.7 | Creativity (0.0–2.0) |
| `top_p` | float | No | 0.9 | Nucleus sampling (0.0–1.0) |
| `top_k` | int | No | 50 | Top-K sampling (1–500) |
| `repetition_penalty` | float | No | 1.2 | Repetition penalty (1.0–3.0) |
| `output_format` | string | No | "wav" | "wav" or "pcm" |

> **Note:** `voice_id` is required. Upload a voice first via `POST /api/v1/voices`.
> Reference audio can be a **local file** or a **URL** (auto-downloaded).
> If no `reference_text` was provided when uploading the voice, a default is used automatically.
> Reference audio longer than 5s is auto-trimmed.

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
  "gpu_slots_free": 1,
  "gpu_slots_total": 2
}
```

### `POST /api/v1/tts/omni/generate/audio` — Raw WAV response

Same request body. Returns **binary WAV** for direct playback.

```bash
curl -X POST http://localhost:8010/api/v1/tts/omni/generate/audio \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "language": "en", "voice_id": "uuid"}' \
  --output output.wav
```

**Response Headers:**
```
Content-Type: audio/wav
X-History-Id: uuid
X-Sample-Rate: 24000
X-GPU-Slots-Free: 1
X-GPU-Slots-Total: 2
```

### `GET /api/v1/tts/engines` — List engines

```json
[{"name": "omni", "loaded": true, "languages": ["en", "zh", ...], "cached_voices": 3, "gpu_slots": {...}}]
```

### `GET /api/v1/tts/omni/languages` — Supported languages

```json
{"engine": "omni", "languages": ["en", "zh", "ja", "ko", "de", "fr", "ru", "pt", "es", "it", "ar", "hi", "vi", "th", "pl", "nl", "sv", "da", "fi", "no"]}
```

> OmniVoice supports 600+ languages. The list above shows the top 20. Pass any valid ISO 639-1 code.

---

## 4. TTS — Async Task Queue

When GPU is busy, tasks queue as `pending` instead of being rejected. Poll status to get result.

### `POST /api/v1/tasks/tts/omni` — Submit task

```bash
curl -X POST http://localhost:8010/api/v1/tasks/tts/omni \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Generate this in background", "language": "en", "voice_id": "uuid"}'
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

**Status lifecycle:** `pending` → `processing` → `completed` / `failed`

```json
// pending
{"task_id": "task_abc", "status": "pending", "queue_position": 1, "gpu_id": null}

// processing
{"task_id": "task_abc", "status": "processing", "gpu_id": 0, "message": "Processing on cuda:0..."}

// completed
{
  "task_id": "task_abc",
  "status": "completed",
  "gpu_id": 0,
  "message": "Completed on cuda:0",
  "audio_url": "/api/v1/tasks/task_abc/audio",
  "history_id": "uuid",
  "duration": 3.25,
  "sample_rate": 24000
}

// failed
{"task_id": "task_abc", "status": "failed", "gpu_id": 0, "error_message": "Generation timed out"}
```

### `GET /api/v1/tasks/{task_id}/audio` — Download result

```bash
curl -H "X-Api-Key: your-key" http://localhost:8010/api/v1/tasks/task_abc/audio --output result.wav
```

Only available when `status = "completed"`.

### `GET /api/v1/tasks` — List tasks

```bash
curl -H "X-Api-Key: your-key" "http://localhost:8010/api/v1/tasks?status=pending&limit=20"
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | null | Filter: pending, processing, completed, failed |
| `limit` | int | 50 | Max results (1–200) |

---

## 5. Comic Dubbing (Multi-Speaker)

Generate multi-speaker dubbed audio for comics/stories. Each segment is generated with voice cloning, then concatenated with 0.3s silence between segments.

**Three ways to provide voices (can mix):**
1. **Upload file:** `narrator=@voice.wav`
2. **Voice ID from DB:** `voice_ids={"narrator":"uuid"}`
3. **Mix both:** file for some speakers, ID for others

### `POST /api/v1/comic/dub` — JSON response

**Example 1: Upload audio files**
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
  -F narrator=@narrator_voice.wav \
  -F char1=@hero_voice.wav \
  -F char2=@villain_voice.wav
```

**Example 2: Use voice IDs from database**
```bash
curl -X POST http://localhost:8010/api/v1/comic/dub \
  -H "X-Api-Key: your-key" \
  -F 'script=[
    {"speaker":"narrator","text":"In a dark night..."},
    {"speaker":"char1","text":"Stop!"},
    {"speaker":"char2","text":"Just a traveler."}
  ]' \
  -F 'voice_ids={"narrator":"550e8400-uuid","char1":"660e8400-uuid","char2":"770e8400-uuid"}' \
  -F language=en
```

**Example 3: Mix (narrator from file, characters from DB)**
```bash
curl -X POST http://localhost:8010/api/v1/comic/dub \
  -H "X-Api-Key: your-key" \
  -F 'script=[{"speaker":"narrator","text":"..."},{"speaker":"char1","text":"..."}]' \
  -F 'voice_ids={"char1":"660e8400-uuid"}' \
  -F language=en \
  -F narrator=@narrator_voice.wav
```

**Form Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `script` | JSON string | Yes | — | `[{"speaker":"name","text":"..."},...]` |
| `voice_ids` | JSON string | No | null | `{"speaker":"voice-uuid-from-db"}` |
| `language` | string | No | "en" | Language code |
| `temperature` | float | No | 0.7 | Creativity |
| `top_p` | float | No | 0.9 | Nucleus sampling |
| `top_k` | int | No | 50 | Top-K sampling |
| `repetition_penalty` | float | No | 1.2 | Repetition penalty |
| `narrator` | file | No | — | Narrator voice WAV/MP3 |
| `char1` | file | No | — | Character 1 voice WAV/MP3 |
| `char2` | file | No | — | Character 2 voice WAV/MP3 |
| `char3` | file | No | — | Character 3 voice WAV/MP3 |
| `char4` | file | No | — | Character 4 voice WAV/MP3 |

> Each speaker in script must have either an uploaded file OR a voice_id. Max 5 speakers.
> Audio files longer than 5s are auto-trimmed.
> Voice IDs with `reference_text` in DB produce better quality.

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
  "gpu_slots_free": 1,
  "gpu_slots_total": 2
}
```

### `POST /api/v1/comic/dub/audio` — Raw WAV response

Same form fields. Returns binary WAV directly.

```bash
curl -X POST http://localhost:8010/api/v1/comic/dub/audio \
  -H "X-Api-Key: your-key" \
  -F 'script=[{"speaker":"narrator","text":"Once upon a time..."}]' \
  -F 'voice_ids={"narrator":"550e8400-uuid"}' \
  -F language=en \
  --output comic_output.wav
```

**Response Headers:**
```
Content-Type: audio/wav
X-History-Id: uuid
X-Sample-Rate: 24000
X-Duration: 18.5
X-GPU-Slots-Free: 1
X-GPU-Slots-Total: 2
```

---

## 6. Voice Management

Upload and manage voice profiles for voice cloning. Voices are cached in memory for fast lookup.

### `POST /api/v1/voices` — Upload voice

```bash
curl -X POST http://localhost:8010/api/v1/voices \
  -H "X-Api-Key: your-key" \
  -F "name=Hero Voice" \
  -F "language=en" \
  -F "description=Male hero character" \
  -F "reference_text=Sample text spoken in the audio file" \
  -F "reference_audio=@voice_sample.wav"
```

> `reference_text`: transcript of what is spoken in the audio. Improves cloning quality. If omitted, a default is used.
> Audio must be 1–30 seconds. Recommended: 3–5 seconds.

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Hero Voice",
  "description": "Male hero character",
  "language": "en",
  "reference_text": "Sample text spoken in the audio file",
  "audio_duration_sec": 5.2,
  "moss_compatible": true,
  "qwen_compatible": true,
  "moss_cached": false,
  "qwen_cached": true,
  "is_default": false,
  "created_at": "2026-04-03T10:30:00Z",
  "updated_at": "2026-04-03T10:30:00Z"
}
```

### `GET /api/v1/voices` — List voices

```bash
curl -H "X-Api-Key: your-key" "http://localhost:8010/api/v1/voices?page=1&page_size=20&language=en"
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (1–100) |
| `language` | string | null | Filter by language |
| `engine` | string | null | Filter by engine compatibility |

**Response:**
```json
{
  "items": [
    {"id": "uuid", "name": "Hero Voice", "language": "en", "audio_duration_sec": 5.2, ...}
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

### `GET /api/v1/voices/{voice_id}` — Get voice detail

### `PUT /api/v1/voices/{voice_id}` — Update metadata

```bash
curl -X PUT http://localhost:8010/api/v1/voices/uuid \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Name", "description": "Updated"}'
```

### `DELETE /api/v1/voices/{voice_id}` — Delete voice (204)

---

## 7. Generation History

### `GET /api/v1/history` — List history

```bash
curl -H "X-Api-Key: your-key" "http://localhost:8010/api/v1/history?page=1&page_size=20"
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
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
      "engine": "omni",
      "text": "Hello world",
      "language": "en",
      "audio_duration_sec": 3.25,
      "total_time_ms": 1234,
      "status": "completed",
      "created_at": "2026-04-03T10:30:00Z"
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

## 8. WebSocket Real-Time TTS

### `WS /ws/tts/omni?api_key=your-key`

**Step 1: Connect**
```javascript
const ws = new WebSocket("ws://localhost:8010/ws/tts/omni?api_key=your-key");
```

**Step 2: Send config (JSON)**
```json
{
  "text": "Hello, streaming world!",
  "language": "en",
  "voice_id": "uuid",
  "request_id": "req-001"
}
```

**Step 3: Receive messages**

Server sends alternating JSON metadata + binary PCM16 audio:

```
← JSON: {"message_type": "synthesis_start", "sample_rate": 24000, ...}
← JSON: {"message_type": "audio_chunk", "chunk_index": 0, "chunk_size": 4096, ...}
← Binary: <PCM16 bytes, 24kHz mono 16-bit LE>
← JSON: {"message_type": "audio_chunk", "chunk_index": 1, ...}
← Binary: <PCM16 bytes>
...
← JSON: {"message_type": "synthesis_complete", "duration": 3.25, "history_id": "uuid", ...}
```

**Message Types:**

| message_type | Description |
|-------------|-------------|
| `synthesis_start` | Confirms synthesis began, includes `sample_rate` |
| `audio_chunk` | Metadata for next binary frame: `chunk_index`, `chunk_size` |
| `synthesis_complete` | Done: `history_id`, `duration`, `synthesis_time`, `gpu_slots_free` |
| `error` | Error: `error_code`, `error_message` |

**Python Client Example:**
```python
import asyncio, json, websockets

async def tts():
    async with websockets.connect("ws://localhost:8010/ws/tts/omni?api_key=my-key") as ws:
        await ws.send(json.dumps({"text": "Hello", "language": "en", "voice_id": "uuid"}))

        audio = bytearray()
        async for msg in ws:
            if isinstance(msg, bytes):
                audio.extend(msg)
            else:
                data = json.loads(msg)
                if data["message_type"] == "synthesis_complete":
                    print(f"Done: {data['duration']}s")
                    break

        with open("output.pcm", "wb") as f:
            f.write(audio)

asyncio.run(tts())
```

---

## 9. SSE Streaming

### `POST /api/v1/tts/omni/stream`

Server-Sent Events stream with base64 audio chunks.

```bash
curl -N -X POST http://localhost:8010/api/v1/tts/omni/stream \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Streaming test", "language": "en", "voice_id": "uuid"}'
```

**Event sequence:**

1. `synthesis_start`
```json
{"text": "Streaming...", "voice_id": "uuid", "language": "en", "sample_rate": 24000}
```

2. `audio_chunk` (repeats)
```json
{"audio_data": "base64_pcm16...", "chunk_index": 0, "chunk_size": 4096, "sample_rate": 24000}
```

3. `synthesis_complete`
```json
{"history_id": "uuid", "total_chunks": 12, "duration": 3.25, "synthesis_time": 2.1, "gpu_slots_free": 1}
```

4. `error` (on failure)
```json
{"error": "gpu_queue_full", "message": "GPU queue full — try again later"}
```

---

## 10. Error Codes

All errors return:
```json
{"error": "error_code", "message": "Human-readable description", "details": {...}}
```

| Code | HTTP | Description |
|------|------|-------------|
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
| `task_not_ready` | 400 | Task not completed yet |
| `missing_voice` | 400 | Comic dub: no file or voice_id for speaker |
| `invalid_script` | 400 | Comic dub: malformed script JSON |

---

## Quick Reference

| Action | Method | Endpoint |
|--------|--------|----------|
| Health check | GET | `/health` |
| Generate TTS (JSON) | POST | `/api/v1/tts/omni/generate` |
| Generate TTS (WAV) | POST | `/api/v1/tts/omni/generate/audio` |
| Stream TTS (SSE) | POST | `/api/v1/tts/omni/stream` |
| Stream TTS (WebSocket) | WS | `/ws/tts/omni?api_key=...` |
| Submit async task | POST | `/api/v1/tasks/tts/omni` |
| Check task status | GET | `/api/v1/tasks/{task_id}` |
| Download task audio | GET | `/api/v1/tasks/{task_id}/audio` |
| List tasks | GET | `/api/v1/tasks` |
| Comic dub (JSON) | POST | `/api/v1/comic/dub` |
| Comic dub (WAV) | POST | `/api/v1/comic/dub/audio` |
| Upload voice | POST | `/api/v1/voices` |
| List voices | GET | `/api/v1/voices` |
| Get voice | GET | `/api/v1/voices/{id}` |
| Update voice | PUT | `/api/v1/voices/{id}` |
| Delete voice | DELETE | `/api/v1/voices/{id}` |
| List history | GET | `/api/v1/history` |
| Get history | GET | `/api/v1/history/{id}` |
| Delete history | DELETE | `/api/v1/history/{id}` |
| List engines | GET | `/api/v1/tts/engines` |
| Engine languages | GET | `/api/v1/tts/omni/languages` |
