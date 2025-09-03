#!/usr/bin/env python3
"""
Comprehensive fix script for all CosyVoice2 API issues
Fixes: missing models, Matcha-TTS imports, dependencies, etc.
"""

import os
import sys
import subprocess

def setup_python_path():
    """Setup comprehensive Python path"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    paths = [
        current_dir,
        os.path.join(current_dir, 'cosyvoice_original'),
        os.path.join(current_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS'),
        os.path.join(current_dir, 'cosyvoice'),
    ]
    
    # Add Matcha-TTS source directory specifically
    matcha_tts_dir = os.path.join(current_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
    if os.path.exists(matcha_tts_dir):
        matcha_src_dir = os.path.join(matcha_tts_dir, 'matcha')
        if os.path.exists(matcha_src_dir):
            paths.append(matcha_src_dir)
    
    for path in paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
    
    # Set PYTHONPATH
    os.environ['PYTHONPATH'] = os.pathsep.join([p for p in paths if os.path.exists(p)])
    
    print(f"✓ Python paths set: {len([p for p in paths if os.path.exists(p)])} paths")
    return current_dir

def install_missing_dependencies():
    """Install missing dependencies"""
    print("🔍 Checking dependencies...")
    
    missing_deps = []
    
    # Check pydantic-settings
    try:
        from pydantic_settings import BaseSettings
    except ImportError:
        missing_deps.append("pydantic-settings>=2.0.0")
    
    # Check whisper
    try:
        import whisper
    except ImportError:
        missing_deps.append("openai-whisper>=20231117")
    
    # Check WeTextProcessing
    try:
        import WeTextProcessing
    except ImportError:
        missing_deps.append("WeTextProcessing>=1.0.3")
    
    # Check transformers version
    try:
        from transformers import Qwen2ForCausalLM
    except ImportError:
        try:
            import transformers
            print(f"⚠️  transformers {transformers.__version__} needs upgrade")
            missing_deps.append("transformers>=4.37.0")
        except ImportError:
            missing_deps.append("transformers>=4.37.0")
    
    if missing_deps:
        print(f"⚠️  Installing: {', '.join(missing_deps)}")
        for dep in missing_deps:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
        print("✓ Dependencies installed")
    else:
        print("✓ All dependencies OK")

def fix_models_directory(current_dir):
    """Fix missing app/models directory"""
    print("🔍 Checking app/models directory...")
    
    app_models_dir = os.path.join(current_dir, 'app', 'models')
    if os.path.exists(app_models_dir):
        print("✓ app/models directory exists")
        return True
    
    print("⚠️  Creating app/models directory...")
    
    # Run the fix_missing_models.py script
    fix_script = os.path.join(current_dir, 'fix_missing_models.py')
    if os.path.exists(fix_script):
        try:
            subprocess.check_call([sys.executable, fix_script])
            print("✓ app/models directory created")
            return True
        except Exception as e:
            print(f"❌ Failed to run fix script: {e}")
    
    # Manual creation if script fails
    try:
        os.makedirs(app_models_dir, exist_ok=True)
        
        # Create minimal __init__.py
        init_file = os.path.join(app_models_dir, '__init__.py')
        with open(init_file, 'w') as f:
            f.write('# Models package\n')
        
        print("✓ Created basic app/models directory")
        return True
    except Exception as e:
        print(f"❌ Failed to create models directory: {e}")
        return False

def fix_matcha_tts_imports(current_dir):
    """Fix Matcha-TTS import issues"""
    print("🔍 Checking Matcha-TTS setup...")
    
    matcha_tts_dir = os.path.join(current_dir, 'cosyvoice_original', 'third_party', 'Matcha-TTS')
    if not os.path.exists(matcha_tts_dir):
        print(f"⚠️  Matcha-TTS directory not found: {matcha_tts_dir}")
        return False
    
    # Check if matcha module exists
    matcha_src_dir = os.path.join(matcha_tts_dir, 'matcha')
    if not os.path.exists(matcha_src_dir):
        print(f"⚠️  Matcha source directory not found: {matcha_src_dir}")
        return False
    
    # Test import
    try:
        # Add to path temporarily for test
        if matcha_src_dir not in sys.path:
            sys.path.insert(0, matcha_src_dir)
        
        import matcha.models
        print("✓ Matcha-TTS import OK")
        return True
    except ImportError as e:
        print(f"⚠️  Matcha-TTS import issue: {e}")
        
        # Try to fix by creating __init__.py files if missing
        try:
            matcha_init = os.path.join(matcha_src_dir, '__init__.py')
            if not os.path.exists(matcha_init):
                with open(matcha_init, 'w') as f:
                    f.write('# Matcha package\n')
                print("✓ Created matcha/__init__.py")
            
            models_dir = os.path.join(matcha_src_dir, 'models')
            if os.path.exists(models_dir):
                models_init = os.path.join(models_dir, '__init__.py')
                if not os.path.exists(models_init):
                    with open(models_init, 'w') as f:
                        f.write('# Matcha models package\n')
                    print("✓ Created matcha/models/__init__.py")
            
            # Test again
            import matcha.models
            print("✓ Matcha-TTS import fixed")
            return True
        except Exception as fix_e:
            print(f"❌ Could not fix Matcha-TTS: {fix_e}")
            return False

def test_critical_imports():
    """Test critical imports"""
    print("🔍 Testing critical imports...")
    
    try:
        from app.core.config import settings
        print("✓ Config import OK")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from app.models.voice import VoiceCreate
        print("✓ Voice models import OK")
    except Exception as e:
        print(f"❌ Voice models import failed: {e}")
        return False
    
    try:
        from app.core.voice_cache import VoiceCache
        print("✓ Voice cache import OK")
    except Exception as e:
        print(f"❌ Voice cache import failed: {e}")
        return False
    
    print("✓ All critical imports successful")
    return True

def main():
    """Main fix function"""
    print("🔧 CosyVoice2 API - Comprehensive Fix")
    print("=" * 50)
    
    # Setup Python path
    current_dir = setup_python_path()
    
    # Install missing dependencies
    try:
        install_missing_dependencies()
    except Exception as e:
        print(f"⚠️  Dependency installation issue: {e}")
    
    # Fix models directory
    if not fix_models_directory(current_dir):
        print("❌ Could not fix models directory")
        return 1
    
    # Fix Matcha-TTS
    fix_matcha_tts_imports(current_dir)
    
    # Test imports
    if not test_critical_imports():
        print("❌ Critical imports still failing")
        return 1
    
    print("\n" + "=" * 50)
    print("🎉 All fixes applied successfully!")
    print("\nYou can now start the server with:")
    print("  python start.py")
    print("  or")
    print("  uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
