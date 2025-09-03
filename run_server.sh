#!/bin/bash

# CosyVoice2 API Server Setup and Run Script
# This script automates the complete setup and running of the CosyVoice2 API server

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_VERSION="3.10"
VENV_NAME="venv"
DEFAULT_PORT=8000
DEFAULT_HOST="0.0.0.0"
DEFAULT_WORKERS=1

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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    else
        print_error "Python not found. Please install Python $PYTHON_VERSION or higher."
        exit 1
    fi

    PYTHON_VER=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    print_status "Found Python version: $PYTHON_VER"
    
    # Check if Python version is at least 3.10
    if [[ $(echo "$PYTHON_VER 3.10" | tr " " "\n" | sort -V | head -n1) != "3.10" ]]; then
        print_warning "Python version $PYTHON_VER detected. Recommended version is $PYTHON_VERSION or higher."
    fi
}

# Function to setup virtual environment
setup_venv() {
    print_status "Setting up virtual environment..."
    
    if [ -d "$VENV_NAME" ]; then
        print_warning "Virtual environment already exists. Removing old environment..."
        rm -rf "$VENV_NAME"
    fi
    
    $PYTHON_CMD -m venv "$VENV_NAME"
    print_success "Virtual environment created successfully"
    
    # Activate virtual environment
    source "$VENV_NAME/bin/activate" || source "$VENV_NAME/Scripts/activate"
    print_success "Virtual environment activated"
    
    # Upgrade pip
    print_status "Upgrading pip..."
    python -m pip install --upgrade pip
    print_success "Pip upgraded successfully"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing dependencies using comprehensive installer..."

    # Use the comprehensive Python installer
    if [ -f "install_dependencies.py" ]; then
        python install_dependencies.py
        if [ $? -eq 0 ]; then
            print_success "Dependencies installation completed successfully"
        else
            print_warning "Comprehensive installer had some issues, trying fallback installation..."
            install_dependencies_fallback
        fi
    else
        print_warning "Comprehensive installer not found, using fallback installation..."
        install_dependencies_fallback
    fi
}

# Fallback dependency installation
install_dependencies_fallback() {
    print_status "Installing dependencies (fallback method)..."

    # Install basic dependencies first
    print_status "Installing setuptools and wheel..."
    pip install setuptools wheel

    # Install PyTorch with CUDA 12.1 support
    print_status "Installing PyTorch with CUDA 12.1 support..."
    pip install torch==2.2.2+cu121 torchaudio==2.2.2+cu121 --extra-index-url https://download.pytorch.org/whl/cu121 || {
        print_warning "CUDA version failed, trying CPU version..."
        pip install torch==2.2.2 torchaudio==2.2.2
    }

    # Install NumPy with version constraint
    print_status "Installing NumPy (compatible version)..."
    pip install "numpy<2"

    # Install core dependencies
    print_status "Installing core dependencies..."
    pip install fastapi uvicorn[standard] python-multipart pydantic pydantic-settings

    # Install audio processing libraries
    print_status "Installing audio processing libraries..."
    pip install librosa soundfile

    # Install ML/AI libraries
    print_status "Installing ML/AI libraries..."
    pip install transformers modelscope

    # Install additional discovered dependencies
    print_status "Installing additional dependencies..."
    pip install gradio lightning omegaconf diffusers hydra-core
    pip install gdown matplotlib pyarrow pyworld wetext conformer
    pip install seaborn wandb tensorboard rich inflect
    pip install eng_to_ipa unidecode cn2an num2words openai-whisper

    # Install CosyVoice specific dependencies
    print_status "Installing CosyVoice specific dependencies..."
    pip install hyperpyyaml onnxruntime pypinyin jieba

    # Try to install text processing dependencies
    print_status "Installing text processing dependencies..."
    pip install pynini openfst-python || print_warning "Some text processing dependencies failed to install"

    # Try to install WeTextProcessing (may fail on some systems)
    print_status "Attempting to install WeTextProcessing..."
    pip install WeTextProcessing>=1.0.3 || print_warning "WeTextProcessing installation failed, using wetext fallback instead"

    print_success "Fallback dependencies installation completed"
}

