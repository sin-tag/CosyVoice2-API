# CosyVoice2 API - Uvicorn Direct Usage Fix

## ✅ Fixed Issue

The `ModuleNotFoundError: No module named 'app.models'` when using uvicorn directly has been resolved.

## 🔧 What Was Fixed

1. **Bulletproof Path Setup** in `main.py`:
   - Ensures correct working directory
   - Comprehensive Python path setup
   - Removes and re-adds paths to avoid conflicts
   - Debug output for troubleshooting

2. **Simplified Module Imports**:
   - Removed complex path setup from individual modules
   - Centralized all path handling in `main.py`
   - Cleaner, more reliable import chain

3. **Working Directory Fix**:
   - Ensures uvicorn runs from the correct directory
   - Proper path calculation regardless of where uvicorn is called from

## 🚀 Now All These Work

```bash
# Method 1: Simple start (recommended)
conda activate cosyvoice
python start.py

# Method 2: Uvicorn wrapper
conda activate cosyvoice  
python run_uvicorn.py

# Method 3: Direct uvicorn (NOW FIXED!)
conda activate cosyvoice
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

# Method 4: Production
conda activate cosyvoice
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 📋 Expected Output

When starting with uvicorn directly, you should now see:

```
DEBUG: Working directory: /root/CosyVoice2-API
DEBUG: Root directory: /root/CosyVoice2-API  
DEBUG: Python path (first 3): ['/root/CosyVoice2-API/cosyvoice', '/root/CosyVoice2-API/cosyvoice_original/third_party/Matcha-TTS', '/root/CosyVoice2-API/cosyvoice_original']
DEBUG: app.models.voice import successful
Installing pydantic-settings...
✓ pydantic-settings installed successfully
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 🎯 Key Changes

- **main.py**: Bulletproof path setup with working directory management
- **voice_cache.py**: Simplified imports (no more complex path handling)
- **voice_manager.py**: Simplified imports
- **config.py**: Auto-install pydantic-settings if missing

## ✅ Verification

Test that it works:
```bash
conda activate cosyvoice
cd /path/to/CosyVoice2-API
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

Should start successfully without `ModuleNotFoundError`!

## 🔍 If Still Having Issues

1. Make sure you're in the project directory: `cd /path/to/CosyVoice2-API`
2. Check the debug output in the console
3. Verify app directory structure exists
4. Try `python start.py` first to ensure dependencies are installed

The fix ensures uvicorn works regardless of how it's called! 🎉
