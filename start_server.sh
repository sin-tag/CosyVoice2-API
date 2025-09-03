#!/bin/bash

# CosyVoice2 API Server Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_status "Starting CosyVoice2 API Server..."
print_status "Working directory: $SCRIPT_DIR"

# Set Python path
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/cosyvoice_original:$SCRIPT_DIR/cosyvoice_original/third_party/Matcha-TTS:$PYTHONPATH"
print_status "PYTHONPATH set: $PYTHONPATH"

# Check if conda environment is active
if [[ -n "$CONDA_DEFAULT_ENV" ]]; then
    print_success "Conda environment active: $CONDA_DEFAULT_ENV"
else
    print_warning "No conda environment detected. Make sure you have activated the correct environment."
fi

# Check if required files exist
if [[ ! -f "main.py" ]]; then
    print_error "main.py not found in current directory"
    exit 1
fi

if [[ ! -d "app" ]]; then
    print_error "app directory not found"
    exit 1
fi

# Test imports
print_status "Testing critical imports..."
python -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
try:
    from app.core.config import settings
    print('✓ Config import OK')
    from app.models.voice import VoiceCreate
    print('✓ Voice models import OK')
    print('✓ All imports successful')
except Exception as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
" || {
    print_error "Import test failed"
    exit 1
}

# Parse command line arguments
HOST=${1:-"0.0.0.0"}
PORT=${2:-"8000"}
RELOAD=${3:-"--reload"}

print_status "Server configuration:"
print_status "  Host: $HOST"
print_status "  Port: $PORT"
print_status "  Reload: $RELOAD"

# Start the server
print_status "Starting uvicorn server..."

if command -v uvicorn &> /dev/null; then
    exec uvicorn main:app --host "$HOST" --port "$PORT" $RELOAD
else
    print_error "uvicorn not found. Please install it with: pip install uvicorn"
    exit 1
fi
