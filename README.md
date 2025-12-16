# CosyVoice API (v2 + v3) - Cross-lingual Voice Cloning

A FastAPI-based REST API for CosyVoice voice cloning and text-to-speech synthesis with **real-time streaming capabilities**.

Supports both **CosyVoice2** (v2 - Legacy) and **CosyVoice3** (v3 - Latest, Recommended).

## API Versions

| Version | Model | Description |
|---------|-------|-------------|
| v1 | CosyVoice2-0.5B | Backward compatibility |
| v2 | CosyVoice2-0.5B | Legacy support |
| **v3** | **CosyVoice3-0.5B** | **Latest - Recommended** |

## CosyVoice3 Features (v3)

- **9+ languages**: Chinese, English, Japanese, Korean, German, Spanish, French, Italian, Russian
- **18+ Chinese dialects**: Cantonese, Sichuan, Shanghai, Hokkien, Hakka, and more
- **Instruction-based voice control**: Control dialect, emotion, speed, volume via natural language
- **~150ms streaming latency**: Ultra-low latency for real-time applications
- **Better quality**: Improved content consistency and speaker similarity

## Quick Start

### Run the Server

#### Option 1: Direct Python (Recommended)

```bash
# Clone the repository
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run the server (default port: 8012)
python main.py
```

#### Option 2: Using Shell Script (Linux/macOS)

```bash
# Run with default settings
./run_server.sh

# Run with custom port
./run_server.sh --port 8080

# Run with custom host
./run_server.sh --host 127.0.0.1 --port 8012
```

#### Option 3: Using Uvicorn Directly

```bash
# Development mode
uvicorn main:app --host 0.0.0.0 --port 8012 --reload

# Production mode with multiple workers
uvicorn main:app --host 0.0.0.0 --port 8012 --workers 4
```

#### Option 4: Using Docker

```bash
# Build and run with Docker Compose
docker-compose up --build
```

### Access the API

Once the server is running:

- **API Base URL**: http://localhost:8012
- **Swagger UI Documentation**: http://localhost:8012/docs
- **ReDoc Documentation**: http://localhost:8012/redoc
- **Health Check**: http://localhost:8012/health
- **OpenAPI JSON**: http://localhost:8012/openapi.json

## Configuration

Copy the example environment file and customize as needed:

```bash
cp .env.example .env
```

Key configuration options:

| Variable | Default | Description |
|----------|---------|-------------|
| HOST | 0.0.0.0 | Server host |
| PORT | 8012 | Server port |
| DEBUG | false | Debug mode |
| MODEL_DIR | models/CosyVoice2-0.5B | CosyVoice2 model path |
| MODEL_DIR_V3 | models/Fun-CosyVoice3-0.5B | CosyVoice3 model path |
| AUTO_DOWNLOAD_MODELS | true | Auto-download models from HuggingFace |

## Model Setup

### Automatic Download (Recommended)

Set `AUTO_DOWNLOAD_MODELS=true` in `.env` and the server will automatically download models from HuggingFace on first run.

### Manual Download

```bash
# CosyVoice2
# Download from HuggingFace and place in models/CosyVoice2-0.5B/

# CosyVoice3
# Download from https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512
# Place in models/Fun-CosyVoice3-0.5B/
```

## API Endpoints

### Voice Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v3/voices/ | Create a new voice from audio sample |
| GET | /api/v3/voices/ | List all cached voices |
| GET | /api/v3/voices/{voice_id} | Get voice details |
| PUT | /api/v3/voices/{voice_id} | Update voice information |
| DELETE | /api/v3/voices/{voice_id} | Delete a voice |

### Cross-lingual Synthesis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v3/cross-lingual/with-audio | Synthesize with audio reference file |
| POST | /api/v3/cross-lingual/with-cache | Synthesize with cached voice |
| POST | /api/v3/cross-lingual/instruct | Synthesize with instruction control (v3 only) |
| GET | /api/v3/cross-lingual/capabilities | Get CosyVoice3 capabilities (v3 only) |

### Task-based Synthesis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v3/cross-lingual/task | Create background synthesis task |
| GET | /api/v3/cross-lingual/task/{task_id} | Get task status |
| GET | /api/v3/cross-lingual/tasks | List all tasks |
| DELETE | /api/v3/cross-lingual/task/{task_id} | Delete a task |

### Scheduled Background Rendering (v3 only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v3/schedule/register | Register task for later rendering |
| POST | /api/v3/schedule/render/{task_id} | Start background rendering |
| GET | /api/v3/schedule/status/{task_id} | Get task status and audio_url |
| GET | /api/v3/schedule/tasks | List all scheduled tasks |
| DELETE | /api/v3/schedule/task/{task_id} | Cancel/delete scheduled task |
| POST | /api/v3/schedule/render-all | Batch render all pending tasks |
| GET | /api/v3/schedule/queue-stats | Get queue statistics |

