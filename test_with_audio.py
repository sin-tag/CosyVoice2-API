#!/usr/bin/env python3
"""
Test cross-lingual with audio
"""

import requests
from pathlib import Path

def test_with_audio():
    base_url = "http://localhost:8013"
    
    # Find audio file
    audio_dir = Path("voice_cache/audio")
    audio_files = list(audio_dir.glob("*.wav"))
    if not audio_files:
        print("No audio files found")
        return
    
    test_audio_file = audio_files[0]
    print(f"Using audio file: {test_audio_file}")
    
    # Test with audio
    data = {
        "text": "Hello, this is a test of cross-lingual voice cloning.",
        "prompt_text": "This is a sample voice for testing.",
        "format": "wav",
        "speed": 1.0,
        "stream": False
    }
    
    try:
        with open(test_audio_file, 'rb') as f:
            files = {'prompt_audio': (test_audio_file.name, f, 'audio/wav')}
            
            response = requests.post(f"{base_url}/api/v1/cross-lingual/with-audio", 
                                   data=data, files=files)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_with_audio()
