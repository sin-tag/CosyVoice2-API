#!/usr/bin/env python3
"""
Dependency compatibility fix script for CosyVoice2 API
Handles common version conflicts and compatibility issues
"""

import subprocess
import sys
import os
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

def run_command(command, description=""):
    """Run a command and return success status"""
    try:
        print_status(f"Running: {command}", "INFO")
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print_status(f"Command failed: {e}", "ERROR")
        if e.stderr:
            print(e.stderr.strip())
        return False

def check_pydantic_version():
    """Check and fix Pydantic version issues"""
    print_status("Checking Pydantic version...", "INFO")
    
    try:
        import pydantic
        version = pydantic.VERSION
        print_status(f"Pydantic version: {version}", "INFO")
        
        # Check if BaseSettings is available
        try:
            from pydantic import BaseSettings
            print_status("BaseSettings available in pydantic", "SUCCESS")
            return True
        except ImportError:
            print_status("BaseSettings not in pydantic, checking pydantic-settings", "WARNING")
            
            try:
                from pydantic_settings import BaseSettings
                print_status("BaseSettings available in pydantic-settings", "SUCCESS")
                return True
            except ImportError:
                print_status("pydantic-settings not installed", "ERROR")
                return False
                
    except ImportError:
        print_status("Pydantic not installed", "ERROR")
        return False

def fix_pydantic_dependencies():
    """Fix Pydantic dependency issues"""
    print_status("Fixing Pydantic dependencies...", "INFO")
    
    commands = [
        "pip install 'pydantic>=2.0.0,<3.0.0'",
        "pip install 'pydantic-settings>=2.0.0,<3.0.0'",
    ]
    
    for command in commands:
        if not run_command(command):
            return False
    
    return True

def fix_fastapi_dependencies():
    """Fix FastAPI and related dependencies"""
    print_status("Fixing FastAPI dependencies...", "INFO")
    
    commands = [
        "pip install 'fastapi>=0.104.0,<1.0.0'",
        "pip install 'uvicorn[standard]>=0.24.0,<1.0.0'",
        "pip install 'python-multipart>=0.0.6,<1.0.0'",
    ]
    
    for command in commands:
        if not run_command(command):
            return False
    
    return True

def fix_audio_dependencies():
    """Fix audio processing dependencies"""
    print_status("Fixing audio dependencies...", "INFO")
    
    # Check if we're in conda environment
    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    
    if conda_env:
        print_status(f"Detected conda environment: {conda_env}", "INFO")
        commands = [
            "conda install -c conda-forge librosa soundfile -y",
            "pip install torchaudio",
        ]
    else:
        commands = [
            "pip install librosa soundfile torchaudio",
        ]
    
    for command in commands:
        if not run_command(command):
            return False
    
    return True

def fix_pytorch_dependencies():
    """Fix PyTorch dependencies"""
    print_status("Checking PyTorch installation...", "INFO")
    
    try:
        import torch
        print_status(f"PyTorch version: {torch.__version__}", "SUCCESS")
        print_status(f"CUDA available: {torch.cuda.is_available()}", "INFO")
        return True
    except ImportError:
        print_status("PyTorch not installed", "ERROR")
        
        # Check if we're in conda environment
        conda_env = os.environ.get('CONDA_DEFAULT_ENV')
        
        if conda_env:
            print_status("Installing PyTorch with conda...", "INFO")
            command = "conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y"
        else:
            print_status("Installing PyTorch with pip...", "INFO")
            command = "pip install torch torchvision torchaudio"
        
        return run_command(command)

def reinstall_all_dependencies():
    """Reinstall all dependencies from requirements"""
    print_status("Reinstalling all dependencies...", "INFO")
    
    # Determine which requirements file to use
    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    
    if conda_env and Path("requirements-conda.txt").exists():
        requirements_file = "requirements-conda.txt"
        print_status("Using conda-specific requirements", "INFO")
    else:
        requirements_file = "requirements.txt"
        print_status("Using standard requirements", "INFO")
    
    if not Path(requirements_file).exists():
        print_status(f"Requirements file {requirements_file} not found", "ERROR")
        return False
    
    command = f"pip install -r {requirements_file} --upgrade"
    return run_command(command)

def clean_pip_cache():
    """Clean pip cache to avoid conflicts"""
    print_status("Cleaning pip cache...", "INFO")
    return run_command("pip cache purge")

def main():
    """Main fix function"""
    print_status("🔧 CosyVoice2 API Dependency Fix Tool", "INFO")
    print("=" * 60)
    
    fixes = [
        ("Clean pip cache", clean_pip_cache),
        ("Fix PyTorch dependencies", fix_pytorch_dependencies),
        ("Fix Pydantic dependencies", fix_pydantic_dependencies),
        ("Fix FastAPI dependencies", fix_fastapi_dependencies),
        ("Fix audio dependencies", fix_audio_dependencies),
        ("Reinstall all dependencies", reinstall_all_dependencies),
        ("Verify Pydantic", check_pydantic_version),
    ]
    
    success_count = 0
    for fix_name, fix_func in fixes:
        print(f"\n--- {fix_name} ---")
        try:
            if fix_func():
                print_status(f"{fix_name}: SUCCESS", "SUCCESS")
                success_count += 1
            else:
                print_status(f"{fix_name}: FAILED", "ERROR")
        except Exception as e:
            print_status(f"{fix_name}: ERROR - {e}", "ERROR")
    
    print("\n" + "=" * 60)
    print_status("🔧 DEPENDENCY FIX SUMMARY", "INFO")
    print("=" * 60)
    
    print(f"Completed: {success_count}/{len(fixes)} fixes")
    
    if success_count == len(fixes):
        print_status("✅ All dependency issues fixed!", "SUCCESS")
        print_status("You can now run: python main.py", "INFO")
        return 0
    else:
        print_status("⚠️ Some fixes failed. Check the errors above.", "WARNING")
        print_status("You may need to manually install missing packages.", "INFO")
        return 1

if __name__ == "__main__":
    sys.exit(main())
