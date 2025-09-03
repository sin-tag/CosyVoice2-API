#!/usr/bin/env python3
"""
Test script for voice synthesis functionality
Tests both pretrained and cached voices
"""

import requests
import json
import time

def test_api_endpoint(base_url="http://localhost:8000"):
    """Test the API endpoints"""
    
    print("🧪 Testing CosyVoice2 API Endpoints")
    print("=" * 50)
    
    # Test health endpoint
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✓ Health endpoint working")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False
    
    # Test voices list endpoint
    print("\n2. Testing voices list endpoint...")
    try:
        response = requests.get(f"{base_url}/api/v1/voices/")
        if response.status_code == 200:
            voices_data = response.json()
            print(f"✓ Found {voices_data.get('total', 0)} voices")
            
            # Print available voices
            for voice in voices_data.get('voices', []):
                print(f"  - {voice['voice_id']}: {voice['name']} ({voice['voice_type']}, {voice.get('language', 'multilingual')})")
            
            return voices_data.get('voices', [])
        else:
            print(f"❌ Voices endpoint failed: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Voices endpoint error: {e}")
        return []

def test_synthesis(base_url="http://localhost:8000", voices=None):
    """Test synthesis with available voices"""
    
    if not voices:
        print("⚠️  No voices available for testing")
        return False
    
    print("\n3. Testing voice synthesis...")
    
    # Test text
    test_texts = [
        "Hello, this is a test of the CosyVoice2 API.",
        "你好，这是CosyVoice2 API的测试。",
        "Bonjour, ceci est un test de l'API CosyVoice2."
    ]
    
    for i, voice in enumerate(voices[:2]):  # Test first 2 voices
        voice_id = voice['voice_id']
        voice_type = voice['voice_type']
        
        print(f"\n  Testing voice: {voice_id} ({voice_type})")
        
        for j, text in enumerate(test_texts):
            print(f"    Text {j+1}: {text[:50]}...")
            
            # Prepare synthesis request
            synthesis_data = {
                "text": text,
                "voice_id": voice_id,
                "format": "wav",
                "speed": 1.0,
                "stream": False
            }
            
            # Choose endpoint based on voice type
            if voice_type == "sft":
                endpoint = f"{base_url}/api/v1/synthesize/sft"
            elif voice_type == "zero_shot":
                endpoint = f"{base_url}/api/v1/synthesize/zero-shot"
                # Add required fields for zero-shot
                synthesis_data.update({
                    "prompt_text": "This is a sample prompt.",
                    "prompt_audio_url": "sample_audio.wav"  # This would need to be a real file
                })
            else:
                print(f"    ⚠️  Unsupported voice type: {voice_type}")
                continue
            
            try:
                start_time = time.time()
                response = requests.post(endpoint, json=synthesis_data)
                end_time = time.time()
                
                if response.status_code == 200:
                    result = response.json()
                    duration = end_time - start_time
                    print(f"    ✓ Synthesis successful ({duration:.2f}s)")
                    print(f"      Audio URL: {result.get('audio_url', 'N/A')}")
                    print(f"      Duration: {result.get('duration', 'N/A')}s")
                else:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                    print(f"    ❌ Synthesis failed ({response.status_code}): {error_data}")
                    
                    # If it's the voice not found error, this is what we're testing
                    if "not found" in str(error_data).lower():
                        print(f"    🔍 This is the error we're fixing!")
                        
            except Exception as e:
                print(f"    ❌ Synthesis error: {e}")
            
            # Small delay between requests
            time.sleep(0.5)
    
    return True

def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test CosyVoice2 API")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL of the API (default: http://localhost:8000)")
    parser.add_argument("--port", type=int, help="Port number (overrides URL)")
    
    args = parser.parse_args()
    
    if args.port:
        base_url = f"http://localhost:{args.port}"
    else:
        base_url = args.url
    
    print(f"🎯 Testing API at: {base_url}")
    
    # Test endpoints and get voices
    voices = test_api_endpoint(base_url)
    
    if voices:
        # Test synthesis
        test_synthesis(base_url, voices)
    else:
        print("❌ No voices found, cannot test synthesis")
        return False
    
    print("\n🎉 Testing completed!")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
