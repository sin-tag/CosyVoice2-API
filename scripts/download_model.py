#!/usr/bin/env python3
"""
Script to download CosyVoice2 model
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from modelscope import snapshot_download


def download_model(model_id: str = "iic/CosyVoice2-0.5B", target_dir: str = "models"):
    """Download CosyVoice2 model from ModelScope"""
    
    print(f"Downloading model {model_id}...")
    
    try:
        # Create target directory
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Download model
        model_dir = snapshot_download(
            model_id, 
            cache_dir=str(target_path),
            revision="master"
        )
        
        print(f"Model downloaded successfully to: {model_dir}")
        
        # Create symlink for easier access
        symlink_path = target_path / "CosyVoice2-0.5B"
        if symlink_path.exists():
            symlink_path.unlink()
        
        symlink_path.symlink_to(Path(model_dir).resolve())
        print(f"Created symlink: {symlink_path}")
        
        return model_dir
        
    except Exception as e:
        print(f"Error downloading model: {e}")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download CosyVoice2 model")
    parser.add_argument(
        "--model-id", 
        default="iic/CosyVoice2-0.5B",
        help="Model ID to download"
    )
    parser.add_argument(
        "--target-dir",
        default="models",
        help="Target directory for model"
    )
    
    args = parser.parse_args()
    
    result = download_model(args.model_id, args.target_dir)
    if result:
        print("Download completed successfully!")
        sys.exit(0)
    else:
        print("Download failed!")
        sys.exit(1)
