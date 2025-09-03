#!/usr/bin/env python3
"""
Uvicorn wrapper with proper Python path setup
Use this instead of direct uvicorn command
"""

import os
import sys
import subprocess

def setup_environment():
    """Setup Python path and environment variables"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Paths to add
    paths = [
        current_dir,
        os.path.join(current_dir, 'cosyvoice_original'),
        os.path.join(current_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
    ]
    
    # Add to sys.path
    for path in paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
    
    # Set PYTHONPATH environment variable
    current_pythonpath = os.environ.get('PYTHONPATH', '')
    new_pythonpath = os.pathsep.join(paths + ([current_pythonpath] if current_pythonpath else []))
    os.environ['PYTHONPATH'] = new_pythonpath
    
    print(f"✓ Python paths set: {len(paths)} paths added")
    print(f"✓ Working directory: {current_dir}")

def main():
    """Main function"""
    print("🚀 Starting CosyVoice2 API with Uvicorn...")
    
    # Setup environment
    setup_environment()
    
    # Parse command line arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    # Default uvicorn arguments
    default_args = [
        "main:app",
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--workers", "1"
    ]
    
    # Use provided args or defaults
    uvicorn_args = args if args else default_args
    
    print(f"✓ Uvicorn args: {' '.join(uvicorn_args)}")
    
    try:
        # Test imports first
        print("Testing critical imports...")
        from app.models.voice import VoiceCreate
        from app.core.config import settings
        print("✓ Imports OK")
        
        # Run uvicorn
        import uvicorn
        
        # Parse arguments into config
        config = {
            "app": "main:app",
            "host": "0.0.0.0",
            "port": 8000,
            "workers": 1
        }
        
        # Parse command line args
        i = 0
        while i < len(uvicorn_args):
            arg = uvicorn_args[i]
            if not arg.startswith('-'):
                config["app"] = arg
                i += 1
            elif arg == "--host" and i + 1 < len(uvicorn_args):
                config["host"] = uvicorn_args[i + 1]
                i += 2
            elif arg == "--port" and i + 1 < len(uvicorn_args):
                config["port"] = int(uvicorn_args[i + 1])
                i += 2
            elif arg == "--workers" and i + 1 < len(uvicorn_args):
                config["workers"] = int(uvicorn_args[i + 1])
                i += 2
            elif arg == "--reload":
                config["reload"] = True
                i += 1
            else:
                i += 1
        
        print(f"✓ Starting server: {config}")
        uvicorn.run(**config)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\n💡 Try installing missing dependencies:")
        print("   python start.py")
        return 1
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Server error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
