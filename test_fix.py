#!/usr/bin/env python3
"""
Quick test to verify the import fix works
"""

import os
import sys

# Setup Python path (same as start.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
paths = [
    current_dir,
    os.path.join(current_dir, 'cosyvoice_original'),
    os.path.join(current_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
]

for path in paths:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

print("🔍 Testing CosyVoice2 API imports...")
print(f"Working directory: {current_dir}")

try:
    print("1. Testing basic imports...")
    import fastapi
    import uvicorn
    print("   ✓ FastAPI/Uvicorn OK")
    
    print("2. Testing app.core imports...")
    from app.core.config import settings
    print("   ✓ Config OK")
    
    print("3. Testing app.models imports...")
    from app.models.voice import VoiceCreate, VoiceInDB
    print("   ✓ Voice models OK")
    
    from app.models.synthesis import SynthesisResponse
    print("   ✓ Synthesis models OK")
    
    print("4. Testing app.core.voice_cache...")
    from app.core.voice_cache import VoiceCache
    print("   ✓ Voice cache OK")
    
    print("5. Testing main app...")
    from main import create_app
    app = create_app()
    print("   ✓ Main app creation OK")
    
    print("\n🎉 ALL TESTS PASSED!")
    print("✅ The import issues are fixed!")
    print("\nYou can now start the server with:")
    print("   python start.py")
    print("   or")
    print("   python main.py")
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    print("\nPlease check the error above and fix any remaining issues.")
    sys.exit(1)
