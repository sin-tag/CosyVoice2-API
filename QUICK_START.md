# CosyVoice2 API - Quick Start Guide

Get up and running with CosyVoice2 API in minutes!

## 🚀 Super Quick Start (Conda - Recommended)

```bash
# 1. Clone repository
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# 2. Run automated setup
chmod +x scripts/setup_conda.sh
./scripts/setup_conda.sh

# 3. Activate environment
conda activate cosyvoice2-api

# 4. Download model
python scripts/download_model.py

# 5. Verify installation (optional)
python scripts/verify_installation.py

# 6. Start server
python main.py
```

🎉 **Done!** API is now running at http://localhost:8000

## 📋 Step-by-Step Instructions

### Prerequisites
- **Conda/Miniconda** installed ([Download here](https://docs.conda.io/en/latest/miniconda.html))
- **NVIDIA GPU** with CUDA support (recommended)
- **8GB+ RAM** and **10GB+ disk space**

### Method 1: Automated Setup (Easiest)

```bash
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API
./scripts/setup_conda.sh
conda activate cosyvoice2-api
python scripts/download_model.py
python main.py
```

### Method 2: Manual Setup

```bash
# 1. Clone and enter directory
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# 2. Create conda environment
conda create -n cosyvoice2-api python=3.9 -y
conda activate cosyvoice2-api

# 3. Install PyTorch with CUDA
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y

# 4. Install audio libraries
conda install -c conda-forge librosa soundfile -y

# 5. Install other dependencies
pip install -r requirements-conda.txt

# 6. Create directories
mkdir -p models voice_cache outputs logs

# 7. Setup configuration
cp .env.example .env

# 8. Download model
python scripts/download_model.py

# 9. Start server
python main.py
```

### Method 3: Using Environment File

```bash
# Clone repository
git clone https://github.com/sin-tag/CosyVoice2-API.git
cd CosyVoice2-API

# Create environment from file
conda env create -f environment.yml
conda activate cosyvoice2-api

# Download model and start
python scripts/download_model.py
python main.py
```

## 🧪 Test Your Installation

### 1. Check API Status
```bash
curl http://localhost:8000/health
```

### 2. List Pre-trained Voices
```bash
curl http://localhost:8000/api/v1/voices/pretrained/list
```

### 3. Add a Custom Voice
```bash
curl -X POST "http://localhost:8000/api/v1/voices/" \
  -F "voice_id=test_voice" \
  -F "name=Test Voice" \
  -F "voice_type=zero_shot" \
  -F "prompt_text=Hello world" \
  -F "audio_file=@your_voice_sample.wav"
```

### 4. Synthesize Speech
```bash
curl -X POST "http://localhost:8000/api/v1/synthesize/sft" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, this is a test!", "voice_id": "pretrained_voice_id"}'
```

## 🌐 Access Points

- **API Server**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🔧 Common Issues & Solutions

### Issue: "conda: command not found"
**Solution**: Install Miniconda from https://docs.conda.io/en/latest/miniconda.html

### Issue: "CUDA not available"
**Solution**: 
```bash
# Check NVIDIA driver
nvidia-smi

# Reinstall PyTorch with CUDA
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia --force-reinstall
```

### Issue: "ffmpeg not found"
**Solution**:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

### Issue: Model download fails
**Solution**:
```bash
# Try manual download with different model
python scripts/download_model.py --model-id iic/CosyVoice-300M

# Or check internet connection and disk space
```

### Issue: Import errors
**Solution**:
```bash
# Make sure you're in the right environment
conda activate cosyvoice2-api

# Reinstall dependencies
pip install -r requirements-conda.txt --force-reinstall
```

## 📚 Next Steps

1. **Read the API Documentation**: Visit http://localhost:8000/docs
2. **Try the Examples**: Check [API_EXAMPLES.md](docs/API_EXAMPLES.md)
3. **Production Setup**: See [DEPLOYMENT.md](DEPLOYMENT.md)
4. **Detailed Setup**: Read [CONDA_SETUP.md](CONDA_SETUP.md)

## 🆘 Need Help?

- **Detailed Setup**: [CONDA_SETUP.md](CONDA_SETUP.md)
- **API Examples**: [docs/API_EXAMPLES.md](docs/API_EXAMPLES.md)
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Troubleshooting**: Check the guides above for common solutions

## 🎯 What's Next?

Once your API is running, you can:

1. **Add custom voices** for zero-shot cloning
2. **Synthesize speech** in multiple languages
3. **Use cross-lingual** voice cloning
4. **Control synthesis** with natural language instructions
5. **Integrate** with your applications via REST API

Happy voice cloning! 🎤✨
