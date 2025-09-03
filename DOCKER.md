# CosyVoice2 API - Docker Setup

This guide explains how to run CosyVoice2 API using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- NVIDIA Docker runtime (for GPU support)
- NVIDIA GPU with CUDA 12.1+ support

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/your-username/CosyVoice2-API.git
cd CosyVoice2-API
```

### 2. Prepare model directory
```bash
# Create model directory
mkdir -p pretrained_models/CosyVoice2-0.5B

# Download your CosyVoice2 model and place it in:
# pretrained_models/CosyVoice2-0.5B/
```

### 3. Build and run with Docker Compose
```bash
# Build and start the service
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

### 4. Access the API
- **API Documentation**: http://localhost:8013/docs
- **Health Check**: http://localhost:8013/health
- **API Base URL**: http://localhost:8013/api/v1

## Manual Docker Commands

### Build the image
```bash
docker build -t cosyvoice2-api .
```

### Run the container
```bash
docker run -d \
  --name cosyvoice2-api \
  --gpus all \
  -p 8013:8013 \
  -v ./pretrained_models:/app/pretrained_models \
  -v ./voice_cache:/app/voice_cache \
  -v ./outputs:/app/outputs \
  -v ./logs:/app/logs \
  -e CUDA_VISIBLE_DEVICES=0 \
  cosyvoice2-api
```

## Directory Structure

```
CosyVoice2-API/
├── pretrained_models/          # Place your CosyVoice2 models here
│   └── CosyVoice2-0.5B/       # Main model directory
├── voice_cache/               # Cached voice data (persistent)
├── outputs/                   # Generated audio files
├── logs/                      # Application logs
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose configuration
└── .dockerignore             # Files to exclude from Docker build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CUDA_VISIBLE_DEVICES` | `0` | GPU device to use |
| `PYTHONUNBUFFERED` | `1` | Python output buffering |

## Health Check

The container includes a health check endpoint at `/health` that verifies:
- API server is running
- Voice manager is initialized
- Models are loaded properly

## Troubleshooting

### GPU not detected
```bash
# Check if NVIDIA Docker runtime is installed
docker run --rm --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi
```

### Container fails to start
```bash
# Check logs
docker-compose logs cosyvoice-api

# Or for specific container
docker logs cosyvoice2-api
```

### Model loading issues
- Ensure your model files are in `pretrained_models/CosyVoice2-0.5B/`
- Check file permissions
- Verify model file integrity

### Memory issues
- Ensure sufficient GPU memory (8GB+ recommended)
- Reduce concurrent synthesis tasks if needed

## Performance Tips

1. **GPU Memory**: The container requires significant GPU memory. Monitor usage with `nvidia-smi`
2. **Storage**: Mount volumes for persistent data (voice cache, outputs)
3. **Networking**: Use host networking for better performance if needed:
   ```bash
   docker run --network host --gpus all cosyvoice2-api
   ```

## Stopping the Service

```bash
# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes
docker-compose down -v
```

## Building for Production

For production deployment, consider:
- Using specific image tags instead of `latest`
- Setting up proper logging and monitoring
- Configuring resource limits
- Using secrets management for sensitive data

Example production docker-compose.yml:
```yaml
version: '3.8'
services:
  cosyvoice-api:
    image: cosyvoice2-api:v1.0.0
    deploy:
      resources:
        limits:
          memory: 16G
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```
