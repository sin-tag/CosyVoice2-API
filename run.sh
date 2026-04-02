#!/bin/bash
# Run voice-fast-service locally (no Docker)

set -e
cd "$(dirname "$0")"

# Create storage dirs
mkdir -p storage/voices storage/history

# Activate venv
source .venv/bin/activate

# Start server
cd src
uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --workers 1 --reload
