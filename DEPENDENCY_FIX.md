# CosyVoice2 API - Dependency Fix Guide

## 🔧 Issues Fixed

### 1. Missing Dependencies
- **whisper** - Required for speech processing
- **WeTextProcessing** - Required for text processing

### 2. Version Compatibility
- **transformers >= 4.37.0** - Required for `Qwen2ForCausalLM` import

## 🚀 Quick Fix

### Option 1: Auto-install (Recommended)
```bash
conda activate tts_api
python start.py
```
The start.py script will automatically detect and install missing dependencies.

### Option 2: Manual Install
```bash
conda activate tts_api
pip install openai-whisper>=20231117
pip install WeTextProcessing>=1.0.3
pip install transformers>=4.37.0
```

### Option 3: Reinstall All Dependencies
```bash
conda activate tts_api
pip install -r requirements.txt --upgrade
```

## 🔍 Check Dependencies

Run the dependency checker:
```bash
python check_cosyvoice_deps.py
```

Expected output:
```
🔍 Checking CosyVoice Dependencies
==================================================
✓ PyTorch: 2.x.x
✓ Transformers: 4.37.x
✓ Whisper: Available
✓ WeTextProcessing: Available
...
🎉 All dependencies are ready!
```

## 📋 What Was Updated

1. **requirements.txt** - Added missing deps, updated transformers
2. **requirements-conda.txt** - Same for conda users
3. **environment.yml** - Conda environment file
4. **start.py** - Auto-install missing dependencies
5. **scripts/fix_dependencies.py** - Enhanced dependency fixer

## ✅ Result

After running `python start.py`, you should see:
```
🚀 Starting CosyVoice2 API...
✓ Dependencies installed
✓ All imports successful
Starting server on http://0.0.0.0:8000
```

No more `ImportError: cannot import name 'Qwen2ForCausalLM'`! 🎉
