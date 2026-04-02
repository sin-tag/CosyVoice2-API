# Deploy voice-fast-service (uvicorn, no Docker)

## Requirements

- Python 3.12+
- CUDA 12.4+ (for GPU inference)
- Git

## 1. Clone & checkout

```bash
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API
git checkout fast-voice
```

## 2. Create venv & install dependencies

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# Install base + PyTorch CUDA 12.4 + Qwen engine
pip install -e ".[cu124,qwen]" --extra-index-url https://download.pytorch.org/whl/cu124

# (Optional) MOSS engine
pip install -e ".[moss]"

# (Optional) Dev tools
pip install -e ".[dev]"
```

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# Server
HOST=0.0.0.0
PORT=8010

# IP whitelist (comma-separated, empty = allow all)
ALLOWED_IPS=192.168.1.100,192.168.1.101

# API key
API_KEY=your-secret-key

# Engine (disable what you don't need)
QWEN_ENABLED=true
QWEN_DEVICE=cuda:0
MOSS_ENABLED=false

# Concurrency
MAX_CONCURRENT_GENERATIONS=2
MAX_CONCURRENT_REQUESTS=50
```

## 4. Create storage dirs

```bash
mkdir -p storage/voices storage/history
```

## 5. Run

### Development (with auto-reload)

```bash
# Linux/macOS
./run.sh

# Windows
run.bat
```

### Production (systemd)

Create `/etc/systemd/system/voice-fast.service`:

```ini
[Unit]
Description=Voice Fast Service
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/voice-fast-service/src
Environment=PYTHONPATH=.
ExecStart=/opt/voice-fast-service/.venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8010 \
    --workers 1 \
    --limit-concurrency 100 \
    --timeout-keep-alive 30
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable voice-fast
sudo systemctl start voice-fast

# Check logs
journalctl -u voice-fast -f
```

### Production (Windows - nssm)

```powershell
# Install nssm: https://nssm.cc/download
nssm install voice-fast "E:\voice-fast-service\.venv\Scripts\python.exe"
nssm set voice-fast AppParameters "-m uvicorn app.main:app --host 0.0.0.0 --port 8010 --workers 1"
nssm set voice-fast AppDirectory "E:\voice-fast-service\src"
nssm set voice-fast AppEnvironmentExtra "PYTHONPATH=."
nssm start voice-fast
```

## 6. Verify

```bash
curl http://localhost:8010/health
```

## Notes

- **Workers = 1**: GPU models are loaded in-process, multiple workers would duplicate GPU memory. Concurrency is handled by async + semaphores.
- **`--limit-concurrency`**: uvicorn-level limit on simultaneous connections (on top of app-level `MAX_CONCURRENT_REQUESTS`).
- **IP whitelist**: Only IPs in `ALLOWED_IPS` can connect. Leave empty to allow all.
- **SQLite**: No external database needed. Data stored in `storage/voice_fast.db`.
