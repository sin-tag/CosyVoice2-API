#!/usr/bin/env python3
"""
Test script to verify all imports work correctly
"""

import sys
import os

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
paths_to_add = [
    ROOT_DIR,
    os.path.join(ROOT_DIR, 'cosyvoice_original'),
    os.path.join(ROOT_DIR, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
]

for path in paths_to_add:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Set PYTHONPATH environment variable
current_pythonpath = os.environ.get('PYTHONPATH', '')
new_paths = [p for p in paths_to_add if p not in current_pythonpath.split(os.pathsep)]
if new_paths:
    if current_pythonpath:
        os.environ['PYTHONPATH'] = os.pathsep.join(new_paths + [current_pythonpath])
    else:
        os.environ['PYTHONPATH'] = os.pathsep.join(new_paths)

def test_imports():
    """Test all critical imports"""
    print("Testing imports...")
    
    try:
        # Test basic imports
        print("✓ Testing basic Python imports...")
        import asyncio
        import logging
        from pathlib import Path
        print("  ✓ Basic imports OK")
        
        # Test Pydantic imports
        print("✓ Testing Pydantic imports...")
        try:
            from pydantic_settings import BaseSettings
            from pydantic import Field
            print("  ✓ Pydantic v2 imports OK")
        except ImportError:
            from pydantic import BaseSettings, Field
            print("  ✓ Pydantic v1 imports OK")
        
        # Test FastAPI imports
        print("✓ Testing FastAPI imports...")
        from fastapi import FastAPI, APIRouter
        import uvicorn
        print("  ✓ FastAPI imports OK")
        
        # Test app imports
        print("✓ Testing app imports...")
        from app.core.config import settings
        print("  ✓ Config import OK")
        
        from app.models.voice import VoiceCreate, VoiceInDB
        print("  ✓ Voice models import OK")
        
        from app.models.synthesis import SynthesisResponse
        print("  ✓ Synthesis models import OK")
        
        from app.core.voice_cache import VoiceCache
        print("  ✓ Voice cache import OK")
        
        from app.core.async_synthesis import AsyncSynthesisManager
        print("  ✓ Async synthesis import OK")
        
        from app.api.v1.router import api_router
        print("  ✓ API router import OK")
        
        # Test main app import
        print("✓ Testing main app import...")
        from main import create_app
        print("  ✓ Main app import OK")
        
        print("\n🎉 All imports successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_creation():
    """Test FastAPI app creation"""
    print("\n✓ Testing app creation...")
    
    try:
        from main import create_app
        app = create_app()
        print("  ✓ FastAPI app created successfully")
        
        # Check routes
        routes = [route.path for route in app.routes]
        print(f"  ✓ Found {len(routes)} routes")
        
        # Check for key routes
        key_routes = ["/", "/health", "/api/v1/voices/", "/api/v1/async/tasks"]
        for route in key_routes:
            if any(r.startswith(route) for r in routes):
                print(f"    ✓ Route {route} found")
            else:
                print(f"    ⚠ Route {route} not found")
        
        return True
        
    except Exception as e:
        print(f"  ❌ App creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🔍 CosyVoice2 API Import Test")
    print("=" * 50)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test app creation
    if not test_app_creation():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed! The application should start correctly.")
        print("\nTo start the server, run:")
        print("  python main.py")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
