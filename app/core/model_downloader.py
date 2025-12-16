"""
Auto-download models from HuggingFace for CosyVoice API
"""

import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def download_cosyvoice3_model(
    model_dir: str,
    repo_id: str = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
    force_download: bool = False
) -> bool:
    """
    Download CosyVoice3 model from HuggingFace

    Args:
        model_dir: Local directory to save the model
        repo_id: HuggingFace repository ID
        force_download: Force re-download even if model exists

    Returns:
        True if download successful or model already exists
    """
    try:
        # Check if model already exists
        model_path = Path(model_dir)
        config_file = model_path / "cosyvoice3.yaml"

        if config_file.exists() and not force_download:
            logger.info(f"CosyVoice3 model already exists at {model_dir}")
            return True

        logger.info(f"Downloading CosyVoice3 model from {repo_id}...")

        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            logger.error("huggingface_hub not installed. Installing...")
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
            from huggingface_hub import snapshot_download

        # Create parent directory
        model_path.parent.mkdir(parents=True, exist_ok=True)

        # Download the model
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(model_path),
            local_dir_use_symlinks=False,
            resume_download=True
        )

        logger.info(f"CosyVoice3 model downloaded successfully to {model_dir}")
        return True

    except Exception as e:
        logger.error(f"Failed to download CosyVoice3 model: {e}")
        return False


def download_ttsfrd_resources(
    target_dir: str = "pretrained_models/CosyVoice-ttsfrd",
    force_download: bool = False
) -> bool:
    """
    Download CosyVoice text normalization resources

    Args:
        target_dir: Local directory to save resources
        force_download: Force re-download even if resources exist

    Returns:
        True if download successful or resources already exist
    """
    try:
        target_path = Path(target_dir)
        resource_file = target_path / "resource.zip"

        if (target_path / "resource").exists() and not force_download:
            logger.info(f"Text normalization resources already exist at {target_dir}")
            return True

        logger.info("Downloading text normalization resources...")

        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            import subprocess
            import sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
            from huggingface_hub import snapshot_download

        # Create directory
        target_path.mkdir(parents=True, exist_ok=True)

        # Download resources
        snapshot_download(
            repo_id="FunAudioLLM/CosyVoice-ttsfrd",
            local_dir=str(target_path),
            local_dir_use_symlinks=False,
            resume_download=True
        )

        # Extract resource.zip if it exists
        if resource_file.exists():
            import zipfile
            logger.info("Extracting resource.zip...")
            with zipfile.ZipFile(resource_file, 'r') as zip_ref:
                zip_ref.extractall(target_path)
            logger.info("Resources extracted successfully")

        return True

    except Exception as e:
        logger.error(f"Failed to download text normalization resources: {e}")
        return False


def ensure_cosyvoice3_model(model_dir: str, repo_id: str, auto_download: bool = True) -> bool:
    """
    Ensure CosyVoice3 model is available, downloading if necessary

    Args:
        model_dir: Local directory for the model
        repo_id: HuggingFace repository ID
        auto_download: Whether to auto-download if not found

    Returns:
        True if model is available
    """
    model_path = Path(model_dir)

    # Check for CosyVoice3 config file
    if (model_path / "cosyvoice3.yaml").exists():
        return True

    # Also check for alternative config names
    if (model_path / "cosyvoice.yaml").exists():
        return True

    if not auto_download:
        logger.warning(f"CosyVoice3 model not found at {model_dir} and auto-download is disabled")
        return False

    # Try to download
    return download_cosyvoice3_model(model_dir, repo_id)
