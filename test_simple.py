#!/usr/bin/env python3
"""
Simple test for cross-lingual API
"""

import requests
import json

def test_simple():
    base_url = "http://localhost:8012"
    
    # Test with cache
    print("Testing with cache...")
    request_data = {
        "text": "Hello test",
        "voice_id": "123",
        "format": "wav",
        "speed": 1.0,
        "stream": False
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/cross-lingual/with-cache", 
                               json=request_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_simple()
