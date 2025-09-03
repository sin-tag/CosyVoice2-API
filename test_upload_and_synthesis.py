#!/usr/bin/env python3
"""
Test script for uploading voice and testing synthesis
"""

import requests
import json
import time
import os
from pathlib import Path

def test_voice_upload_and_synthesis(base_url="http://localhost:8011"):
    """Test voice upload and synthesis"""
    
    print("🧪 Testing Voice Upload and Synthesis")
    print("=" * 50)
    
    # Check if there are any audio files in voice_cache/audio
    audio_dir = Path("voice_cache/audio")
    if not audio_dir.exists():
        print("❌ No voice_cache/audio directory found")
        return False
    
    audio_files = list(audio_dir.glob("*.wav"))
    if not audio_files:
        print("❌ No audio files found in voice_cache/audio")
        return False
    
    print(f"✓ Found {len(audio_files)} audio files")
    for audio_file in audio_files:
        print(f"  - {audio_file.name}")
    
    # Use the first audio file for testing
    test_audio_file = audio_files[0]
    print(f"\n📤 Testing upload with: {test_audio_file.name}")
    
    # Test voice upload with unique ID
    import uuid
    unique_id = f"test_voice_{uuid.uuid4().hex[:8]}"
    voice_data = {
        "voice_id": unique_id,
        "name": "Test Voice",
        "description": "Test voice for synthesis",
        "voice_type": "sft",
        "prompt_text": "This is a test voice sample for speech synthesis."
    }
    
    try:
        with open(test_audio_file, 'rb') as f:
            files = {'audio_file': (test_audio_file.name, f, 'audio/wav')}
            response = requests.post(f"{base_url}/api/v1/voices/", 
                                   data=voice_data, files=files)
        
        if response.status_code in [200, 201]:
            result = response.json()
            print("✓ Voice uploaded successfully")
            print(f"  Voice ID: {result.get('voice_id')}")
            print(f"  Name: {result.get('name')}")
            print(f"  Type: {result.get('voice_type')}")
        else:
            print(f"❌ Voice upload failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Voice upload error: {e}")
        return False
    
    # Wait a moment for processing
    print("\n⏳ Waiting for voice processing...")
    time.sleep(2)
    
    # Test voice listing
    print("\n📋 Testing voice listing...")
    try:
        response = requests.get(f"{base_url}/api/v1/voices/")
        if response.status_code == 200:
            voices_data = response.json()
            print(f"✓ Found {voices_data.get('total', 0)} voices")
            
            voices = voices_data.get('voices', [])
            test_voice = None
            for voice in voices:
                print(f"  - {voice['voice_id']}: {voice['name']} ({voice['voice_type']})")
                if voice['voice_id'] == unique_id:
                    test_voice = voice
            
            if not test_voice:
                print("❌ Test voice not found in voice list")
                return False
                
        else:
            print(f"❌ Voice listing failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Voice listing error: {e}")
        return False
    
    # Test synthesis
    print("\n🎵 Testing voice synthesis...")
    
    test_texts = [
        "Hello, this is a test of the voice synthesis system.",
        "Testing multilingual support with English text.",
        "The quick brown fox jumps over the lazy dog."
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n  Test {i}: {text[:50]}...")
        
        synthesis_data = {
            "text": text,
            "voice_id": unique_id,
            "format": "wav",
            "speed": 1.0,
            "stream": False
        }
        
        try:
            start_time = time.time()
            response = requests.post(f"{base_url}/api/v1/synthesize/sft", 
                                   json=synthesis_data)
            end_time = time.time()
            
            if response.status_code == 200:
                result = response.json()
                duration = end_time - start_time
                print(f"    ✓ Synthesis successful ({duration:.2f}s)")
                print(f"      Success: {result.get('success')}")
                print(f"      Message: {result.get('message')}")
                print(f"      Audio URL: {result.get('audio_url', 'N/A')}")
                print(f"      Duration: {result.get('duration', 'N/A')}s")
                print(f"      Synthesis Time: {result.get('synthesis_time', 'N/A')}s")
                
                # Check if audio file exists
                if result.get('file_path') and os.path.exists(result['file_path']):
                    file_size = os.path.getsize(result['file_path'])
                    print(f"      File Size: {file_size} bytes")
                else:
                    print("      ⚠️  Audio file not found on disk")
                
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                print(f"    ❌ Synthesis failed ({response.status_code})")
                print(f"      Error: {error_data}")
                
        except Exception as e:
            print(f"    ❌ Synthesis error: {e}")
        
        # Small delay between requests
        time.sleep(1)
    
    print("\n🎉 Testing completed!")
    return True

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test voice upload and synthesis")
    parser.add_argument("--url", default="http://localhost:8011", 
                       help="Base URL of the API")
    parser.add_argument("--port", type=int, help="Port number (overrides URL)")
    
    args = parser.parse_args()
    
    if args.port:
        base_url = f"http://localhost:{args.port}"
    else:
        base_url = args.url
    
    print(f"🎯 Testing API at: {base_url}")
    
    # Test upload and synthesis
    success = test_voice_upload_and_synthesis(base_url)
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
