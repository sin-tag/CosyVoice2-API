#!/bin/bash

# CosyVoice2 API Setup Script

set -e

echo "Setting up CosyVoice2 API..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p models
mkdir -p voice_cache
mkdir -p outputs
mkdir -p logs

# Copy environment file
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
fi

# Download model (optional)
echo "To download CosyVoice2 model, run:"
echo "python scripts/download_model.py"

echo "Setup complete!"
echo "To start the server, run: python main.py"
