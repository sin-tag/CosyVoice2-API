# CosyVoice2 API Deployment Guide

This guide covers different deployment options for the CosyVoice2 API.

## Prerequisites

- Python 3.9+
- CUDA-compatible GPU (recommended for better performance)
- At least 8GB RAM
- 10GB+ disk space for models and cache

## Local Development

### Quick Start

```bash
# Clone and setup
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API
./scripts/setup.sh

# Download model
python scripts/download_model.py

# Start development server
python main.py
```

### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir -p models voice_cache outputs logs

# Copy configuration
cp .env.example .env
# Edit .env as needed

# Download model
python scripts/download_model.py

# Run server
python main.py
```

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Clone repository
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# Download model first
python scripts/download_model.py

# Start with Docker Compose
docker-compose up -d
```

### Using Docker directly

```bash
# Build image
docker build -t cosyvoice2-api .

# Run container
docker run -d \
  --name cosyvoice2-api \
  -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/voice_cache:/app/voice_cache \
  -v $(pwd)/outputs:/app/outputs \
  -e MODEL_DIR=/app/models/CosyVoice2-0.5B \
  cosyvoice2-api
```

## Production Deployment

### Using Nginx + Gunicorn

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Create Gunicorn configuration (`gunicorn.conf.py`):
```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 300
keepalive = 2
```

3. Start with Gunicorn:
```bash
gunicorn main:app -c gunicorn.conf.py
```

4. Configure Nginx:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_timeout 300s;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

### Using Systemd Service

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
Environment=PATH=/path/to/CosyVoice2-API/venv/bin
ExecStart=/path/to/CosyVoice2-API/venv/bin/gunicorn main:app -c gunicorn.conf.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable cosyvoice2-api
sudo systemctl start cosyvoice2-api
```

## Cloud Deployment

### AWS EC2

1. Launch EC2 instance (recommended: g4dn.xlarge or larger)
2. Install Docker and Docker Compose
3. Clone repository and follow Docker deployment steps
4. Configure security groups to allow port 8000
5. Use Application Load Balancer for production

### Google Cloud Platform

1. Create Compute Engine instance with GPU
2. Install Docker
3. Follow Docker deployment steps
4. Use Cloud Load Balancer for production

### Azure

1. Create Virtual Machine with GPU
2. Install Docker
3. Follow Docker deployment steps
4. Use Azure Load Balancer for production

## Environment Variables

Key environment variables for production:

```bash
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Model
MODEL_DIR=/app/models/CosyVoice2-0.5B

# Storage
VOICE_CACHE_DIR=/app/voice_cache
OUTPUT_DIR=/app/outputs

# Limits
MAX_FILE_SIZE=52428800  # 50MB
MAX_AUDIO_DURATION=30
MAX_TEXT_LENGTH=1000

# Cleanup
CLEANUP_INTERVAL=3600
TEMP_FILE_LIFETIME=7200
```

## Performance Optimization

### GPU Configuration

Ensure CUDA is properly configured:
```bash
# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"
```

### Memory Management

For production, consider:
- Increasing worker memory limits
- Setting up swap if needed
- Monitoring memory usage

### Caching

- Use Redis for distributed caching (future enhancement)
- Configure proper file system caching
- Set up CDN for audio file delivery

## Monitoring

### Health Checks

The API provides health check endpoints:
- `GET /health` - Basic health check
- `GET /` - API information

### Logging

Configure logging in production:
```python
# In your environment
LOGGING_LEVEL=INFO
LOG_FILE=/app/logs/cosyvoice2-api.log
```

### Metrics

Consider adding:
- Prometheus metrics
- Application performance monitoring
- Error tracking (Sentry)

## Security

### Basic Security

1. Use HTTPS in production
2. Configure CORS properly
3. Add rate limiting
4. Validate all inputs
5. Use proper authentication (future enhancement)

### Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

## Backup and Recovery

### Data Backup

Important directories to backup:
- `voice_cache/` - User voice data
- `models/` - Model files (can be re-downloaded)
- Configuration files

### Recovery Procedures

1. Restore voice cache data
2. Re-download models if needed
3. Restore configuration
4. Restart services

## Troubleshooting

### Common Issues

1. **Model not loading**: Check MODEL_DIR path and permissions
2. **Out of memory**: Reduce batch size or add more RAM
3. **Audio processing errors**: Check ffmpeg installation
4. **Permission errors**: Check file permissions and user/group settings

### Debug Mode

Enable debug mode for troubleshooting:
```bash
DEBUG=true python main.py
```

### Logs

Check logs for errors:
```bash
# Application logs
tail -f logs/cosyvoice2-api.log

# System logs
journalctl -u cosyvoice2-api -f
```
