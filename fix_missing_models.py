#!/usr/bin/env python3
"""
Fix missing app/models directory and files
This script recreates the missing models directory if it doesn't exist
"""

import os
import sys

def create_models_directory():
    """Create the app/models directory and files if missing"""
    
    # Get current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(current_dir, 'app')
    models_dir = os.path.join(app_dir, 'models')
    
    print(f"🔍 Checking app/models directory...")
    print(f"Current directory: {current_dir}")
    print(f"App directory: {app_dir}")
    print(f"Models directory: {models_dir}")
    
    # Check if app directory exists
    if not os.path.exists(app_dir):
        print(f"❌ App directory doesn't exist: {app_dir}")
        return False
    
    print(f"✓ App directory exists")
    print(f"Contents of app/: {os.listdir(app_dir)}")
    
    # Check if models directory exists
    if not os.path.exists(models_dir):
        print(f"❌ Models directory missing, creating: {models_dir}")
        os.makedirs(models_dir, exist_ok=True)
        print(f"✓ Created models directory")
    else:
        print(f"✓ Models directory exists")
        print(f"Contents of app/models/: {os.listdir(models_dir)}")
        return True
    
    # Create __init__.py
    init_file = os.path.join(models_dir, '__init__.py')
    if not os.path.exists(init_file):
        print(f"Creating {init_file}")
        with open(init_file, 'w') as f:
            f.write('''# Data models
# Import all models to make them available when importing app.models
from .voice import (
    VoiceType, AudioFormat, VoiceCreate, VoiceUpdate, 
    VoiceInDB, VoiceResponse, VoiceListResponse, VoiceStats
)
from .synthesis import (
    SynthesisRequest, SFTSynthesisRequest, ZeroShotSynthesisRequest,
    CrossLingualSynthesisRequest, InstructSynthesisRequest, SynthesisResponse
)
''')
        print(f"✓ Created {init_file}")
    
    # Create voice.py
    voice_file = os.path.join(models_dir, 'voice.py')
    if not os.path.exists(voice_file):
        print(f"Creating {voice_file}")
        with open(voice_file, 'w') as f:
            f.write('''"""
Voice models for CosyVoice2 API
"""

from typing import Optional, List
from datetime import datetime
from enum import Enum

try:
    from pydantic import BaseModel, Field, field_validator
    PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseModel, Field, validator
    PYDANTIC_V2 = False


class VoiceType(str, Enum):
    """Voice type enumeration"""
    SFT = "sft"  # Supervised Fine-Tuning (pre-trained voices)
    ZERO_SHOT = "zero_shot"  # Zero-shot voice cloning
    CROSS_LINGUAL = "cross_lingual"  # Cross-lingual voice synthesis
    INSTRUCT = "instruct"  # Natural language control


class AudioFormat(str, Enum):
    """Audio format enumeration"""
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"


class VoiceBase(BaseModel):
    """Base voice model"""
    voice_id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Human-readable voice name")
    description: Optional[str] = Field(None, description="Voice description")
    voice_type: VoiceType = Field(..., description="Type of voice")
    language: Optional[str] = Field(None, description="Primary language of the voice")
    
    if PYDANTIC_V2:
        @field_validator('voice_id')
        @classmethod
        def validate_voice_id(cls, v):
            if not v or len(v.strip()) == 0:
                raise ValueError('voice_id cannot be empty')
            # Only allow alphanumeric, underscore, and hyphen
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError('voice_id can only contain alphanumeric characters, underscores, and hyphens')
            return v.strip()
    else:
        @validator('voice_id')
        def validate_voice_id(cls, v):
            if not v or len(v.strip()) == 0:
                raise ValueError('voice_id cannot be empty')
            # Only allow alphanumeric, underscore, and hyphen
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError('voice_id can only contain alphanumeric characters, underscores, and hyphens')
            return v.strip()


class VoiceCreate(VoiceBase):
    """Model for creating a new voice"""
    prompt_text: Optional[str] = Field(None, description="Text that matches the audio sample")
    audio_format: AudioFormat = Field(AudioFormat.WAV, description="Audio file format")
    
    if PYDANTIC_V2:
        @field_validator('prompt_text')
        @classmethod
        def validate_prompt_text(cls, v, info):
            values = info.data if info else {}
            voice_type = values.get('voice_type')
            if voice_type in [VoiceType.ZERO_SHOT, VoiceType.CROSS_LINGUAL] and not v:
                raise ValueError('prompt_text is required for zero-shot and cross-lingual voices')
            return v
    else:
        @validator('prompt_text')
        def validate_prompt_text(cls, v, values):
            voice_type = values.get('voice_type')
            if voice_type in [VoiceType.ZERO_SHOT, VoiceType.CROSS_LINGUAL] and not v:
                raise ValueError('prompt_text is required for zero-shot and cross-lingual voices')
            return v


class VoiceUpdate(BaseModel):
    """Model for updating voice information"""
    name: Optional[str] = Field(None, description="Human-readable voice name")
    description: Optional[str] = Field(None, description="Voice description")
    language: Optional[str] = Field(None, description="Primary language of the voice")


class VoiceInDB(VoiceBase):
    """Voice model as stored in database"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    audio_file_path: Optional[str] = Field(None, description="Path to audio file")
    prompt_text: Optional[str] = Field(None, description="Text that matches the audio sample")
    audio_format: AudioFormat = Field(AudioFormat.WAV, description="Audio file format")
    file_size: Optional[int] = Field(None, description="Audio file size in bytes")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    sample_rate: Optional[int] = Field(None, description="Audio sample rate")
    is_active: bool = Field(True, description="Whether the voice is active")


class VoiceResponse(VoiceBase):
    """Voice response model"""
    created_at: datetime
    updated_at: datetime
    audio_format: AudioFormat
    file_size: Optional[int] = None
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    is_active: bool = True


class VoiceListResponse(BaseModel):
    """Response model for voice list"""
    voices: List[VoiceResponse]
    total: int
    page: int = 1
    per_page: int = 10


class VoiceStats(BaseModel):
    """Voice statistics model"""
    total_voices: int = 0
    active_voices: int = 0
    voice_types: dict = Field(default_factory=dict)
    languages: dict = Field(default_factory=dict)
    total_duration: float = 0.0
    total_size: int = 0
''')
        print(f"✓ Created {voice_file}")
    
    # Create synthesis.py
    synthesis_file = os.path.join(models_dir, 'synthesis.py')
    if not os.path.exists(synthesis_file):
        print(f"Creating {synthesis_file}")
        with open(synthesis_file, 'w') as f:
            f.write('''"""
Synthesis request and response models for CosyVoice2 API
"""

from typing import Optional, List
try:
    from pydantic import BaseModel, Field, field_validator
    PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseModel, Field, validator
    PYDANTIC_V2 = False
from enum import Enum

from .voice import AudioFormat


class SynthesisMode(str, Enum):
    """Synthesis mode enumeration"""
    SFT = "sft"  # Supervised Fine-Tuning (pre-trained voices)
    ZERO_SHOT = "zero_shot"  # Zero-shot voice cloning
    CROSS_LINGUAL = "cross_lingual"  # Cross-lingual voice synthesis
    INSTRUCT = "instruct"  # Natural language control


class SynthesisRequest(BaseModel):
    """Base synthesis request model"""
    text: str = Field(..., description="Text to synthesize", max_length=1000)
    speed: float = Field(1.0, description="Synthesis speed", ge=0.5, le=2.0)
    format: AudioFormat = Field(AudioFormat.WAV, description="Output audio format")
    stream: bool = Field(False, description="Enable streaming synthesis")
    
    if PYDANTIC_V2:
        @field_validator('text')
        @classmethod
        def validate_text(cls, v):
            if not v or len(v.strip()) == 0:
                raise ValueError('text cannot be empty')
            return v.strip()
    else:
        @validator('text')
        def validate_text(cls, v):
            if not v or len(v.strip()) == 0:
                raise ValueError('text cannot be empty')
            return v.strip()


class SFTSynthesisRequest(SynthesisRequest):
    """Synthesis request for pre-trained voices"""
    voice_id: str = Field(..., description="Pre-trained voice ID")


class ZeroShotSynthesisRequest(SynthesisRequest):
    """Synthesis request for zero-shot voice cloning"""
    voice_id: Optional[str] = Field(None, description="Cached voice ID (if using cached voice)")
    prompt_text: Optional[str] = Field(None, description="Text that matches the prompt audio")
    # Note: prompt_audio will be handled as file upload in the endpoint
    
    if PYDANTIC_V2:
        @field_validator('prompt_text')
        @classmethod
        def validate_prompt_text(cls, v, info):
            values = info.data if info else {}
            voice_id = values.get('voice_id')
            if not voice_id and not v:
                raise ValueError('prompt_text is required when not using cached voice')
            return v
    else:
        @validator('prompt_text')
        def validate_prompt_text(cls, v, values):
            voice_id = values.get('voice_id')
            if not voice_id and not v:
                raise ValueError('prompt_text is required when not using cached voice')
            return v


class CrossLingualSynthesisRequest(ZeroShotSynthesisRequest):
    """Synthesis request for cross-lingual voice synthesis"""
    target_language: str = Field(..., description="Target language for synthesis")


class InstructSynthesisRequest(SynthesisRequest):
    """Synthesis request for natural language control"""
    voice_id: str = Field(..., description="Pre-trained voice ID")
    instruct_text: str = Field(..., description="Natural language instruction for synthesis control")
    
    if PYDANTIC_V2:
        @field_validator('instruct_text')
        @classmethod
        def validate_instruct_text(cls, v):
            if not v or len(v.strip()) == 0:
                raise ValueError('instruct_text cannot be empty')
            return v.strip()
    else:
        @validator('instruct_text')
        def validate_instruct_text(cls, v):
            if not v or len(v.strip()) == 0:
                raise ValueError('instruct_text cannot be empty')
            return v.strip()


class SynthesisResponse(BaseModel):
    """Synthesis response model"""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Synthesis status")
    audio_url: Optional[str] = Field(None, description="URL to download the generated audio")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    format: AudioFormat = Field(..., description="Audio format")
    created_at: str = Field(..., description="Task creation timestamp")
    completed_at: Optional[str] = Field(None, description="Task completion timestamp")
    error: Optional[str] = Field(None, description="Error message if synthesis failed")
''')
        print(f"✓ Created {synthesis_file}")
    
    print(f"\n✅ Models directory setup complete!")
    print(f"Contents of app/models/: {os.listdir(models_dir)}")
    
    return True

def main():
    """Main function"""
    print("🔧 Fixing missing app/models directory...")
    
    if create_models_directory():
        print("\n🎉 Success! The app/models directory has been created/fixed.")
        print("\nNow try running:")
        print("  uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1")
    else:
        print("\n❌ Failed to create models directory.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
