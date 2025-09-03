#!/usr/bin/env python3
"""
CosyVoice2 API Fast Startup Script
This script starts the server without environment checks for faster startup
"""

import os
import sys
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Fast startup without environment checks"""
    
    print("🚀 CosyVoice2 API - Fast Startup")
    print("================================")
    
    # Check if we're in the right directory
    if not os.path.exists('main.py'):
        logger.error("main.py not found. Please run from the project root directory.")
        sys.exit(1)
    
    # Start server directly
    print("🌐 Server will be available at: http://localhost:8013")
    print("📚 API Documentation: http://localhost:8013/docs")
    print("🔄 Starting server...")
    print("")
    
    try:
        # Use uvicorn directly
        cmd = [
            sys.executable, "-m", "uvicorn", 
            "main:app", 
            "--host", "0.0.0.0", 
            "--port", "8013", 
            "--workers", "1"
        ]
        
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
