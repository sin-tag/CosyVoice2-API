# CosyVoice2 API Examples

This document provides practical examples of how to use the CosyVoice2 API.

## Authentication

Currently, the API does not require authentication. This may change in future versions.

## Base URL

```
http://localhost:8000
```

## Voice Management

### 1. Add a Voice to Cache

Add a new voice for zero-shot cloning:

```bash
curl -X POST "http://localhost:8000/api/v1/voices/" \
  -H "Content-Type: multipart/form-data" \
  -F "voice_id=my_custom_voice" \
  -F "name=My Custom Voice" \
  -F "description=A custom voice for testing" \
  -F "voice_type=zero_shot" \
  -F "language=en" \
  -F "prompt_text=Hello, this is a sample of my voice." \
  -F "audio_format=wav" \
  -F "audio_file=@/path/to/voice_sample.wav"
```

Python example:

```python
import requests

url = "http://localhost:8000/api/v1/voices/"

with open("voice_sample.wav", "rb") as audio_file:
    files = {"audio_file": audio_file}
    data = {
        "voice_id": "my_custom_voice",
        "name": "My Custom Voice",
        "description": "A custom voice for testing",
        "voice_type": "zero_shot",
        "language": "en",
        "prompt_text": "Hello, this is a sample of my voice.",
        "audio_format": "wav"
    }
    
    response = requests.post(url, files=files, data=data)
    print(response.json())
```

### 2. List All Voices

```bash
curl -X GET "http://localhost:8000/api/v1/voices/"
```

With filtering:

```bash
curl -X GET "http://localhost:8000/api/v1/voices/?voice_type=zero_shot&language=en&page=1&page_size=10"
```

### 3. Get a Specific Voice

```bash
curl -X GET "http://localhost:8000/api/v1/voices/my_custom_voice"
```

### 4. Update Voice Information

```bash
curl -X PUT "http://localhost:8000/api/v1/voices/my_custom_voice" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Voice Name",
    "description": "Updated description"
  }'
```

### 5. Delete a Voice

```bash
curl -X DELETE "http://localhost:8000/api/v1/voices/my_custom_voice"
```

### 6. Get Voice Statistics

```bash
curl -X GET "http://localhost:8000/api/v1/voices/stats/summary"
```

### 7. List Pre-trained Voices

```bash
curl -X GET "http://localhost:8000/api/v1/voices/pretrained/list"
```

## Voice Synthesis

The API supports both **synchronous** and **asynchronous** voice synthesis:

- **Sync endpoints** (`/api/v1/synthesize/*`): Return results immediately (may take time)
- **Async endpoints** (`/api/v1/async/synthesize/*`): Return task ID immediately, check status later

### 1. SFT Synthesis (Pre-trained Voices)

#### Synchronous:

```bash
curl -X POST "http://localhost:8000/api/v1/synthesize/sft" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you today?",
    "voice_id": "pretrained_voice_001",
    "speed": 1.0,
    "format": "wav",
    "stream": false
  }'
```

Python example:

```python
import requests

url = "http://localhost:8000/api/v1/synthesize/sft"
data = {
    "text": "Hello, how are you today?",
    "voice_id": "pretrained_voice_001",
    "speed": 1.0,
    "format": "wav",
    "stream": False
}

response = requests.post(url, json=data)
result = response.json()

if result["success"]:
    # Download the audio file
    audio_url = f"http://localhost:8000{result['audio_url']}"
    audio_response = requests.get(audio_url)
    
    with open("output.wav", "wb") as f:
        f.write(audio_response.content)
    
    print(f"Audio saved to output.wav (duration: {result['duration']}s)")
```

#### Asynchronous:

```bash
curl -X POST "http://localhost:8000/api/v1/async/synthesize/sft" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you today?",
    "voice_id": "pretrained_voice_001",
    "speed": 1.0,
    "format": "wav"
  }'
```

Response:
```json
{
  "task_id": "task_abc123def456",
  "status": "submitted",
  "message": "SFT synthesis task submitted successfully",
  "check_status_url": "/api/v1/async/tasks/task_abc123def456/status",
  "result_url": "/api/v1/async/tasks/task_abc123def456/result"
}
```

Check status:
```bash
curl -X GET "http://localhost:8000/api/v1/async/tasks/task_abc123def456/status"
```