### Streaming Synthesis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v3/streaming/cross-lingual | HTTP streaming synthesis |
| GET | /api/v3/streaming/cross-lingual/sse | Server-Sent Events streaming |
| WS | /api/v3/ws/stream | WebSocket bidirectional streaming |
| GET | /api/v3/streaming/health | Streaming service health check |

## Usage Examples

### Python

```python
import requests

# 1. Create a voice from audio sample
files = {'audio_file': open('sample.wav', 'rb')}
data = {
    'voice_id': 'my_voice',
    'name': 'My Voice',
    'voice_type': 'cross_lingual'
}
response = requests.post('http://localhost:8012/api/v3/voices/', files=files, data=data)
print(response.json())

# 2. Synthesize with cached voice
response = requests.post('http://localhost:8012/api/v3/cross-lingual/with-cache', json={
    'text': 'Hello, this is a test of voice synthesis.',
    'voice_id': 'my_voice',
    'format': 'wav',
    'speed': 1.0
})
result = response.json()
audio_url = result['audio_url']
print(f"Audio URL: http://localhost:8012{audio_url}")

# 3. Download the audio file
audio = requests.get(f'http://localhost:8012{audio_url}')
with open('output.wav', 'wb') as f:
    f.write(audio.content)

# 4. Synthesize with instruction control (v3 only)
files = {'prompt_audio': open('sample.wav', 'rb')}
data = {
    'text': 'Hello, how are you today?',
    'instruct_text': 'Speak slowly with a happy tone',
    'format': 'wav'
}
response = requests.post('http://localhost:8012/api/v3/cross-lingual/instruct', files=files, data=data)
print(response.json())
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

# Synthesize with cached voice
curl -X POST http://localhost:8012/api/v3/cross-lingual/with-cache \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice_id": "my_voice"}'

# Download generated audio
curl -O http://localhost:8012/api/v3/audio/v3_cache_abc12345.wav
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
    const audioData = atob(data.audio_data);
  }
};
```

## Project Structure

```
CosyVoice2-API/
├── main.py                     # FastAPI application entry point
├── requirements.txt            # Python dependencies
├── .env                        # Environment configuration
├── .env.example               # Environment template
├── API_DOCUMENTATION.md       # Detailed API documentation
├── openapi_schema.json        # OpenAPI 3.0 schema for integration
├── app/
│   ├── core/
│   │   ├── config.py          # Configuration settings
│   │   ├── voice_manager.py   # Voice manager for v2
│   │   ├── voice_manager_v3.py # Voice manager for v3
│   │   ├── synthesis_engine.py # Synthesis engine for v2
│   │   ├── synthesis_engine_v3.py # Synthesis engine for v3
│   │   └── model_downloader.py # Auto-download from HuggingFace
│   ├── api/
│   │   ├── v1/                # API v1 (backward compatibility)
│   │   ├── v2/                # API v2 (CosyVoice2)
│   │   └── v3/                # API v3 (CosyVoice3)
│   └── models/                # Pydantic models
├── cosyvoice_original/        # Original CosyVoice repository
├── voice_cache/               # Cached voice data
├── outputs/                   # Generated audio files
└── models/                    # CosyVoice model files
    ├── CosyVoice2-0.5B/      # CosyVoice2 model
    └── Fun-CosyVoice3-0.5B/  # CosyVoice3 model
```

## System Requirements

- **Python**: 3.9+ (3.10 recommended)
- **GPU**: CUDA-compatible GPU recommended (NVIDIA GTX 1060+ or better)
- **RAM**: 8GB minimum, 16GB+ recommended
- **Storage**: 10GB+ for models and cache
- **OS**: Linux (Ubuntu 18.04+), macOS, Windows 10+

## Documentation

- **[API Documentation](API_DOCUMENTATION.md)** - Detailed API reference
- **[OpenAPI Schema](openapi_schema.json)** - For API integration
- **Swagger UI**: http://localhost:8012/docs (when server is running)

## Troubleshooting

### Common Issues

1. **Pydantic Import Error**:
   ```bash
   pip install pydantic-settings>=2.0.0
   ```

2. **CUDA not available**: Install proper NVIDIA drivers and CUDA toolkit

3. **Model not found**: Set `AUTO_DOWNLOAD_MODELS=true` in `.env` or manually download models

4. **Port already in use**: Change PORT in `.env` or use `--port` flag

5. **Import errors**: Ensure all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

### Getting Help

- Check the [API Documentation](API_DOCUMENTATION.md) for detailed endpoint information
- Use `/health` endpoint to check model status
- Check server logs for detailed error messages

## License

This project is licensed under the Apache License 2.0 - see the original CosyVoice repository for details.

## Credits

- [CosyVoice](https://github.com/FunAudioLLM/CosyVoice) - Original TTS model by FunAudioLLM
- [HuggingFace](https://huggingface.co/FunAudioLLM) - Model hosting
