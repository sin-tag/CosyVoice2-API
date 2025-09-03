#!/usr/bin/env python3
"""
CosyVoice2 API Server Starter
The ONLY startup script you need
"""

import os
import sys

# Setup Python path FIRST
current_dir = os.path.dirname(os.path.abspath(__file__))
paths = [
    current_dir,
    os.path.join(current_dir, 'cosyvoice_original'),
    os.path.join(current_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
]

for path in paths:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Set environment variable
os.environ['PYTHONPATH'] = os.pathsep.join(paths + [os.environ.get('PYTHONPATH', '')])

print("🚀 Starting CosyVoice2 API...")
print(f"Working directory: {current_dir}")
print(f"Python paths added: {len(paths)}")

# Test critical imports
try:
    print("Testing imports...")

    # Check and install missing dependencies
    missing_deps = []

    try:
        from pydantic_settings import BaseSettings
    except ImportError:
        missing_deps.append("pydantic-settings>=2.0.0")

    try:
        import whisper
    except ImportError:
        missing_deps.append("openai-whisper>=20231117")

    try:
        import WeTextProcessing
    except ImportError:
        missing_deps.append("WeTextProcessing>=1.0.3")

    # Check transformers version for Qwen2ForCausalLM
    try:
        from transformers import Qwen2ForCausalLM
    except ImportError:
        try:
            import transformers
            print(f"⚠️  transformers version {transformers.__version__} doesn't have Qwen2ForCausalLM")
            missing_deps.append("transformers>=4.37.0")
        except ImportError:
            missing_deps.append("transformers>=4.37.0")

    if missing_deps:
        print(f"⚠️  Installing missing dependencies: {', '.join(missing_deps)}")
        import subprocess
        for dep in missing_deps:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
        print("✓ Dependencies installed")

    from app.core.config import settings
    print("✓ Config OK")

    from app.models.voice import VoiceCreate
    print("✓ Models OK")

    from app.core.voice_cache import VoiceCache
    print("✓ Voice cache OK")

    print("✓ All imports successful")

except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    print("\n💡 Try running: pip install pydantic-settings")
    sys.exit(1)

# Start the server
try:
    import uvicorn
    print("Starting server on http://0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    
except KeyboardInterrupt:
    print("\n👋 Server stopped")
except Exception as e:
    print(f"❌ Server error: {e}")
    sys.exit(1)
