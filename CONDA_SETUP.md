# CosyVoice2 API - Conda Setup Guide

This guide provides detailed instructions for setting up CosyVoice2 API using Conda environment management.

## Prerequisites

- Anaconda or Miniconda installed
- CUDA-compatible GPU (recommended)
- At least 8GB RAM
- 10GB+ disk space

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API
```

### 2. Create Conda Environment

```bash
# Create new conda environment with Python 3.9
conda create -n cosyvoice2-api python=3.9 -y

# Activate the environment
conda activate cosyvoice2-api
```

### 3. Install System Dependencies

#### For Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y build-essential ffmpeg git curl
```

#### For CentOS/RHEL:
```bash
sudo yum update -y
sudo yum install -y gcc gcc-c++ make ffmpeg git curl
```

#### For macOS:
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install ffmpeg git
```

### 4. Install PyTorch with CUDA Support

#### For CUDA 11.8 (recommended):
```bash
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y
```

#### For CUDA 12.1:
```bash
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y
```

#### For CPU-only (not recommended for production):
```bash
conda install pytorch torchvision torchaudio cpuonly -c pytorch -y
```

### 5. Install Audio Processing Libraries

```bash
# Install conda packages first
conda install -y numpy scipy

# Install librosa and soundfile via conda-forge
conda install -c conda-forge librosa soundfile -y
```

### 6. Install Other Dependencies

```bash
# Install remaining packages via pip
pip install fastapi uvicorn[standard] python-multipart
pip install pydantic pydantic-settings
pip install aiofiles python-jose[cryptography] httpx
pip install tqdm hyperpyyaml onnxruntime
pip install modelscope transformers

# Install text processing dependencies
pip install pypinyin jieba inflect eng_to_ipa unidecode cn2an num2words

# Install testing dependencies
pip install pytest pytest-asyncio black flake8
```

### 7. Create Required Directories

```bash
mkdir -p models voice_cache outputs logs temp
```

### 8. Setup Configuration

```bash
# Copy environment configuration
cp .env.example .env

# Edit configuration (optional)
nano .env
```

### 9. Download CosyVoice2 Model

```bash
# Using the provided script
python scripts/download_model.py

# Or specify a different model
python scripts/download_model.py --model-id iic/CosyVoice2-0.5B --target-dir models
```

### 10. Verify Installation

```bash
# Test PyTorch CUDA availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Test audio libraries
python -c "import librosa, soundfile; print('Audio libraries OK')"

# Test CosyVoice imports
python -c "from cosyvoice.cli.cosyvoice import CosyVoice; print('CosyVoice import OK')"
```

## Running the Application

### 1. Activate Environment

```bash
conda activate cosyvoice2-api
```

### 2. Start the Server

#### Development Mode:
```bash
python main.py
```

#### Production Mode with Gunicorn:
```bash
# Install gunicorn first
pip install gunicorn

# Run with gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 3. Access the API

- API Server: http://localhost:8000
- Interactive Documentation: http://localhost:8000/docs
- Alternative Documentation: http://localhost:8000/redoc

## Environment Management

### Useful Conda Commands

```bash
# List all environments
conda env list

# Activate environment
conda activate cosyvoice2-api

# Deactivate environment
conda deactivate

# Update packages
conda update --all

# Export environment
conda env export > environment.yml

# Create environment from file
conda env create -f environment.yml

# Remove environment
conda env remove -n cosyvoice2-api
```

### Export Environment for Sharing

```bash
# Export conda environment
conda env export --no-builds > environment.yml

# Export pip requirements
pip freeze > requirements-conda.txt
```

## Troubleshooting

### Common Issues and Solutions

#### 1. CUDA Not Available
```bash
# Check NVIDIA driver
nvidia-smi

# Reinstall PyTorch with correct CUDA version
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia --force-reinstall
```

#### 2. Audio Library Issues
```bash
# Reinstall audio libraries
conda remove librosa soundfile -y
conda install -c conda-forge librosa soundfile -y
```

#### 3. Model Download Issues
```bash
# Check internet connection and try again
python scripts/download_model.py

# Or download manually from ModelScope/HuggingFace
```

#### 4. Import Errors
```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Ensure you're in the right directory and environment
pwd
conda info --envs
```

#### 5. Permission Issues
```bash
# Fix permissions
chmod -R 755 scripts/
chmod +x scripts/setup.sh
```

### Performance Optimization

#### 1. GPU Memory Management
```bash
# Set CUDA memory fraction (optional)
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
```

#### 2. CPU Optimization
```bash
# Set number of threads
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
```

## Development Setup

### 1. Install Development Dependencies

```bash
conda activate cosyvoice2-api

# Install development tools
pip install black flake8 isort mypy
pip install jupyter notebook ipython

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### 2. Code Formatting

```bash
# Format code with black
black app/ tests/ main.py

# Check code style
flake8 app/ tests/ main.py

# Sort imports
isort app/ tests/ main.py
```

### 3. Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pip install pytest-cov
pytest --cov=app tests/

# Run specific test file
pytest tests/test_voice_cache.py -v
```

## Production Deployment with Conda

### 1. Create Production Environment

```bash
# Create production environment
conda create -n cosyvoice2-prod python=3.9 -y
conda activate cosyvoice2-prod

# Install production dependencies only
pip install -r requirements.txt --no-dev
```

### 2. Systemd Service with Conda

Create `/etc/systemd/system/cosyvoice2-api.service`:

```ini
[Unit]
Description=CosyVoice2 API
After=network.target

[Service]
Type=exec
User=your-user
Group=your-group
WorkingDirectory=/path/to/CosyVoice2-API
Environment=PATH=/home/your-user/miniconda3/envs/cosyvoice2-prod/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/home/your-user/miniconda3/envs/cosyvoice2-prod/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Environment Variables for Production

```bash
# Create production .env file
cp .env.example .env.prod

# Edit for production
cat > .env.prod << EOF
HOST=0.0.0.0
PORT=8000
DEBUG=false
MODEL_DIR=/path/to/models/CosyVoice2-0.5B
VOICE_CACHE_DIR=/path/to/voice_cache
OUTPUT_DIR=/path/to/outputs
MAX_FILE_SIZE=52428800
CLEANUP_INTERVAL=3600
EOF
```

## Updating the Application

### 1. Update Code

```bash
# Activate environment
conda activate cosyvoice2-api

# Pull latest changes
git pull origin main

# Update dependencies if needed
pip install -r requirements.txt --upgrade
```

### 2. Update Models

```bash
# Re-download models if needed
python scripts/download_model.py --force
```

### 3. Restart Service

```bash
# If using systemd
sudo systemctl restart cosyvoice2-api

# If running manually
# Stop the current process and restart
python main.py
```

## Backup and Restore

### 1. Backup Important Data

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Backup voice cache
cp -r voice_cache/ backups/$(date +%Y%m%d)/

# Backup configuration
cp .env backups/$(date +%Y%m%d)/

# Export conda environment
conda env export > backups/$(date +%Y%m%d)/environment.yml
```

### 2. Restore from Backup

```bash
# Restore voice cache
cp -r backups/20231201/voice_cache/ ./

# Restore configuration
cp backups/20231201/.env ./

# Recreate conda environment
conda env create -f backups/20231201/environment.yml
```

This comprehensive conda setup guide should help users get the CosyVoice2 API running without Docker!
