# CosyVoice2 API - Simple Usage

## 🚀 Ultra-Simple Setup

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# Create conda environment with Python 3.10+
conda create -n cosyvoice2-api python=3.10
conda activate cosyvoice2-api
```

### 2. Start the Server (Auto-Setup)

**That's it! Just run:**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### 🎯 What Happens Automatically

**🔄 First Run:**
- Clones CosyVoice from GitHub if missing
- Updates git submodules (Matcha-TTS)
- Installs all required dependencies
- Creates app/models directory and files
- Sets up Python paths

**⚡ Subsequent Runs:**
- Starts immediately (no setup needed)

### 🌐 Access the API

- **API Server**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 🔧 Production Mode

```bash
# For production with multiple workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 📋 Requirements

- **Python**: 3.10+ (recommended)
- **Git**: For cloning CosyVoice
- **Internet**: For downloading dependencies and models

### ✅ That's It!

No manual setup, no configuration files, no complex scripts.
Just one command and everything works automatically! 🎉

---

## 🔍 What Gets Installed Automatically

- FastAPI and Uvicorn
- PyTorch and TorchAudio
- Transformers (4.37.0+)
- Librosa and SoundFile
- OpenAI Whisper
- WeTextProcessing
- ModelScope
- Pydantic Settings
- And all other dependencies

## 🗂️ What Gets Created Automatically

- `cosyvoice_original/` - CosyVoice source code
- `cosyvoice_original/third_party/Matcha-TTS/` - Matcha-TTS dependency
- `app/models/` - API models directory
- All necessary Python packages and paths

## 🎯 Zero Configuration Required

The system automatically detects and configures:
- Python paths for CosyVoice and Matcha-TTS
- Model directories and cache locations
- API endpoints and documentation
- Health checks and monitoring

Just run `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1` and you're ready to go!
