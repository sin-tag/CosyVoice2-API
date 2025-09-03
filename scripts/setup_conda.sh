#!/bin/bash

# CosyVoice2 API Conda Setup Script

set -e

echo "🚀 Setting up CosyVoice2 API with Conda..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    print_error "Conda is not installed. Please install Anaconda or Miniconda first."
    echo "Download from: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

print_success "Conda found: $(conda --version)"

# Environment name
ENV_NAME="cosyvoice2-api"

# Check if environment already exists
if conda env list | grep -q "^${ENV_NAME} "; then
    print_warning "Environment '${ENV_NAME}' already exists."
    read -p "Do you want to remove and recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Removing existing environment..."
        conda env remove -n ${ENV_NAME} -y
    else
        print_status "Using existing environment..."
        conda activate ${ENV_NAME}
    fi
fi

# Create conda environment if it doesn't exist
if ! conda env list | grep -q "^${ENV_NAME} "; then
    print_status "Creating conda environment '${ENV_NAME}' with Python 3.9..."
    conda create -n ${ENV_NAME} python=3.9 -y
fi

# Activate environment
print_status "Activating conda environment..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate ${ENV_NAME}

# Check if CUDA is available
if command -v nvidia-smi &> /dev/null; then
    print_success "NVIDIA GPU detected"
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}' | cut -d. -f1,2)
    print_status "CUDA Version: ${CUDA_VERSION}"
    
    # Install PyTorch with CUDA support
    if [[ "${CUDA_VERSION}" == "11.8" ]] || [[ "${CUDA_VERSION}" > "11.8" ]]; then
        print_status "Installing PyTorch with CUDA 11.8 support..."
        conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y
    elif [[ "${CUDA_VERSION}" == "12."* ]]; then
        print_status "Installing PyTorch with CUDA 12.1 support..."
        conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y
    else
        print_warning "CUDA version ${CUDA_VERSION} detected. Installing PyTorch with CUDA 11.8..."
        conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y
    fi
else
    print_warning "No NVIDIA GPU detected. Installing CPU-only PyTorch..."
    conda install pytorch torchvision torchaudio cpuonly -c pytorch -y
fi

# Install audio processing libraries
print_status "Installing audio processing libraries..."
conda install -c conda-forge librosa soundfile -y

# Install system dependencies check
print_status "Checking system dependencies..."

# Check for ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    print_warning "ffmpeg not found. Please install it:"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
        echo "  CentOS/RHEL: sudo yum install ffmpeg"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  macOS: brew install ffmpeg"
    fi
else
    print_success "ffmpeg found: $(ffmpeg -version | head -n1)"
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install "fastapi>=0.104.0,<1.0.0" "uvicorn[standard]>=0.24.0,<1.0.0" "python-multipart>=0.0.6,<1.0.0"
pip install "pydantic>=2.0.0,<3.0.0" "pydantic-settings>=2.0.0,<3.0.0"
pip install aiofiles "python-jose[cryptography]" httpx
pip install tqdm hyperpyyaml onnxruntime
pip install modelscope transformers

# Install text processing dependencies
print_status "Installing text processing libraries..."
pip install pypinyin jieba inflect eng_to_ipa unidecode cn2an num2words

# Install development dependencies
print_status "Installing development dependencies..."
pip install pytest pytest-asyncio black flake8 "gunicorn>=21.0.0,<22.0.0"

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p models voice_cache outputs logs temp

# Copy environment configuration
if [ ! -f .env ]; then
    print_status "Creating .env configuration file..."
    cp .env.example .env
    print_success ".env file created. Please edit it with your configuration."
else
    print_warning ".env file already exists. Skipping..."
fi

# Test installation
print_status "Testing installation..."

# Test PyTorch
python -c "import torch; print(f'PyTorch version: {torch.__version__}')" || {
    print_error "PyTorch installation failed"
    exit 1
}

# Test CUDA availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Test audio libraries
python -c "import librosa, soundfile; print('Audio libraries: OK')" || {
    print_error "Audio libraries installation failed"
    exit 1
}

# Test FastAPI
python -c "import fastapi; print(f'FastAPI version: {fastapi.__version__}')" || {
    print_error "FastAPI installation failed"
    exit 1
}

print_success "Installation completed successfully!"
print_status "Next steps:"
echo "  1. Activate the environment: conda activate ${ENV_NAME}"
echo "  2. Download the model: python scripts/download_model.py"
echo "  3. Start the server: python main.py"
echo ""
print_status "The API will be available at: http://localhost:8000"
print_status "Interactive documentation: http://localhost:8000/docs"

# Save environment info
print_status "Saving environment information..."
conda env export > environment.yml
pip freeze > requirements-conda.txt

print_success "Environment exported to environment.yml and requirements-conda.txt"
print_success "Setup complete! 🎉"
print_status "If you encounter dependency issues, run: python scripts/fix_dependencies.py"