Get result when completed:
```bash
curl -X GET "http://localhost:8000/api/v1/async/tasks/task_abc123def456/result"
```

### 2. Zero-shot Synthesis (with Cached Voice)

```bash
curl -X POST "http://localhost:8000/api/v1/synthesize/zero-shot" \
  -H "Content-Type: multipart/form-data" \
  -F "text=Hello, this is a test of voice cloning." \
  -F "voice_id=my_custom_voice" \
  -F "speed=1.0" \
  -F "format=wav" \
  -F "stream=false"
```

### 3. Zero-shot Synthesis (with Prompt Audio)

```bash
curl -X POST "http://localhost:8000/api/v1/synthesize/zero-shot" \
  -H "Content-Type: multipart/form-data" \
  -F "text=Hello, this is a test of voice cloning." \
  -F "prompt_text=This is the original text from the audio sample." \
  -F "speed=1.0" \
  -F "format=wav" \
  -F "stream=false" \
  -F "prompt_audio=@/path/to/voice_sample.wav"
```

### 4. Cross-lingual Synthesis

```bash
curl -X POST "http://localhost:8000/api/v1/synthesize/cross-lingual" \
  -H "Content-Type: multipart/form-data" \
  -F "text=你好，这是跨语言语音合成测试。" \
  -F "voice_id=my_custom_voice" \
  -F "speed=1.0" \
  -F "format=wav" \
  -F "stream=false"
```

### 5. Instruct Synthesis (Natural Language Control)

```bash
curl -X POST "http://localhost:8000/api/v1/synthesize/instruct" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you today?",
    "voice_id": "pretrained_voice_001",
    "instruct_text": "Please speak in a happy and energetic tone",
    "speed": 1.0,
    "format": "wav",
    "stream": false
  }'
```

## Complete Python Example

Here's a complete example that demonstrates the full workflow:

```python
import requests
import time

BASE_URL = "http://localhost:8000"

def add_voice():
    """Add a custom voice to the cache"""
    url = f"{BASE_URL}/api/v1/voices/"
    
    with open("my_voice_sample.wav", "rb") as audio_file:
        files = {"audio_file": audio_file}
        data = {
            "voice_id": "my_voice_001",
            "name": "My Voice",
            "description": "My personal voice for cloning",
            "voice_type": "zero_shot",
            "language": "en",
            "prompt_text": "Hello, this is my voice sample.",
            "audio_format": "wav"
        }
        
        response = requests.post(url, files=files, data=data)
        if response.status_code == 201:
            print("Voice added successfully!")
            return True
        else:
            print(f"Failed to add voice: {response.text}")
            return False

def synthesize_speech(text, voice_id):
    """Synthesize speech using the cached voice"""
    url = f"{BASE_URL}/api/v1/synthesize/zero-shot"
    
    data = {
        "text": text,
        "voice_id": voice_id,
        "speed": 1.0,
        "format": "wav",
        "stream": False
    }
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            # Download the audio
            audio_url = f"{BASE_URL}{result['audio_url']}"
            audio_response = requests.get(audio_url)
            
            filename = f"synthesized_{int(time.time())}.wav"
            with open(filename, "wb") as f:
                f.write(audio_response.content)
            
            print(f"Speech synthesized successfully: {filename}")
            print(f"Duration: {result['duration']}s")
            return filename
        else:
            print(f"Synthesis failed: {result['message']}")
    else:
        print(f"Request failed: {response.text}")
    
    return None

def main():
    # Step 1: Add a voice (make sure you have my_voice_sample.wav)
    if add_voice():
        # Step 2: Synthesize speech
        text = "Hello! This is a test of voice cloning using CosyVoice2 API."
        synthesize_speech(text, "my_voice_001")

if __name__ == "__main__":
    main()
```

## Error Handling

The API returns structured error responses:

```json
{
  "error": "voice_not_found",
  "message": "Voice with ID 'non_existent' not found",
  "details": {
    "path": "/api/v1/voices/non_existent"
  }
}
```

Common error codes:
- `400`: Bad Request (invalid input)
- `404`: Not Found (voice or resource not found)
- `409`: Conflict (voice already exists)
- `422`: Unprocessable Entity (validation error)
- `500`: Internal Server Error
- `503`: Service Unavailable (model not ready)

## Rate Limiting

Currently, there are no rate limits, but this may be added in future versions for production deployments.
