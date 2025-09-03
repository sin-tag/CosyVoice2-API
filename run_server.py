#!/usr/bin/env python3
"""
CosyVoice2 API Server Launcher
Ensures proper Python path setup before starting the server
"""

import os
import sys
import subprocess

def setup_python_path():
    """Setup Python path for proper module imports"""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    paths_to_add = [
        root_dir,
        os.path.join(root_dir, 'cosyvoice_original'),
        os.path.join(root_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
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

def check_imports():
    """Check if critical imports work"""
    try:
        print("Checking imports...")

        # Ensure path is set up first
        setup_python_path()

        # Test basic imports
        import fastapi
        import uvicorn
        print("✓ FastAPI and Uvicorn imports OK")

        # Test app imports
        from app.core.config import settings
        print("✓ Config import OK")

        from app.models.voice import VoiceCreate
        print("✓ Voice models import OK")

        from app.core.voice_cache import VoiceCache
        print("✓ Voice cache import OK")

        print("✓ All critical imports successful")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main launcher function"""
    print("🚀 Starting CosyVoice2 API Server...")
    
    # Setup Python path
    setup_python_path()
    
    # Check imports
    if not check_imports():
        print("❌ Import check failed. Please fix the issues above.")
        return 1
    
    # Get command line arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    # Default arguments
    default_args = [
        "main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    
    # Use provided args or defaults
    uvicorn_args = args if args else default_args
    
    print(f"Starting server with args: {' '.join(uvicorn_args)}")
    
    try:
        # Import and run uvicorn
        import uvicorn
        
        # Parse arguments
        if len(uvicorn_args) >= 1 and not uvicorn_args[0].startswith('-'):
            app_str = uvicorn_args[0]
            remaining_args = uvicorn_args[1:]
        else:
            app_str = "main:app"
            remaining_args = uvicorn_args
        
        # Parse remaining arguments
        config = {
            "app": app_str,
            "host": "0.0.0.0",
            "port": 8000,
            "reload": True
        }
        
        i = 0
        while i < len(remaining_args):
            arg = remaining_args[i]
            if arg == "--host" and i + 1 < len(remaining_args):
                config["host"] = remaining_args[i + 1]
                i += 2
            elif arg == "--port" and i + 1 < len(remaining_args):
                config["port"] = int(remaining_args[i + 1])
                i += 2
            elif arg == "--reload":
                config["reload"] = True
                i += 1
            elif arg == "--no-reload":
                config["reload"] = False
                i += 1
            else:
                i += 1
        
        print(f"Server config: {config}")
        uvicorn.run(**config)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Server error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
