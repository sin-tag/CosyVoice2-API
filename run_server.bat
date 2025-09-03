@echo off
REM CosyVoice2 API Server Setup and Run Script for Windows
REM This script automates the complete setup and running of the CosyVoice2 API server

setlocal enabledelayedexpansion

REM Configuration
set PYTHON_VERSION=3.10
set VENV_NAME=venv
set DEFAULT_PORT=8000
set DEFAULT_HOST=0.0.0.0
set DEFAULT_WORKERS=1

REM Parse command line arguments
set HOST=%DEFAULT_HOST%
set PORT=%DEFAULT_PORT%
set WORKERS=%DEFAULT_WORKERS%
set SKIP_SETUP=false

:parse_args
if "%~1"=="" goto end_parse
if "%~1"=="--host" (
    set HOST=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--port" (
    set PORT=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--workers" (
    set WORKERS=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--skip-setup" (
    set SKIP_SETUP=true
    shift
    goto parse_args
)
if "%~1"=="--help" (
    echo Usage: %0 [OPTIONS]
    echo Options:
    echo   --host HOST        Host to bind to ^(default: %DEFAULT_HOST%^)
    echo   --port PORT        Port to bind to ^(default: %DEFAULT_PORT%^)
    echo   --workers WORKERS  Number of workers ^(default: %DEFAULT_WORKERS%^)
    echo   --skip-setup       Skip environment setup and dependency installation
    echo   --help             Show this help message
    exit /b 0
)
echo [ERROR] Unknown option: %~1
exit /b 1

:end_parse

echo [INFO] 🚀 CosyVoice2 API Server Setup and Run Script
echo [INFO] ==============================================

if "%SKIP_SETUP%"=="true" (
    echo [INFO] Skipping setup as requested
    goto start_server
)

REM Check Python version
echo [INFO] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python %PYTHON_VERSION% or higher.
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo [INFO] Found Python version: %PYTHON_VER%

REM Setup virtual environment
echo [INFO] Setting up virtual environment...
if exist "%VENV_NAME%" (
    echo [WARNING] Virtual environment already exists. Removing old environment...
    rmdir /s /q "%VENV_NAME%"
)

python -m venv "%VENV_NAME%"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    exit /b 1
)
echo [SUCCESS] Virtual environment created successfully

REM Activate virtual environment
call "%VENV_NAME%\Scripts\activate.bat"
echo [SUCCESS] Virtual environment activated

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
echo [SUCCESS] Pip upgraded successfully

REM Install dependencies using comprehensive installer
echo [INFO] Installing dependencies using comprehensive installer...

REM Use the comprehensive Python installer
if exist "install_dependencies.py" (
    python install_dependencies.py
    if errorlevel 1 (
        echo [WARNING] Comprehensive installer had some issues, trying fallback installation...
        goto fallback_install
    ) else (
        echo [SUCCESS] Dependencies installation completed successfully
        goto setup_models
    )
) else (
    echo [WARNING] Comprehensive installer not found, using fallback installation...
    goto fallback_install
)

:fallback_install
echo [INFO] Installing dependencies ^(fallback method^)...

echo [INFO] Installing setuptools and wheel...
pip install setuptools wheel

echo [INFO] Installing PyTorch with CUDA 12.1 support...
pip install torch==2.2.2+cu121 torchaudio==2.2.2+cu121 --extra-index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo [WARNING] CUDA version failed, trying CPU version...
    pip install torch==2.2.2 torchaudio==2.2.2
)

echo [INFO] Installing NumPy ^(compatible version^)...
pip install "numpy<2"

echo [INFO] Installing core dependencies...
pip install fastapi uvicorn[standard] python-multipart pydantic pydantic-settings

echo [INFO] Installing audio processing libraries...
pip install librosa soundfile

echo [INFO] Installing ML/AI libraries...
pip install transformers modelscope

echo [INFO] Installing additional dependencies...
pip install gradio lightning omegaconf diffusers hydra-core
pip install gdown matplotlib pyarrow pyworld wetext conformer
pip install seaborn wandb tensorboard rich inflect
pip install eng_to_ipa unidecode cn2an num2words openai-whisper

echo [INFO] Installing CosyVoice specific dependencies...
pip install hyperpyyaml onnxruntime pypinyin jieba

echo [INFO] Installing text processing dependencies...
pip install pynini openfst-python || echo [WARNING] Some text processing dependencies failed to install

echo [INFO] Attempting to install WeTextProcessing...
pip install WeTextProcessing>=1.0.3 || echo [WARNING] WeTextProcessing installation failed, using wetext fallback instead

echo [SUCCESS] Fallback dependencies installation completed

:setup_models
REM Setup model directory
echo [INFO] Setting up model directory...
if exist "models\iic\CosyVoice2-0___5B" if not exist "models\CosyVoice2-0.5B" (
    echo [INFO] Creating model directory...
    xcopy "models\iic\CosyVoice2-0___5B" "models\CosyVoice2-0.5B" /E /I /Q
    echo [SUCCESS] Model directory setup completed
)

REM Create cosyvoice.yaml if it doesn't exist
if exist "models\CosyVoice2-0.5B\cosyvoice2.yaml" if not exist "models\CosyVoice2-0.5B\cosyvoice.yaml" (
    echo [INFO] Creating cosyvoice.yaml...
    copy "models\CosyVoice2-0.5B\cosyvoice2.yaml" "models\CosyVoice2-0.5B\cosyvoice.yaml" >nul
    echo [SUCCESS] Configuration file setup completed
)

REM Cleanup unnecessary files
echo [INFO] Cleaning up unnecessary files...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
if exist ".pytest_cache" rmdir /s /q ".pytest_cache" 2>nul
if exist ".coverage" del ".coverage" 2>nul
if exist "htmlcov" rmdir /s /q "htmlcov" 2>nul
echo [SUCCESS] Cleanup completed

echo [SUCCESS] Setup completed successfully!

:start_server
REM Start the server
echo [INFO] Starting CosyVoice2 API server...

REM Check if port is available (simplified check)
netstat -an | find ":%PORT% " >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Port %PORT% appears to be in use
    set /a PORT=%PORT%+1
    echo [WARNING] Trying port !PORT! instead
)

echo [INFO] Server configuration:
echo [INFO]   Host: %HOST%
echo [INFO]   Port: %PORT%
echo [INFO]   Workers: %WORKERS%
echo [INFO]   Access URL: http://localhost:%PORT%
echo [INFO]   API Documentation: http://localhost:%PORT%/docs

REM Activate virtual environment
call "%VENV_NAME%\Scripts\activate.bat"

echo [SUCCESS] Starting server...
uvicorn main:app --host %HOST% --port %PORT% --workers %WORKERS%

endlocal
