#!/usr/bin/env python3
"""
Test script for 跨语种复刻 API (Cross-lingual Voice Cloning API)
Tests both modes: with-audio and with-cache
"""

import requests
import json
import time
import os
from pathlib import Path

def test_cross_lingual_api(base_url="http://localhost:8011"):
    """Test cross-lingual voice cloning API"""
    
    print("🧪 Testing 跨语种复刻 API (Cross-lingual Voice Cloning)")
    print("=" * 60)
    
    # Test health endpoint
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            health_data = response.json()
            print("✓ Health endpoint working")
            print(f"  Status: {health_data.get('status')}")
            print(f"  Voice Manager Ready: {health_data.get('voice_manager_ready')}")
            print(f"  API Mode: {health_data.get('api_mode')}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False
    
    # Test root endpoint
    print("\n2. Testing root endpoint...")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            root_data = response.json()
            print("✓ Root endpoint working")
            print(f"  Message: {root_data.get('message')}")
            print(f"  Available endpoints:")
            for name, endpoint in root_data.get('endpoints', {}).items():
                print(f"    - {name}: {endpoint}")
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Root endpoint error: {e}")
    
    # Test voice listing
    print("\n3. Testing voice listing...")
    try:
        response = requests.get(f"{base_url}/api/v1/voices/")
        if response.status_code == 200:
            voices_data = response.json()
            print(f"✓ Found {voices_data.get('total', 0)} voices")
            
            voices = voices_data.get('voices', [])
            for voice in voices:
                print(f"  - {voice['voice_id']}: {voice['name']} ({voice['voice_type']})")
            
            return voices
        else:
            print(f"❌ Voice listing failed: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Voice listing error: {e}")
        return []

def test_cross_lingual_with_audio(base_url="http://localhost:8011"):
    """Test cross-lingual synthesis with audio file"""
    print("\n4. Testing 跨语种复刻 - 带音频文件 (Cross-lingual with audio)...")
    
    # Check if there are any audio files in voice_cache/audio
    audio_dir = Path("voice_cache/audio")
    if not audio_dir.exists():
        print("❌ No voice_cache/audio directory found")
        return False
    
    audio_files = list(audio_dir.glob("*.wav"))
    if not audio_files:
        print("❌ No audio files found in voice_cache/audio")
        return False
    
    test_audio_file = audio_files[0]
    print(f"📤 Using audio file: {test_audio_file.name}")
    
    # Test texts in different languages
    test_cases = [
        {
            "text": "Hello, this is a test of cross-lingual voice cloning.",
            "prompt_text": "This is a sample voice for testing.",
            "instruct_text": None,
            "description": "English synthesis"
        },
        {
            "text": "你好，这是跨语种语音克隆的测试。",
            "prompt_text": "This is a sample voice for testing.",
            "instruct_text": None,
            "description": "Chinese synthesis"
        },
        {
            "text": "Hello, this is an emotional test.",
            "prompt_text": "This is a sample voice for testing.",
            "instruct_text": "Please speak with a happy and energetic tone.",
            "description": "English with instruct"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  Test {i}: {test_case['description']}")
        print(f"    Text: {test_case['text'][:50]}...")
        
        # Prepare form data
        data = {
            "text": test_case["text"],
            "prompt_text": test_case["prompt_text"],
            "format": "wav",
            "speed": 1.0,
            "stream": False
        }
        
        if test_case["instruct_text"]:
            data["instruct_text"] = test_case["instruct_text"]
            print(f"    Instruct: {test_case['instruct_text'][:50]}...")
        
        try:
            with open(test_audio_file, 'rb') as f:
                files = {'prompt_audio': (test_audio_file.name, f, 'audio/wav')}
                
                start_time = time.time()
                response = requests.post(f"{base_url}/api/v1/cross-lingual/with-audio", 
                                       data=data, files=files)
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
        time.sleep(2)
    
    return True

def test_cross_lingual_with_cache(base_url="http://localhost:8011", voices=None):
    """Test cross-lingual synthesis with cached voice"""
    print("\n5. Testing 跨语种复刻 - 使用缓存语音 (Cross-lingual with cache)...")
    
    if not voices:
        print("❌ No cached voices available for testing")
        return False
    
    # Use the first available voice
    test_voice = voices[0]
    voice_id = test_voice['voice_id']
    print(f"📤 Using cached voice: {voice_id}")
    
    # Test texts in different languages
    test_cases = [
        {
            "text": "Hello, this is a test using cached voice.",
            "instruct_text": None,
            "description": "English synthesis"
        },
        {
            "text": "你好，这是使用缓存语音的测试。",
            "instruct_text": None,
            "description": "Chinese synthesis"
        },
        {
            "text": "Hello, this is an emotional test with cached voice.",
            "instruct_text": "Please speak with a calm and gentle tone.",
            "description": "English with instruct"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  Test {i}: {test_case['description']}")
        print(f"    Text: {test_case['text'][:50]}...")
        
        # Prepare request data
        request_data = {
            "text": test_case["text"],
            "voice_id": voice_id,
            "format": "wav",
            "speed": 1.0,
            "stream": False
        }
        
        if test_case["instruct_text"]:
            request_data["instruct_text"] = test_case["instruct_text"]
            print(f"    Instruct: {test_case['instruct_text'][:50]}...")
        
        try:
            start_time = time.time()
            response = requests.post(f"{base_url}/api/v1/cross-lingual/with-cache", 
                                   json=request_data)
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
        time.sleep(2)
    
    return True

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test 跨语种复刻 API")
    parser.add_argument("--url", default="http://localhost:8011", 
                       help="Base URL of the API")
    parser.add_argument("--port", type=int, help="Port number (overrides URL)")
    
    args = parser.parse_args()
    
    if args.port:
        base_url = f"http://localhost:{args.port}"
    else:
        base_url = args.url
    
    print(f"🎯 Testing API at: {base_url}")
    
    # Test basic endpoints and get voices
    voices = test_cross_lingual_api(base_url)
    
    # Test cross-lingual synthesis with audio
    test_cross_lingual_with_audio(base_url)
    
    # Test cross-lingual synthesis with cache
    if voices:
        test_cross_lingual_with_cache(base_url, voices)
    
    print("\n🎉 Testing completed!")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
