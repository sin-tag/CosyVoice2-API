# CosyVoice2 API - Startup Guide

This guide provides multiple methods to start the CosyVoice2 API server, ensuring it works in different environments.

## 🚀 Quick Start (Choose One Method)

### Method 1: Bash Startup Script (Recommended)

```bash
# Activate your environment
conda activate cosyvoice2-api

# Start with the robust bash script
./start_server.sh
```

### Method 2: Python Launcher

```bash
# Activate your environment
conda activate cosyvoice2-api

# Start with the Python launcher
python run_server.py
```

### Method 3: Manual with Import Test

```bash
# Activate your environment
conda activate cosyvoice2-api

# Test imports first
python test_imports.py

# If successful, start server
python main.py
```

## 🔧 Troubleshooting Import Errors

If you get `ModuleNotFoundError: No module named 'app.models'` or similar:

### Solution 1: Use Startup Scripts
The startup scripts automatically handle Python path setup:

```bash
./start_server.sh
# or
python run_server.py
```

### Solution 2: Manual PYTHONPATH Setup
```bash
# Set PYTHONPATH manually
export PYTHONPATH="$(pwd):$(pwd)/cosyvoice_original:$(pwd)/cosyvoice_original/third_party/Matcha-TTS:$PYTHONPATH"

# Then start server
python main.py
```

### Solution 3: Verify Environment
```bash
# Check you're in the right directory
pwd  # Should show /path/to/CosyVoice2-API

# Check conda environment
conda info --envs
conda activate cosyvoice2-api

# Test imports
python test_imports.py
```

## 📋 Startup Methods Comparison

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| `./start_server.sh` | Auto path setup, validation, clear output | Requires bash | Linux/macOS users |
| `python run_server.py` | Cross-platform, Python-based | Requires Python | Windows users |
| `python main.py` | Direct, simple | Manual path setup needed | Development |

## 🔍 Validation Steps

Before starting the server, you can validate your setup:

### 1. Check Environment
```bash
# Verify conda environment
echo $CONDA_DEFAULT_ENV

# Check Python version
python --version

# Verify you're in project directory
ls -la  # Should see main.py, app/, etc.
```

### 2. Test Imports
```bash
python test_imports.py
```

Expected output:
```
🔍 CosyVoice2 API Import Test
==================================================
Testing imports...
✓ Testing basic Python imports...
  ✓ Basic imports OK
✓ Testing Pydantic imports...
  ✓ Pydantic v2 imports OK
✓ Testing FastAPI imports...
  ✓ FastAPI imports OK
✓ Testing app imports...
  ✓ Config import OK
  ✓ Voice models import OK
  ✓ Synthesis models import OK
  ✓ Voice cache import OK
  ✓ Async synthesis import OK
  ✓ API router import OK
✓ Testing main app import...
  ✓ Main app import OK

🎉 All imports successful!
```

### 3. Start Server
```bash
# Use any of the startup methods
./start_server.sh
```

Expected output:
```
🚀 Starting CosyVoice2 API Server...
Working directory: /path/to/CosyVoice2-API
✓ Config import OK
✓ Voice models import OK
✓ All imports successful
Starting uvicorn server...
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 🌐 Verify Server is Running

### 1. Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "voice_manager_ready": true,
  "async_synthesis_ready": true
}
```

### 2. API Documentation
Open in browser: http://localhost:8000/docs

### 3. Test API Endpoint
```bash
curl http://localhost:8000/api/v1/voices/pretrained/list
```

## 🐛 Common Issues and Solutions

### Issue: "Permission denied: ./start_server.sh"
```bash
chmod +x start_server.sh
chmod +x run_server.py
```

### Issue: "conda: command not found"
```bash
# Add conda to PATH
export PATH="$HOME/miniconda3/bin:$PATH"
# or
source ~/.bashrc
```

### Issue: "uvicorn: command not found"
```bash
# Install uvicorn
pip install uvicorn[standard]
```

### Issue: Server starts but imports fail
```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Restart with explicit path
PYTHONPATH="$(pwd):$PYTHONPATH" python main.py
```

### Issue: Port already in use
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
./start_server.sh 0.0.0.0 8001
```

## 🔧 Advanced Configuration

### Custom Host/Port
```bash
# Bash script
./start_server.sh 127.0.0.1 8080

# Python launcher
python run_server.py --host 127.0.0.1 --port 8080

# Direct uvicorn
uvicorn main:app --host 127.0.0.1 --port 8080
```

### Production Mode
```bash
# Disable reload for production
./start_server.sh 0.0.0.0 8000 --no-reload

# Or use gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Environment Variables
```bash
# Set in .env file or export
export DEBUG=false
export MODEL_DIR=/path/to/models
export VOICE_CACHE_DIR=/path/to/cache

# Then start server
./start_server.sh
```

## 📝 Summary

1. **Always activate your conda/venv environment first**
2. **Use the startup scripts for best results** (`./start_server.sh` or `python run_server.py`)
3. **Test imports if you have issues** (`python test_imports.py`)
4. **Check the health endpoint** after startup (`curl http://localhost:8000/health`)
5. **Refer to TROUBLESHOOTING.md** for specific error solutions

The startup scripts handle all the complex Python path setup automatically, making it much easier to get the server running reliably! 🎉
