#!/usr/bin/env python3
"""
Test Vietnamese text synthesis
"""

import requests
import json

def test_vietnamese():
    base_url = "http://localhost:8012"
    
    # Test Vietnamese text with cache
    print("Testing Vietnamese text with cache...")
    request_data = {
        "text": "Xin chào, đây là bài kiểm tra tổng hợp giọng nói tiếng Việt.",
        "voice_id": "123",
        "format": "wav",
        "speed": 1.0,
        "stream": False
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/cross-lingual/with-cache", 
                               json=request_data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Success: {result.get('success')}")
        print(f"Message: {result.get('message')}")
        print(f"Audio URL: {result.get('audio_url')}")
        print(f"Duration: {result.get('duration')}s")
        print(f"Synthesis Time: {result.get('synthesis_time')}s")
        
    except Exception as e:
        print(f"Error: {e}")

    # Test English text
    print("\nTesting English text with cache...")
    request_data = {
        "text": "Hello, this is a test of English text synthesis with proper pronunciation.",
        "voice_id": "123",
        "format": "wav",
        "speed": 1.0,
        "stream": False
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/cross-lingual/with-cache", 
                               json=request_data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Success: {result.get('success')}")
        print(f"Message: {result.get('message')}")
        print(f"Audio URL: {result.get('audio_url')}")
        print(f"Duration: {result.get('duration')}s")
        print(f"Synthesis Time: {result.get('synthesis_time')}s")
        
    except Exception as e:
        print(f"Error: {e}")

    # Test Chinese text
    print("\nTesting Chinese text with cache...")
    request_data = {
        "text": "你好，这是中文语音合成的测试，应该能够正确发音。",
        "voice_id": "123",
        "format": "wav",
        "speed": 1.0,
        "stream": False
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/cross-lingual/with-cache", 
                               json=request_data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Success: {result.get('success')}")
        print(f"Message: {result.get('message')}")
        print(f"Audio URL: {result.get('audio_url')}")
        print(f"Duration: {result.get('duration')}s")
        print(f"Synthesis Time: {result.get('synthesis_time')}s")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_vietnamese()
