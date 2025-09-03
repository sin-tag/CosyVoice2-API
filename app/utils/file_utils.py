"""
File handling utilities for CosyVoice2 API
"""

import os
import uuid
import tempfile
import shutil
import aiofiles
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

from app.core.config import settings


class FileManager:
    """File management utilities"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "cosyvoice2_api"
        self.temp_dir.mkdir(exist_ok=True)
    
    def generate_unique_filename(self, original_filename: str, prefix: str = "") -> str:
        """Generate a unique filename with timestamp and UUID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        # Extract file extension
        file_ext = Path(original_filename).suffix
        
        # Create unique filename
        if prefix:
            filename = f"{prefix}_{timestamp}_{unique_id}{file_ext}"
        else:
            filename = f"{timestamp}_{unique_id}{file_ext}"
        
        return filename
    
    async def save_uploaded_file(self, file_content: bytes, filename: str, 
                               destination_dir: str) -> str:
        """
        Save uploaded file to destination directory
        Returns: full file path
        """
        # Ensure destination directory exists
        dest_path = Path(destination_dir)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        unique_filename = self.generate_unique_filename(filename)
        file_path = dest_path / unique_filename
        
        # Save file asynchronously
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        return str(file_path)
    
    async def save_temp_file(self, file_content: bytes, filename: str) -> str:
        """
        Save file to temporary directory
        Returns: full file path
        """
        return await self.save_uploaded_file(file_content, filename, str(self.temp_dir))
    
    def get_voice_audio_path(self, voice_id: str, audio_format: str) -> str:
        """Get the file path for a voice audio file"""
        filename = f"{voice_id}.{audio_format}"
        return str(Path(settings.VOICE_CACHE_DIR) / "audio" / filename)
    
    def get_output_audio_path(self, filename: str) -> str:
        """Get the file path for an output audio file"""
        return str(Path(settings.OUTPUT_DIR) / filename)
    
    async def copy_file(self, source_path: str, destination_path: str) -> bool:
        """
        Copy file from source to destination
        Returns: success status
        """
        try:
            # Ensure destination directory exists
            dest_dir = Path(destination_path).parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, destination_path)
            return True
            
        except Exception as e:
            print(f"Error copying file from {source_path} to {destination_path}: {e}")
            return False
    
    async def move_file(self, source_path: str, destination_path: str) -> bool:
        """
        Move file from source to destination
        Returns: success status
        """
        try:
            # Ensure destination directory exists
            dest_dir = Path(destination_path).parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Move file
            shutil.move(source_path, destination_path)
            return True
            
        except Exception as e:
            print(f"Error moving file from {source_path} to {destination_path}: {e}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete file if it exists
        Returns: success status
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes"""
        try:
            return os.path.getsize(file_path)
        except Exception:
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        return os.path.exists(file_path)
    
    async def cleanup_temp_files(self, max_age_hours: int = 2):
        """Clean up temporary files older than max_age_hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            for file_path in self.temp_dir.iterdir():
                if file_path.is_file():
                    # Get file modification time
                    mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if mod_time < cutoff_time:
                        try:
                            file_path.unlink()
                            print(f"Cleaned up temp file: {file_path}")
                        except Exception as e:
                            print(f"Error cleaning up temp file {file_path}: {e}")
                            
        except Exception as e:
            print(f"Error during temp file cleanup: {e}")
    
    async def cleanup_output_files(self, max_age_hours: int = 24):
        """Clean up output files older than max_age_hours"""
        try:
            output_dir = Path(settings.OUTPUT_DIR)
            if not output_dir.exists():
                return
                
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            for file_path in output_dir.iterdir():
                if file_path.is_file():
                    # Get file modification time
                    mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if mod_time < cutoff_time:
                        try:
                            file_path.unlink()
                            print(f"Cleaned up output file: {file_path}")
                        except Exception as e:
                            print(f"Error cleaning up output file {file_path}: {e}")
                            
        except Exception as e:
            print(f"Error during output file cleanup: {e}")
    
    def get_relative_path(self, full_path: str, base_path: str) -> str:
        """Get relative path from base path"""
        try:
            return str(Path(full_path).relative_to(Path(base_path)))
        except ValueError:
            return full_path
    
    def ensure_directory_exists(self, directory_path: str):
        """Ensure directory exists, create if it doesn't"""
        Path(directory_path).mkdir(parents=True, exist_ok=True)


# Global file manager instance
file_manager = FileManager()
