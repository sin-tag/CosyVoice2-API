#!/usr/bin/env python3
"""
CosyVoice2 API Server Starter
The ONLY startup script you need
"""

import os
import sys

# Setup Python path FIRST
current_dir = os.path.dirname(os.path.abspath(__file__))

# Auto-detect CosyVoice directory (could be 'cosyvoice' or 'cosyvoice_original')
cosyvoice_dir = None
for dirname in ['cosyvoice', 'cosyvoice_original']:
    test_dir = os.path.join(current_dir, dirname)
    if os.path.exists(test_dir):
        cosyvoice_dir = test_dir
        print(f"✓ Found CosyVoice directory: {dirname}")
        break

if not cosyvoice_dir:
    print("⚠️  No CosyVoice directory found (looking for 'cosyvoice' or 'cosyvoice_original')")

paths = [current_dir]
if cosyvoice_dir:
    paths.append(cosyvoice_dir)

# Look for Matcha-TTS in multiple locations
matcha_locations = [
    os.path.join(current_dir, 'third_party', 'Matcha-TTS'),  # Root level
]
if cosyvoice_dir:
    matcha_locations.append(os.path.join(cosyvoice_dir, 'third_party', 'Matcha-TTS'))

for matcha_path in matcha_locations:
    if os.path.exists(matcha_path):
        paths.append(matcha_path)
        print(f"✓ Found Matcha-TTS at: {matcha_path}")
        break

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

    # Fix missing app/models directory
    print("Checking app/models directory...")
    app_models_dir = os.path.join(current_dir, 'app', 'models')
    if not os.path.exists(app_models_dir):
        print("⚠️  app/models directory missing, creating...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, "fix_missing_models.py"])
            print("✓ app/models directory created")
        except Exception as e:
            print(f"❌ Failed to create app/models: {e}")
            print("Please run: python fix_missing_models.py")
            sys.exit(1)

    # Fix Matcha-TTS path issue
    print("Checking Matcha-TTS setup...")

    # Look for Matcha-TTS in multiple locations
    matcha_locations = [
        os.path.join(current_dir, 'third_party', 'Matcha-TTS'),  # Root level
        os.path.join(current_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS'),
        os.path.join(current_dir, 'cosyvoice', 'third_party', 'Matcha-TTS'),
    ]

    matcha_dir = None
    for location in matcha_locations:
        if os.path.exists(location):
            matcha_dir = location
            print(f"✓ Found Matcha-TTS at: {location}")
            break

    if matcha_dir:
        # Add Matcha-TTS to path if not already there
        if matcha_dir not in sys.path:
            sys.path.insert(0, matcha_dir)

        # Check if matcha module can be imported
        try:
            import matcha.models
            print("✓ Matcha-TTS import OK")
        except ImportError as e:
            print(f"⚠️  Matcha-TTS import issue: {e}")
            # Try to fix by adding the matcha directory specifically
            matcha_src_dir = os.path.join(matcha_dir, 'matcha')
            if os.path.exists(matcha_src_dir) and matcha_src_dir not in sys.path:
                sys.path.insert(0, matcha_src_dir)
                print(f"✓ Added Matcha source directory: {matcha_src_dir}")
    else:
        print("⚠️  Matcha-TTS directory not found in any expected location")
        print("This may cause issues with CosyVoice flow matching")

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
