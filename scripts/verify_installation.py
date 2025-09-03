#!/usr/bin/env python3
"""
Installation verification script for CosyVoice2 API
"""

import sys
import os
import subprocess
from pathlib import Path

def print_status(message, status="INFO"):
    colors = {
        "INFO": "\033[0;34m",
        "SUCCESS": "\033[0;32m", 
        "WARNING": "\033[1;33m",
        "ERROR": "\033[0;31m",
        "NC": "\033[0m"
    }
    print(f"{colors.get(status, colors['INFO'])}[{status}]{colors['NC']} {message}")

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    print_status(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 9:
        print_status("Python version OK", "SUCCESS")
        return True
    else:
        print_status("Python 3.9+ required", "ERROR")
        return False

def check_conda_environment():
    """Check if running in conda environment"""
    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    if conda_env:
        print_status(f"Conda environment: {conda_env}", "SUCCESS")
        return True
    else:
        print_status("Not in conda environment", "WARNING")
        return False

def check_package_imports():
    """Check if required packages can be imported"""
    packages = [
        ("torch", "PyTorch"),
        ("torchaudio", "TorchAudio"),
        ("librosa", "Librosa"),
        ("soundfile", "SoundFile"),
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("numpy", "NumPy"),
        ("scipy", "SciPy"),
    ]
    
    success_count = 0
    for package, name in packages:
        try:
            __import__(package)
            print_status(f"{name}: OK", "SUCCESS")
            success_count += 1
        except ImportError as e:
            print_status(f"{name}: FAILED - {e}", "ERROR")
    
    return success_count == len(packages)

def check_cuda_availability():
    """Check CUDA availability"""
    try:
        import torch
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            device_name = torch.cuda.get_device_name(0) if device_count > 0 else "Unknown"
            print_status(f"CUDA available: {device_count} device(s)", "SUCCESS")
            print_status(f"Primary GPU: {device_name}", "INFO")
            return True
        else:
            print_status("CUDA not available - using CPU", "WARNING")
            return False
    except Exception as e:
        print_status(f"CUDA check failed: {e}", "ERROR")
        return False

def check_system_dependencies():
    """Check system dependencies"""
    dependencies = ["ffmpeg"]
    success_count = 0
    
    for dep in dependencies:
        try:
            result = subprocess.run([dep, "-version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_line = result.stderr.split('\n')[0] if result.stderr else "Unknown version"
                print_status(f"{dep}: OK - {version_line}", "SUCCESS")
                success_count += 1
            else:
                print_status(f"{dep}: Not found", "ERROR")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print_status(f"{dep}: Not found", "ERROR")
    
    return success_count == len(dependencies)

def check_directories():
    """Check if required directories exist"""
    directories = ["models", "voice_cache", "outputs", "logs"]
    success_count = 0
    
    for directory in directories:
        if Path(directory).exists():
            print_status(f"Directory '{directory}': OK", "SUCCESS")
            success_count += 1
        else:
            print_status(f"Directory '{directory}': Missing", "WARNING")
            # Create missing directory
            Path(directory).mkdir(exist_ok=True)
            print_status(f"Created directory '{directory}'", "INFO")
            success_count += 1
    
    return success_count == len(directories)

def check_configuration():
    """Check configuration files"""
    config_files = [".env", "requirements.txt"]
    success_count = 0
    
    for config_file in config_files:
        if Path(config_file).exists():
            print_status(f"Config file '{config_file}': OK", "SUCCESS")
            success_count += 1
        else:
            print_status(f"Config file '{config_file}': Missing", "WARNING")
    
    return success_count > 0

def check_cosyvoice_imports():
    """Check CosyVoice specific imports"""
    try:
        # Add current directory to path
        current_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(current_dir))
        
        from cosyvoice.cli.cosyvoice import CosyVoice
        print_status("CosyVoice import: OK", "SUCCESS")
        return True
    except ImportError as e:
        print_status(f"CosyVoice import: FAILED - {e}", "ERROR")
        return False

def check_model_availability():
    """Check if model directory exists"""
    model_paths = [
        "models/CosyVoice2-0.5B",
        "models/CosyVoice-300M",
        "models"
    ]
    
    for model_path in model_paths:
        if Path(model_path).exists():
            files = list(Path(model_path).glob("*"))
            if files:
                print_status(f"Model directory '{model_path}': OK ({len(files)} files)", "SUCCESS")
                return True
            else:
                print_status(f"Model directory '{model_path}': Empty", "WARNING")
    
    print_status("No model found. Run: python scripts/download_model.py", "WARNING")
    return False

def run_api_test():
    """Test if the API can start"""
    try:
        print_status("Testing API startup...", "INFO")
        
        # Import main app
        current_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(current_dir))
        
        from main import create_app
        app = create_app()
        print_status("API app creation: OK", "SUCCESS")
        return True
    except Exception as e:
        print_status(f"API test failed: {e}", "ERROR")
        return False

def main():
    """Main verification function"""
    print_status("🔍 CosyVoice2 API Installation Verification", "INFO")
    print("=" * 60)
    
    checks = [
        ("Python Version", check_python_version),
        ("Conda Environment", check_conda_environment),
        ("Package Imports", check_package_imports),
        ("CUDA Availability", check_cuda_availability),
        ("System Dependencies", check_system_dependencies),
        ("Required Directories", check_directories),
        ("Configuration Files", check_configuration),
        ("CosyVoice Imports", check_cosyvoice_imports),
        ("Model Availability", check_model_availability),
        ("API Startup Test", run_api_test),
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n--- {check_name} ---")
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print_status(f"Check failed with exception: {e}", "ERROR")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print_status("📊 VERIFICATION SUMMARY", "INFO")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        print_status("🎉 All checks passed! Installation is ready.", "SUCCESS")
        print_status("You can now run: python main.py", "INFO")
        return 0
    elif passed >= total * 0.8:
        print_status("⚠️  Most checks passed. Some issues may affect functionality.", "WARNING")
        print_status("Check the failed items above and fix them if needed.", "INFO")
        return 1
    else:
        print_status("❌ Multiple checks failed. Please fix the issues before running.", "ERROR")
        return 2

if __name__ == "__main__":
    sys.exit(main())
