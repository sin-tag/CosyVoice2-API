#!/usr/bin/env python3
"""
Check CosyVoice dependencies and version compatibility
"""

import sys
import os

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def check_dependency(name, import_path, min_version=None):
    """Check if a dependency is available and optionally check version"""
    try:
        module = __import__(import_path)
        if hasattr(module, '__version__'):
            version = module.__version__
            print(f"✓ {name}: {version}")
            if min_version and version < min_version:
                print(f"  ⚠️  Version {version} < required {min_version}")
                return False
        else:
            print(f"✓ {name}: Available (no version info)")
        return True
    except ImportError as e:
        print(f"❌ {name}: Not available - {e}")
        return False

def check_transformers_qwen():
    """Check if transformers has Qwen2ForCausalLM"""
    try:
        from transformers import Qwen2ForCausalLM
        print("✓ transformers: Qwen2ForCausalLM available")
        return True
    except ImportError:
        try:
            import transformers
            print(f"❌ transformers {transformers.__version__}: Qwen2ForCausalLM not available")
            print("  💡 Need transformers >= 4.37.0")
            return False
        except ImportError:
            print("❌ transformers: Not installed")
            return False

def main():
    """Main check function"""
    print("🔍 Checking CosyVoice Dependencies")
    print("=" * 50)
    
    # Core dependencies
    deps = [
        ("PyTorch", "torch"),
        ("TorchAudio", "torchaudio"),
        ("Transformers", "transformers"),
        ("NumPy", "numpy"),
        ("SciPy", "scipy"),
        ("Librosa", "librosa"),
        ("SoundFile", "soundfile"),
        ("FastAPI", "fastapi"),
        ("Uvicorn", "uvicorn"),
        ("Pydantic", "pydantic"),
        ("Pydantic Settings", "pydantic_settings"),
        ("ModelScope", "modelscope"),
        ("Whisper", "whisper"),
        ("WeTextProcessing", "WeTextProcessing"),
        ("HyperPyYAML", "hyperpyyaml"),
        ("ONNX Runtime", "onnxruntime"),
        ("PyPinyin", "pypinyin"),
        ("Jieba", "jieba"),
    ]
    
    results = []
    for name, import_path in deps:
        results.append(check_dependency(name, import_path))
    
    print("\n" + "=" * 50)
    print("🔍 Special Checks")
    print("=" * 50)
    
    # Special check for Qwen2ForCausalLM
    qwen_ok = check_transformers_qwen()
    results.append(qwen_ok)
    
    # Check CUDA
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✓ CUDA: Available ({torch.cuda.device_count()} devices)")
            print(f"  Primary GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("⚠️  CUDA: Not available (using CPU)")
    except:
        print("❌ CUDA: Cannot check")
    
    print("\n" + "=" * 50)
    print("📊 Summary")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Dependencies: {passed}/{total} OK")
    
    if passed == total:
        print("🎉 All dependencies are ready!")
        print("You can start the server with: python start.py")
        return 0
    else:
        print("⚠️  Some dependencies are missing or outdated")
        print("\n💡 To fix missing dependencies:")
        print("   pip install -r requirements.txt")
        print("   or")
        print("   python start.py  # (auto-installs missing deps)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
