# CosyVoice2 API

A FastAPI-based REST API for CosyVoice2 voice cloning and text-to-speech synthesis.

## Features

- **Voice Cache Management**: CRUD operations for managing cached voices
- **Multiple Audio Formats**: Support for MP3, WAV, FLAC, and M4A formats
- **Voice Cloning**: Zero-shot voice cloning with 3-second audio samples
- **Cross-lingual Support**: Multi-language voice synthesis
- **Async Processing**: High-performance async API endpoints
- **Auto-loading**: Automatic loading of cached voices on startup

## Quick Start

### 1. Installation Options

#### Option A: Using Conda (Recommended)

```bash
# Clone the repository
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# Create conda environment
conda create -n cosyvoice2-api python=3.9 -y
conda activate cosyvoice2-api

# Install PyTorch with CUDA support
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y

# Install audio libraries
conda install -c conda-forge librosa soundfile -y

# Install other dependencies
pip install -r requirements.txt
```

#### Option B: Using Virtual Environment

```bash
# Clone the repository
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# Run setup script (recommended)
chmod +x scripts/setup.sh
./scripts/setup.sh

# Or install manually
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Option C: Using Docker

```bash
# Clone and start with Docker Compose
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API
docker-compose up -d
```

### 2. Configuration

```bash
# Copy environment configuration
cp .env.example .env

# Edit configuration as needed
nano .env
```

### 3. Download Models

Download the CosyVoice2 model:

```bash
# Using the provided script (recommended)
python scripts/download_model.py

# Or manually download and extract to models/CosyVoice2-0.5B/
```

### 4. Run the Server

#### If using Conda:
```bash
# Activate conda environment
conda activate cosyvoice2-api

# Start the server
python main.py
```

#### If using Virtual Environment:
```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Start the server
python main.py
```

#### Production Mode:
```bash
# Using Gunicorn (install first: pip install gunicorn)
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Or using Uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

## API Endpoints

### Voice Management

- `GET /api/v1/voices/` - List all cached voices
- `POST /api/v1/voices/` - Add a new voice to cache
- `GET /api/v1/voices/{voice_id}` - Get voice details
- `PUT /api/v1/voices/{voice_id}` - Update voice information
- `DELETE /api/v1/voices/{voice_id}` - Remove voice from cache

### Voice Synthesis

- `POST /api/v1/synthesize/sft` - Synthesize with pre-trained voices
- `POST /api/v1/synthesize/zero-shot` - Zero-shot voice cloning
- `POST /api/v1/synthesize/cross-lingual` - Cross-lingual synthesis

### System

- `GET /` - API information
- `GET /health` - Health check

## Usage Examples

### Add Voice to Cache

```python
import requests

# Upload voice sample
with open("voice_sample.wav", "rb") as f:
    files = {"audio_file": f}
    data = {
        "voice_id": "my_voice_001",
        "name": "My Custom Voice",
        "description": "A custom voice for testing",
        "prompt_text": "Hello, this is a sample voice."
    }
    response = requests.post("http://localhost:8000/api/v1/voices/", files=files, data=data)
```

### Synthesize Speech

```python
import requests

# Zero-shot synthesis
data = {
    "text": "Hello, how are you today?",
    "voice_id": "my_voice_001",
    "speed": 1.0,
    "format": "wav"
}
response = requests.post("http://localhost:8000/api/v1/synthesize/zero-shot", json=data)

# Save audio file
with open("output.wav", "wb") as f:
    f.write(response.content)
```

## Project Structure

```
CosyVoice2-API/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment configuration template
├── README.md              # This file
├── app/                   # Application package
│   ├── __init__.py
│   ├── core/              # Core application logic
│   │   ├── config.py      # Configuration settings
│   │   ├── voice_manager.py # Voice management logic
│   │   └── exceptions.py  # Exception handlers
│   ├── api/               # API routes
│   │   └── v1/            # API version 1
│   │       ├── router.py  # Main router
│   │       ├── voices.py  # Voice management endpoints
│   │       └── synthesis.py # Synthesis endpoints
│   ├── models/            # Pydantic models
│   │   ├── voice.py       # Voice data models
│   │   └── synthesis.py   # Synthesis request/response models
│   └── utils/             # Utility functions
│       ├── audio.py       # Audio processing utilities
│       └── file_utils.py  # File handling utilities
├── cosyvoice_original/    # Original CosyVoice repository
├── voice_cache/           # Cached voice data
├── outputs/               # Generated audio files
└── models/                # CosyVoice model files
```

## Detailed Setup Guides

- **[Conda Setup Guide](CONDA_SETUP.md)** - Comprehensive conda-based installation
- **[Quick Start Guide](QUICK_START.md)** - Get running in minutes
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Fix common issues
- **[Docker Deployment](DEPLOYMENT.md)** - Docker and production deployment
- **[API Examples](docs/API_EXAMPLES.md)** - Detailed API usage examples

## System Requirements

- **Python**: 3.9+
- **GPU**: CUDA-compatible GPU recommended (NVIDIA GTX 1060+ or better)
- **RAM**: 8GB minimum, 16GB+ recommended
- **Storage**: 10GB+ for models and cache
- **OS**: Linux (Ubuntu 18.04+), macOS, Windows 10+

## Troubleshooting

### Common Issues

1. **Pydantic Import Error**: Run `python scripts/fix_dependencies.py`
2. **CUDA not available**: Install proper NVIDIA drivers and CUDA toolkit
3. **Audio processing errors**: Install ffmpeg system package
4. **Model download fails**: Check internet connection and disk space
5. **Import errors**: Ensure all dependencies are installed in the correct environment

For detailed solutions, see **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**

### Getting Help

- Check the [Conda Setup Guide](CONDA_SETUP.md) for detailed installation steps
- Review [API Examples](docs/API_EXAMPLES.md) for usage examples
- Check the [Deployment Guide](DEPLOYMENT.md) for production setup

## License

This project is licensed under the Apache License 2.0 - see the original CosyVoice repository for details.
