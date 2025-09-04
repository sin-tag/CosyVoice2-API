# CosyVoice2 API Docker Image
FROM nvidia/cuda:12.1-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CUDA_VISIBLE_DEVICES=0

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3.10-venv \
    git \
    wget \
    curl \
    unzip \
    build-essential \
    cmake \
    pkg-config \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    sox \
    libsox-fmt-all \
    espeak-ng \
    espeak-ng-data \
    libespeak-ng-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link for python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python

# Upgrade pip
RUN python -m pip install --upgrade pip

# Install PyTorch with CUDA support
RUN pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2 --index-url https://download.pytorch.org/whl/cu121

# Install grpcio with pre-built wheels
RUN pip install grpcio grpcio-tools --only-binary=all

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for CosyVoice
RUN pip install \
    conformer==0.3.2 \
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
    wget==3.2 \
    aiohttp>=3.8.0

# Copy application code
COPY . .

# Download CosyVoice source code
RUN mkdir -p temp_cosyvoice && \
    cd temp_cosyvoice && \
    wget -q https://github.com/FunAudioLLM/CosyVoice/archive/refs/heads/main.zip && \
    unzip -q main.zip && \
    cp -r CosyVoice-main/cosyvoice ../ && \
    cd .. && \
    rm -rf temp_cosyvoice

# Create necessary directories
RUN mkdir -p outputs voice_cache/audio voice_cache/metadata logs pretrained_models

# Set permissions
RUN chmod +x setup_env.sh run_fast.py

# Expose port
EXPOSE 8012

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8012/health || exit 1

# Default command
CMD ["python", "run_fast.py"]