# Function to setup model directory
setup_models() {
    print_status "Setting up model directory..."
    
    if [ -d "models/iic/CosyVoice2-0___5B" ] && [ ! -d "models/CosyVoice2-0.5B" ]; then
        print_status "Creating model directory symlink..."
        if command_exists ln; then
            ln -sf "iic/CosyVoice2-0___5B" "models/CosyVoice2-0.5B"
        else
            cp -r "models/iic/CosyVoice2-0___5B" "models/CosyVoice2-0.5B"
        fi
        print_success "Model directory setup completed"
    fi
    
    # Create cosyvoice.yaml if it doesn't exist
    if [ -f "models/CosyVoice2-0.5B/cosyvoice2.yaml" ] && [ ! -f "models/CosyVoice2-0.5B/cosyvoice.yaml" ]; then
        print_status "Creating cosyvoice.yaml symlink..."
        if command_exists ln; then
            ln -sf "cosyvoice2.yaml" "models/CosyVoice2-0.5B/cosyvoice.yaml"
        else
            cp "models/CosyVoice2-0.5B/cosyvoice2.yaml" "models/CosyVoice2-0.5B/cosyvoice.yaml"
        fi
        print_success "Configuration file setup completed"
    fi
}

# Function to check if port is available
check_port() {
    local port=$1
    if command_exists netstat; then
        if netstat -tuln | grep -q ":$port "; then
            return 1
        fi
    elif command_exists ss; then
        if ss -tuln | grep -q ":$port "; then
            return 1
        fi
    fi
    return 0
}

# Function to find available port
find_available_port() {
    local start_port=$1
    local port=$start_port
    
    while ! check_port $port; do
        print_warning "Port $port is already in use"
        port=$((port + 1))
        if [ $port -gt $((start_port + 100)) ]; then
            print_error "Could not find available port after checking 100 ports starting from $start_port"
            exit 1
        fi
    done
    
    echo $port
}

# Function to start the server
start_server() {
    local host=${1:-$DEFAULT_HOST}
    local port=${2:-$DEFAULT_PORT}
    local workers=${3:-$DEFAULT_WORKERS}
    
    print_status "Starting CosyVoice2 API server..."
    
    # Find available port if the default is taken
    available_port=$(find_available_port $port)
    if [ $available_port -ne $port ]; then
        print_warning "Port $port is not available, using port $available_port instead"
        port=$available_port
    fi
    
    print_status "Server configuration:"
    print_status "  Host: $host"
    print_status "  Port: $port"
    print_status "  Workers: $workers"
    print_status "  Access URL: http://localhost:$port"
    print_status "  API Documentation: http://localhost:$port/docs"
    
    # Activate virtual environment
    source "$VENV_NAME/bin/activate" || source "$VENV_NAME/Scripts/activate"
    
    print_success "Starting server..."
    uvicorn main:app --host "$host" --port "$port" --workers "$workers"
}

# Function to clean up unnecessary files
cleanup_files() {
    print_status "Cleaning up unnecessary files..."
    
    # Remove Python cache files
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "*.pyo" -delete 2>/dev/null || true
    
    # Remove temporary files
    rm -rf .pytest_cache 2>/dev/null || true
    rm -rf .coverage 2>/dev/null || true
    rm -rf htmlcov 2>/dev/null || true
    
    print_success "Cleanup completed"
}

# Main execution
main() {
    print_status "🚀 CosyVoice2 API Server Setup and Run Script"
    print_status "=============================================="
    
    # Parse command line arguments
    HOST=$DEFAULT_HOST
    PORT=$DEFAULT_PORT
    WORKERS=$DEFAULT_WORKERS
    SKIP_SETUP=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host)
                HOST="$2"
                shift 2
                ;;
            --port)
                PORT="$2"
                shift 2
                ;;
            --workers)
                WORKERS="$2"
                shift 2
                ;;
            --skip-setup)
                SKIP_SETUP=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --host HOST        Host to bind to (default: $DEFAULT_HOST)"
                echo "  --port PORT        Port to bind to (default: $DEFAULT_PORT)"
                echo "  --workers WORKERS  Number of workers (default: $DEFAULT_WORKERS)"
                echo "  --skip-setup       Skip environment setup and dependency installation"
                echo "  --help             Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    if [ "$SKIP_SETUP" = false ]; then
        # Check Python version
        check_python_version
        
        # Setup virtual environment
        setup_venv
        
        # Install dependencies
        install_dependencies
        
        # Setup models
        setup_models
        
        # Cleanup unnecessary files
        cleanup_files
        
        print_success "Setup completed successfully!"
    else
        print_status "Skipping setup as requested"
    fi
    
    # Start the server
    start_server "$HOST" "$PORT" "$WORKERS"
}

# Run main function with all arguments
main "$@"
