# Voice Fast Service — API Documentation (XTTS-v2)

> **Engine:** [coqui/XTTS-v2](https://huggingface.co/coqui/XTTS-v2) — 17 languages, zero-shot voice cloning, streaming
> **Base URL:** `http://your-server:8010`
> **Auth:** `X-Api-Key` header on all endpoints (except `/health`)
> **Audio Output:** MP3, 24kHz, mono
> **Backward compatible:** All `/omni/` URLs also work (alias to `/xtts/`)

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
ws://host:8010/ws/tts/xtts?api_key=your-api-key
```

---

## 2. Health & Status

### `GET /health`

No auth required.

```bash
curl http://localhost:8010/health
```

```json
{
  "status": "ok",
  "engines": [{
    "name": "xtts",
    "loaded": true,
    "languages": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi"],
    "cached_voices": 3,
    "gpu_slots": {"free": 2, "total": 2, "busy": 0, "gpus": 1}
  }],
  "queue": {"pending": 0, "processing": 0, "max_queue_size": 100}
}
```

---

## 3. TTS — Synchronous Generation

### `POST /api/v1/tts/xtts/generate` — JSON response

```bash
curl -X POST http://localhost:8010/api/v1/tts/xtts/generate \
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
| `language` | string | Yes | — | Language code (see table below) |
| `voice_id` | UUID | Yes | — | Voice ID from `/api/v1/voices` |
| `speed` | float | No | 0.8 | Speaking speed (0.3–2.0, lower = slower/clearer) |
| `temperature` | float | No | 0.7 | Creativity (0.0–2.0) |
| `top_p` | float | No | 0.9 | Nucleus sampling (0.0–1.0) |
| `top_k` | int | No | 50 | Top-K sampling (1–500) |
| `repetition_penalty` | float | No | 1.2 | Repetition penalty (1.0–3.0) |

**Supported Languages (17):**

| Code | Language | Code | Language | Code | Language |
|------|----------|------|----------|------|----------|
| en | English | pt | Portuguese | cs | Czech |
| es | Spanish | pl | Polish | ar | Arabic |
| fr | French | tr | Turkish | zh / zh-cn | Chinese |
| de | German | ru | Russian | ja | Japanese |
| it | Italian | nl | Dutch | ko | Korean |
| hu | Hungarian | hi | Hindi | | |

> `zh` is auto-mapped to `zh-cn`. Reference audio should match target language for best quality.

**Response:**
```json
{
  "success": true,
  "message": "Synthesis completed",
  "audio_url": "/api/v1/tts/audio/history-uuid",
  "duration": 3.25,
  "format": "mp3",
  "synthesis_time": 1.234,
  "sample_rate": 24000,
  "history_id": "history-uuid",
  "gpu_slots_free": 1,
  "gpu_slots_total": 2
}
```

### `POST /api/v1/tts/xtts/generate/audio` — Raw MP3 response

Same request body. Returns **binary MP3** for direct playback.

```bash
curl -X POST http://localhost:8010/api/v1/tts/xtts/generate/audio \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "language": "en", "voice_id": "uuid"}' \
  --output output.mp3
```

**Response Headers:**
```
Content-Type: audio/mpeg
X-History-Id: uuid
X-Sample-Rate: 24000
X-GPU-Slots-Free: 1
X-GPU-Slots-Total: 2
```

### `GET /api/v1/tts/audio/{history_id}` — Download audio

No auth required. Supports HEAD + GET.

```bash
curl http://localhost:8010/api/v1/tts/audio/history-uuid --output result.mp3
```

### `GET /api/v1/tts/engines` — List engines

### `GET /api/v1/tts/xtts/languages` — Supported languages

---

## 4. TTS — Async Task Queue

When GPU is busy, tasks queue as `pending`. Poll status to get result.

### `POST /api/v1/tasks/tts/xtts` — Submit task

```bash
curl -X POST http://localhost:8010/api/v1/tasks/tts/xtts \
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
  "check_status_url": "/api/v1/tasks/task_a1b2c3d4e5f6"
}
```

### `GET /api/v1/tasks/{task_id}` — Poll status

**Status lifecycle:** `pending` → `processing` → `completed` / `failed`

```json
{
  "task_id": "task_abc",
  "status": "completed",
  "audio_url": "/api/v1/tasks/task_abc/audio",
  "history_id": "uuid",
  "duration": 3.25
}
```

### `GET /api/v1/tasks/{task_id}/audio` — Download result

Only when `status = "completed"`.

### `GET /api/v1/tasks` — List tasks

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | null | pending, processing, completed, failed |
| `limit` | int | 50 | Max results (1–200) |

---

## 5. Comic Dubbing (Multi-Speaker)

Generate multi-speaker dubbed audio. Each segment synthesized with voice cloning, concatenated with 0.3s silence.

**Three ways to provide voices (can mix):**
1. **Upload file:** `narrator=@voice.wav`
2. **Voice ID from DB:** `voice_ids={"narrator":"uuid"}`
3. **Mix both**

### `POST /api/v1/comic/dub` — JSON response

```bash
curl -X POST http://localhost:8010/api/v1/comic/dub \
  -H "X-Api-Key: your-key" \
  -F 'script=[
    {"speaker":"narrator","text":"In a dark night, a figure appeared..."},
    {"speaker":"char1","text":"Stop! Who goes there?"},
    {"speaker":"char2","text":"Just a traveler, nothing more."}
  ]' \
  -F language=en \
  -F narrator=@narrator_voice.wav \
  -F char1=@hero_voice.wav \
  -F char2=@villain_voice.wav
```

**Using voice IDs instead of files:**
```bash
curl -X POST http://localhost:8010/api/v1/comic/dub \
  -H "X-Api-Key: your-key" \
  -F 'script=[{"speaker":"narrator","text":"..."},{"speaker":"char1","text":"..."}]' \
  -F 'voice_ids={"narrator":"550e-uuid","char1":"660e-uuid"}' \
  -F language=en
```

**Form Fields:**

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `script` | JSON | Yes | — |
| `voice_ids` | JSON | No | null |
| `language` | string | No | "en" |
| `speed` | float | No | 0.8 |
| `narrator` | file | No | — |
| `char1`–`char4` | file | No | — |

> Each speaker needs a file OR voice_id. Max 5 speakers. Audio >5s auto-trimmed.

**Response:**
```json
{
  "success": true,
  "message": "Comic dubbing completed: 3 segments, 2 speakers",
  "audio_url": "/api/v1/comic/audio/history-uuid",
  "duration": 18.5,
  "synthesis_time": 12.3,
  "speakers": ["narrator", "char1"],
  "segments_count": 3
}
```

### `POST /api/v1/comic/dub/audio` — Raw MP3

Same form fields. Returns binary MP3.

### `GET /api/v1/comic/audio/{history_id}` — Download audio

No auth. Supports HEAD + GET.

---

## 6. Voice Management

### `POST /api/v1/voices` — Upload voice

```bash
curl -X POST http://localhost:8010/api/v1/voices \
  -H "X-Api-Key: your-key" \
  -F "name=Hero Voice" \
  -F "language=en" \
  -F "reference_text=Sample text spoken in the audio" \
  -F "reference_audio=@voice_sample.wav"
```

> `reference_text` improves cloning quality. Audio: 1–30s, recommended 3–5s.

### `GET /api/v1/voices` — List (paginated)

### `GET /api/v1/voices/{id}` — Get detail

### `PUT /api/v1/voices/{id}` — Update metadata

### `DELETE /api/v1/voices/{id}` — Delete (204)

---

## 7. Generation History

### `GET /api/v1/history` — List (paginated, filterable by engine/voice_id)

### `GET /api/v1/history/{id}` — Get detail

### `DELETE /api/v1/history/{id}` — Delete (204)

---

## 8. WebSocket Real-Time TTS

### `WS /ws/tts/xtts?api_key=your-key`

Also works: `/ws/tts/omni?api_key=...`

**Send:** `{"text": "Hello", "language": "en", "voice_id": "uuid"}`

**Receive:** JSON metadata + binary PCM16 audio frames

| message_type | Description |
|-------------|-------------|
| `synthesis_start` | Started, includes `sample_rate` |
| `audio_chunk` | JSON metadata then binary PCM16 |
| `synthesis_complete` | Done: `history_id`, `duration` |
| `error` | Error: `error_code`, `error_message` |

---

## 9. SSE Streaming

### `POST /api/v1/tts/xtts/stream`

Events: `synthesis_start` → `audio_chunk` (base64 PCM16) → `synthesis_complete`

---

## 10. Error Codes

```json
{"error": "error_code", "message": "description"}
```

| Code | HTTP | Description |
|------|------|-------------|
| `validation_error` | 422 | Invalid parameters |
| `http_error` | 401 | Invalid API key |
| `voice_not_found` | 404 | Voice ID doesn't exist |
| `unsupported_language` | 400 | Language not supported |
| `engine_not_loaded` | 503 | Engine not available |
| `generation_timeout` | 504 | Took too long |
| `gpu_oom` | 503 | GPU out of memory |
| `access_denied` | 403 | IP not whitelisted |
| `server_busy` | 503 | Too many requests |
| `missing_voice` | 400 | Comic: no voice for speaker |
| `invalid_script` | 400 | Comic: bad script JSON |

---

## Backward Compatibility (from omni-voice branch)

All `/omni/` URLs are aliased to `/xtts/`. Backend does **not** need to change URLs.

| Old URL (omni) | New URL (xtts) |
|----------------|----------------|
| `/api/v1/tts/omni/generate` | `/api/v1/tts/xtts/generate` |
| `/api/v1/tts/omni/generate/audio` | `/api/v1/tts/xtts/generate/audio` |
| `/api/v1/tts/omni/stream` | `/api/v1/tts/xtts/stream` |
| `/api/v1/tasks/tts/omni` | `/api/v1/tasks/tts/xtts` |
| `/ws/tts/omni` | `/ws/tts/xtts` |

---

## Quick Reference

| Action | Method | Endpoint |
|--------|--------|----------|
| Health | GET | `/health` |
| Generate (JSON) | POST | `/api/v1/tts/xtts/generate` |
| Generate (MP3) | POST | `/api/v1/tts/xtts/generate/audio` |
| Download audio | GET | `/api/v1/tts/audio/{history_id}` |
| Stream SSE | POST | `/api/v1/tts/xtts/stream` |
| Stream WS | WS | `/ws/tts/xtts?api_key=...` |
| Submit task | POST | `/api/v1/tasks/tts/xtts` |
| Task status | GET | `/api/v1/tasks/{task_id}` |
| Task audio | GET | `/api/v1/tasks/{task_id}/audio` |
| Comic dub (JSON) | POST | `/api/v1/comic/dub` |
| Comic dub (MP3) | POST | `/api/v1/comic/dub/audio` |
| Comic audio | GET | `/api/v1/comic/audio/{history_id}` |
| Upload voice | POST | `/api/v1/voices` |
| List voices | GET | `/api/v1/voices` |
| Engines | GET | `/api/v1/tts/engines` |
| Languages | GET | `/api/v1/tts/xtts/languages` |
