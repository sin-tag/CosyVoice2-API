#!/bin/bash

# CosyVoice2 API Environment Setup Script for Linux
# This script sets up the complete environment for CosyVoice2 API

set -e  # Exit on any error

echo "🚀 CosyVoice2 API - Environment Setup for Linux"
echo "================================================"

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

# Check if Python 3.8+ is available
check_python() {
    print_status "Checking Python version..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python3"
        else
            print_error "Python 3.8+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 not found. Please install Python 3.8+"
        exit 1
    fi
}

# Check if CUDA is available
check_cuda() {
    print_status "Checking CUDA availability..."
    
    if command -v nvidia-smi &> /dev/null; then
        CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}')
        print_success "CUDA $CUDA_VERSION detected"
        USE_CUDA=true
    else
        print_warning "CUDA not detected, will use CPU version"
        USE_CUDA=false
    fi
}

# Create virtual environment
create_venv() {
    print_status "Creating virtual environment..."
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists, removing..."
        rm -rf venv
    fi
    
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    print_success "Virtual environment created and activated"
}

# Install PyTorch
install_pytorch() {
    print_status "Installing PyTorch..."
    
    if [ "$USE_CUDA" = true ]; then
        print_status "Installing PyTorch with CUDA support..."
        pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cu121
    else
        print_status "Installing PyTorch CPU version..."
        pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cpu
    fi
    
    print_success "PyTorch installed successfully"
}

# Install other dependencies
install_dependencies() {
    print_status "Installing other dependencies..."
    
    # Install grpcio with pre-built wheels
    pip install grpcio grpcio-tools --only-binary=all
    
    # Install main dependencies
    pip install conformer==0.3.2 \
                diffusers==0.29.0 \
                fastapi==0.115.6 \
                fastapi-cli==0.0.4 \
                gdown==5.1.0 \
                gradio==5.4.0 \
                hydra-core==1.3.2 \
                HyperPyYAML==1.2.2 \
                inflect==7.3.1 \
                librosa==0.10.2 \
                lightning==2.2.4 \
                matplotlib==3.7.5 \
                modelscope==1.20.0 \
                networkx==3.1 \
                omegaconf==2.3.0 \
                onnx==1.16.0 \
                onnxruntime==1.18.0 \
                openai-whisper==20231117 \
                pyarrow==18.1.0 \
                pydantic==2.7.0 \
                pyworld==0.3.4 \
                rich==13.7.1 \
                soundfile==0.12.1 \
                tensorboard==2.14.0 \
                transformers==4.51.3 \
                uvicorn==0.30.0 \
                wetext==0.0.4 \
                wget==3.2
    
    print_success "Dependencies installed successfully"
}

# Download CosyVoice source if not exists
setup_cosyvoice() {
    print_status "Setting up CosyVoice source code..."
    
    if [ ! -d "cosyvoice" ]; then
        print_status "Downloading CosyVoice source code..."
        
        # Create temp directory
        mkdir -p temp_cosyvoice
        cd temp_cosyvoice
        
        # Download and extract
        wget -q https://github.com/FunAudioLLM/CosyVoice/archive/refs/heads/main.zip
        unzip -q main.zip
        
        # Copy cosyvoice directory
        cp -r CosyVoice-main/cosyvoice ../
        
        # Cleanup
        cd ..
        rm -rf temp_cosyvoice
        
        print_success "CosyVoice source code downloaded"
    else
        print_success "CosyVoice source code already exists"
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p outputs
    mkdir -p voice_cache/audio
    mkdir -p voice_cache/metadata
    mkdir -p logs
    
    print_success "Directories created"
}

# Create run script
create_run_script() {
    print_status "Creating run script..."
    
    cat > run.sh << 'EOF'
#!/bin/bash

# CosyVoice2 API Quick Start Script
# This script starts the server without environment checks for faster startup

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting CosyVoice2 API Server...${NC}"

# Activate virtual environment
source venv/bin/activate

# Start server
echo -e "${GREEN}✓ Environment activated${NC}"
echo -e "${BLUE}🌐 Server will be available at: http://localhost:8013${NC}"
echo -e "${BLUE}📚 API Documentation: http://localhost:8013/docs${NC}"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8013 --workers 1
EOF

    chmod +x run.sh
    print_success "Run script created (run.sh)"
}

# Main setup function
main() {
    echo ""
    print_status "Starting environment setup..."
    echo ""
    
    check_python
    check_cuda
    create_venv
    install_pytorch
    install_dependencies
    setup_cosyvoice
    create_directories
    create_run_script
    
    echo ""
    print_success "🎉 Environment setup completed successfully!"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo -e "  1. Place your CosyVoice2 model in: ${BLUE}pretrained_models/CosyVoice2-0.5B${NC}"
    echo -e "  2. Start the server: ${BLUE}./run.sh${NC}"
    echo -e "  3. Access API docs: ${BLUE}http://localhost:8013/docs${NC}"
    echo ""
    echo -e "${YELLOW}Note:${NC} Make sure to download the CosyVoice2 model before starting the server"
    echo ""
}

# Run main function
main "$@"
