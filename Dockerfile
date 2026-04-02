FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3-pip libsndfile1 ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install PyTorch with CUDA 12.4
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[moss,qwen]"

# Install streaming fork for Qwen3
RUN pip install --no-cache-dir git+https://github.com/dffdeeq/Qwen3-TTS-streaming.git || true

# Install MOSS-TTS
RUN pip install --no-cache-dir git+https://github.com/OpenMOSS/MOSS-TTS.git || true

# Copy application
COPY . .

# Storage directories
RUN mkdir -p /app/storage/voices /app/storage/history

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
