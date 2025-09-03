# CosyVoice2 API - Troubleshooting Guide

This guide helps you resolve common issues when setting up and running CosyVoice2 API.

## Quick Fix Script

For most dependency issues, try running the automatic fix script first:

```bash
python scripts/fix_dependencies.py
```

## Common Issues and Solutions

### 1. Pydantic Import Error

**Error:**
```
pydantic.errors.PydanticImportError: `BaseSettings` has been moved to the `pydantic-settings` package
```

**Solution:**
```bash
# Install the correct pydantic packages
pip install "pydantic>=2.0.0,<3.0.0"
pip install "pydantic-settings>=2.0.0,<3.0.0"

# Or run the fix script
python scripts/fix_dependencies.py
```

### 2. FastAPI Version Conflicts

**Error:**
```
ImportError: cannot import name 'X' from 'fastapi'
```

**Solution:**
```bash
# Update FastAPI and related packages
pip install "fastapi>=0.104.0,<1.0.0"
pip install "uvicorn[standard]>=0.24.0,<1.0.0"
pip install "python-multipart>=0.0.6,<1.0.0"
```

### 3. PyTorch CUDA Issues

**Error:**
```
RuntimeError: CUDA error: no kernel image is available for execution on the device
```

**Solutions:**

#### Option A: Reinstall PyTorch with correct CUDA version
```bash
# Check your CUDA version
nvidia-smi

# For CUDA 11.8
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia --force-reinstall

# For CUDA 12.1
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia --force-reinstall

# For CPU-only (fallback)
conda install pytorch torchvision torchaudio cpuonly -c pytorch --force-reinstall
```

#### Option B: Use pip installation
```bash
# For CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# For CPU-only
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 4. Audio Library Issues

**Error:**
```
ImportError: No module named 'librosa'
OSError: cannot load library 'libsndfile.so'
```

**Solutions:**

#### For Conda users:
```bash
conda install -c conda-forge librosa soundfile -y
```

#### For pip users:
```bash
# Install system dependencies first
# Ubuntu/Debian:
sudo apt-get install libsndfile1-dev

# macOS:
brew install libsndfile

# Then install Python packages
pip install librosa soundfile
```

### 5. Model Download Issues

**Error:**
```
ConnectionError: Failed to download model
HTTPError: 404 Client Error
```

**Solutions:**
```bash
# Try different model IDs
python scripts/download_model.py --model-id iic/CosyVoice-300M
python scripts/download_model.py --model-id iic/CosyVoice2-0.5B

# Check internet connection and try again
ping google.com

# Use manual download if needed
# Visit: https://www.modelscope.cn/models/iic/CosyVoice2-0.5B
```

### 6. Memory Issues

**Error:**
```
RuntimeError: CUDA out of memory
MemoryError: Unable to allocate array
```

**Solutions:**
```bash
# Reduce batch size in environment
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Monitor GPU memory
nvidia-smi

# Use CPU-only mode if needed
export CUDA_VISIBLE_DEVICES=""
```

### 7. Permission Issues

**Error:**
```
PermissionError: [Errno 13] Permission denied
```

**Solutions:**
```bash
# Fix script permissions
chmod +x scripts/*.sh
chmod +x scripts/*.py

# Fix directory permissions
chmod -R 755 voice_cache/ outputs/ logs/

# Don't run as root (create regular user)
sudo useradd -m cosyvoice
sudo su - cosyvoice
```

### 8. Port Already in Use

**Error:**
```
OSError: [Errno 98] Address already in use
```

**Solutions:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
python main.py --port 8001

# Or set in environment
export PORT=8001
```

### 9. Import Path Issues

**Error:**
```
ModuleNotFoundError: No module named 'cosyvoice'
ModuleNotFoundError: No module named 'app'
ModuleNotFoundError: No module named 'app.models'
```

**Solutions:**

#### Option 1: Use the startup scripts (Recommended)
```bash
# Use the robust startup script
./start_server.sh

# Or use the Python launcher
python run_server.py
```

#### Option 2: Manual Python path setup
```bash
# Make sure you're in the project directory
cd /path/to/CosyVoice2-API

# Set PYTHONPATH properly
export PYTHONPATH="$(pwd):$(pwd)/cosyvoice_original:$(pwd)/cosyvoice_original/third_party/Matcha-TTS:$PYTHONPATH"

# Then start the server
python main.py
```

#### Option 3: Test imports first
```bash
# Run the import test
python test_imports.py

# If successful, then start server
python main.py
```

### 10. Environment Issues

**Error:**
```
conda: command not found
pip: command not found
```

**Solutions:**
```bash
# Activate conda environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate cosyvoice2-api

# Or activate virtual environment
source venv/bin/activate

# Check which python you're using
which python
which pip
```

## Environment-Specific Issues

### Ubuntu/Debian Issues

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y build-essential python3-dev
sudo apt-get install -y ffmpeg libsndfile1-dev
sudo apt-get install -y curl git

# Fix locale issues
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
```

### CentOS/RHEL Issues

```bash
# Install system dependencies
sudo yum update -y
sudo yum groupinstall -y "Development Tools"
sudo yum install -y python3-devel
sudo yum install -y ffmpeg libsndfile-devel

# Enable EPEL repository if needed
sudo yum install -y epel-release
```

### macOS Issues

```bash
# Install Xcode command line tools
xcode-select --install

# Install Homebrew if needed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install ffmpeg libsndfile
```

### Windows Issues

```powershell
# Install Visual Studio Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Install ffmpeg
# Download from: https://ffmpeg.org/download.html
# Add to PATH

# Use Windows Subsystem for Linux (WSL) as alternative
wsl --install
```

## Advanced Troubleshooting

### Clean Installation

If you have persistent issues, try a clean installation:

```bash
# Remove existing environment
conda env remove -n cosyvoice2-api

# Clear pip cache
pip cache purge

# Remove project directory and re-clone
rm -rf CosyVoice2-API
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# Run setup again
./scripts/setup_conda.sh
```

### Debug Mode

Enable debug mode for more detailed error messages:

```bash
# Set debug environment
export DEBUG=true
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Run with verbose output
python -v main.py

# Check logs
tail -f logs/cosyvoice2-api.log
```

### Dependency Conflicts

Resolve complex dependency conflicts:

```bash
# Check for conflicts
pip check

# Create dependency graph
pip install pipdeptree
pipdeptree

# Force reinstall problematic packages
pip install --force-reinstall --no-deps <package_name>
```

## Getting Help

If you're still having issues:

1. **Run the verification script**: `python scripts/verify_installation.py`
2. **Run the fix script**: `python scripts/fix_dependencies.py`
3. **Check the logs**: Look in `logs/` directory for error details
4. **Create an issue**: Include the full error message and system info

### System Information to Include

When reporting issues, include:

```bash
# System info
uname -a
python --version
pip --version
conda --version

# Environment info
conda info
conda list
pip list

# GPU info (if applicable)
nvidia-smi
```

This information helps diagnose the problem quickly!
