#!/usr/bin/env python3
"""
Comprehensive dependency installer for CosyVoice2 API
Handles all the tricky dependencies and provides fallbacks
"""

import subprocess
import sys
import os
import platform

def run_command(cmd, check=True, capture_output=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, check=check, 
                              capture_output=capture_output, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout if e.stdout else "", e.stderr if e.stderr else str(e)

def install_pytorch_cuda():
    """Install PyTorch with CUDA 12.1 support"""
    print("🔥 Installing PyTorch with CUDA 12.1 support...")
    
    # Check if CUDA is available
    success, stdout, stderr = run_command("nvidia-smi", check=False)
    if success:
        print("✓ NVIDIA GPU detected, installing CUDA version")
        cmd = "pip install torch==2.1.2+cu121 torchaudio==2.1.2+cu121 --extra-index-url https://download.pytorch.org/whl/cu121"
    else:
        print("⚠️  No NVIDIA GPU detected, installing CPU version")
        cmd = "pip install torch==2.1.2 torchaudio==2.1.2"
    
    success, stdout, stderr = run_command(cmd)
    if success:
        print("✓ PyTorch installed successfully")
    else:
        print(f"❌ Failed to install PyTorch: {stderr}")
        # Fallback to latest stable
        print("🔄 Trying fallback PyTorch installation...")
        success, _, _ = run_command("pip install torch torchaudio")
        if success:
            print("✓ Fallback PyTorch installation successful")
        else:
            print("❌ PyTorch installation failed completely")
            return False
    return True

def install_numpy_compatible():
    """Install NumPy version compatible with compiled modules"""
    print("🔢 Installing compatible NumPy version...")
    success, _, stderr = run_command('pip install "numpy<2"')
    if success:
        print("✓ Compatible NumPy installed")
    else:
        print(f"❌ Failed to install NumPy: {stderr}")
        return False
    return True

def install_core_dependencies():
    """Install core dependencies that must work"""
    print("📦 Installing core dependencies...")
    
    core_deps = [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0", 
        "python-multipart>=0.0.6",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "transformers>=4.37.0",
        "librosa>=0.10.0",
        "soundfile>=0.12.0",
        "scipy>=1.11.0",
        "openai-whisper>=20231117",
        "modelscope>=1.9.0",
        "hyperpyyaml>=1.2.0",
        "onnxruntime>=1.16.0",
        "pypinyin>=0.50.0",
        "jieba>=0.42.0",
        "aiofiles>=23.0.0",
        "gradio",
        "lightning",
        "omegaconf",
        "diffusers",
        "hydra-core",
        "gdown",
        "matplotlib",
        "pyarrow",
        "pyworld",
        "wetext",
        "conformer",
        "inflect",
        "eng_to_ipa",
        "unidecode", 
        "cn2an",
        "num2words"
    ]
    
    failed_deps = []
    for dep in core_deps:
        print(f"  Installing {dep}...")
        success, _, stderr = run_command(f"pip install {dep}")
        if not success:
            print(f"  ❌ Failed: {dep}")
            failed_deps.append(dep)
        else:
            print(f"  ✓ Success: {dep}")
    
    if failed_deps:
        print(f"⚠️  Some core dependencies failed: {failed_deps}")
        return False
    
    print("✓ All core dependencies installed successfully")
    return True

def install_optional_dependencies():
    """Install optional dependencies that may fail"""
    print("🔧 Installing optional dependencies...")
    
    optional_deps = [
        ("WeTextProcessing>=1.0.3", "Text processing (may fail due to compilation)"),
        ("pynini", "Text normalization"),
        ("openfst-python", "OpenFST bindings"),
        ("seaborn", "Data visualization"),
        ("wandb", "Experiment tracking"),
        ("tensorboard", "TensorBoard logging"),
        ("rich", "Rich text formatting"),
        ("wget", "File downloading")
    ]
    
    for dep, desc in optional_deps:
        print(f"  Installing {dep} ({desc})...")
        success, _, stderr = run_command(f"pip install {dep}")
        if not success:
            print(f"  ⚠️  Optional dependency failed: {dep}")
        else:
            print(f"  ✓ Success: {dep}")
    
    print("✓ Optional dependencies installation completed")
    return True

def verify_installation():
    """Verify that key packages can be imported"""
    print("🔍 Verifying installation...")
    
    test_imports = [
        ("torch", "PyTorch"),
        ("torchaudio", "TorchAudio"), 
        ("numpy", "NumPy"),
        ("fastapi", "FastAPI"),
        ("librosa", "Librosa"),
        ("transformers", "Transformers"),
        ("gradio", "Gradio"),
        ("wetext", "WeText (fallback for WeTextProcessing)")
    ]
    
    failed_imports = []
    for module, name in test_imports:
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError as e:
            print(f"  ❌ {name}: {e}")
            failed_imports.append(name)
    
    if failed_imports:
        print(f"⚠️  Some imports failed: {failed_imports}")
        return False
    
    print("✓ All key packages verified successfully")
    return True

def main():
    """Main installation process"""
    print("🚀 CosyVoice2 API Dependency Installer")
    print("=" * 50)
    
    # Check Python version
    python_version = sys.version_info
    print(f"🐍 Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    
    # Upgrade pip first
    print("📦 Upgrading pip...")
    run_command("python -m pip install --upgrade pip")
    
    # Install setuptools and wheel
    print("🔧 Installing build tools...")
    run_command("pip install setuptools wheel")
    
    # Install dependencies in order
    steps = [
        ("Installing compatible NumPy", install_numpy_compatible),
        ("Installing PyTorch with CUDA support", install_pytorch_cuda),
        ("Installing core dependencies", install_core_dependencies),
        ("Installing optional dependencies", install_optional_dependencies),
        ("Verifying installation", verify_installation)
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ Step failed: {step_name}")
            print("⚠️  Installation completed with errors")
            return False
    
    print("\n🎉 Installation completed successfully!")
    print("\n📝 Next steps:")
    print("  1. Run: python main.py  (or use run_server.sh/run_server.bat)")
    print("  2. Access API at: http://localhost:8000")
    print("  3. View docs at: http://localhost:8000/docs")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
