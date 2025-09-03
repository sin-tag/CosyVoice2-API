# CosyVoice2 API - Async Voice Synthesis Guide

This guide explains how to use the asynchronous voice synthesis features for non-blocking voice generation.

## Why Use Async API?

- **Non-blocking**: API calls return immediately with a task ID
- **Better UX**: No waiting for voice generation to complete
- **Scalable**: Handle multiple synthesis requests concurrently
- **Progress tracking**: Monitor synthesis progress in real-time
- **Cancellation**: Cancel pending tasks if needed

## How It Works

1. **Submit Task**: Send synthesis request → Get `task_id` immediately
2. **Check Status**: Poll task status using `task_id`
3. **Get Result**: Download generated audio when task completes

## API Endpoints

### Submit Synthesis Tasks

- `POST /api/v1/async/synthesize/sft` - Pre-trained voice synthesis
- `POST /api/v1/async/synthesize/zero-shot` - Zero-shot voice cloning
- `POST /api/v1/async/synthesize/cross-lingual` - Cross-lingual synthesis
- `POST /api/v1/async/synthesize/instruct` - Natural language control

### Task Management

- `GET /api/v1/async/tasks/{task_id}/status` - Check task status
- `GET /api/v1/async/tasks/{task_id}/result` - Get completed result
- `DELETE /api/v1/async/tasks/{task_id}` - Cancel pending task
- `GET /api/v1/async/tasks` - List recent tasks

## Usage Examples

### 1. Basic Async Synthesis

```python
import requests
import time

# Submit synthesis task
response = requests.post("http://localhost:8000/api/v1/async/synthesize/sft", json={
    "text": "Hello, this is async voice synthesis!",
    "voice_id": "pretrained_voice_001",
    "speed": 1.0,
    "format": "wav"
})

task_data = response.json()
task_id = task_data["task_id"]
print(f"Task submitted: {task_id}")

# Poll for completion
while True:
    status_response = requests.get(f"http://localhost:8000/api/v1/async/tasks/{task_id}/status")
    status = status_response.json()
    
    print(f"Status: {status['status']} - Progress: {status['progress']*100:.1f}%")
    
    if status["status"] == "completed":
        # Get the result
        result_response = requests.get(f"http://localhost:8000/api/v1/async/tasks/{task_id}/result")
        result = result_response.json()
        
        # Download audio
        audio_url = f"http://localhost:8000{result['audio_url']}"
        audio_response = requests.get(audio_url)
        
        with open("async_output.wav", "wb") as f:
            f.write(audio_response.content)
        
        print("Audio saved to async_output.wav")
        break
    elif status["status"] == "failed":
        print(f"Task failed: {status.get('error', 'Unknown error')}")
        break
    
    time.sleep(2)  # Wait 2 seconds before checking again
```

### 2. Zero-shot Async Synthesis

```python
import requests

# Submit zero-shot synthesis with voice file
with open("my_voice_sample.wav", "rb") as audio_file:
    files = {"prompt_audio": audio_file}
    data = {
        "text": "This is zero-shot voice cloning in async mode!",
        "prompt_text": "Hello, this is my voice sample.",
        "speed": 1.0,
        "format": "wav"
    }
    
    response = requests.post(
        "http://localhost:8000/api/v1/async/synthesize/zero-shot",
        files=files,
        data=data
    )

task_data = response.json()
print(f"Zero-shot task submitted: {task_data['task_id']}")
```

### 3. Multiple Concurrent Tasks

```python
import requests
import asyncio
import aiohttp

async def submit_and_wait(session, text, voice_id):
    """Submit task and wait for completion"""
    
    # Submit task
    async with session.post("http://localhost:8000/api/v1/async/synthesize/sft", json={
        "text": text,
        "voice_id": voice_id,
        "format": "wav"
    }) as response:
        task_data = await response.json()
        task_id = task_data["task_id"]
    
    print(f"Submitted task {task_id} for: {text[:30]}...")
    
    # Wait for completion
    while True:
        async with session.get(f"http://localhost:8000/api/v1/async/tasks/{task_id}/status") as response:
            status = await response.json()
        
        if status["status"] == "completed":
            # Get result
            async with session.get(f"http://localhost:8000/api/v1/async/tasks/{task_id}/result") as response:
                result = await response.json()
            
            print(f"Task {task_id} completed: {result['audio_url']}")
            return result
        elif status["status"] == "failed":
            print(f"Task {task_id} failed: {status.get('error')}")
            return None
        
        await asyncio.sleep(1)

async def main():
    """Process multiple synthesis tasks concurrently"""
    texts = [
        "Hello, this is the first synthesis task.",
        "This is the second synthesis running in parallel.",
        "And here's the third one, all processing together!"
    ]
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            submit_and_wait(session, text, "pretrained_voice_001")
            for text in texts
        ]
        
        results = await asyncio.gather(*tasks)
        print(f"Completed {len([r for r in results if r])} tasks successfully")

# Run the async example
asyncio.run(main())
```

### 4. Task Management

```python
import requests

# List all recent tasks
response = requests.get("http://localhost:8000/api/v1/async/tasks")
tasks = response.json()

print(f"Found {tasks['total']} recent tasks:")
for task in tasks['tasks']:
    print(f"  {task['task_id']}: {task['status']} ({task['progress']*100:.1f}%)")

# Cancel a pending task
task_id = "task_abc123def456"
response = requests.delete(f"http://localhost:8000/api/v1/async/tasks/{task_id}")
if response.status_code == 200:
    print(f"Task {task_id} cancelled successfully")
```

## Task Status Values

- `pending` - Task is queued and waiting to start
- `processing` - Task is currently being processed
- `completed` - Task finished successfully, result available
- `failed` - Task failed with an error

## Best Practices

### 1. Polling Strategy

```python
import time

def wait_for_task(task_id, max_wait=300, poll_interval=2):
    """Wait for task completion with exponential backoff"""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(f"http://localhost:8000/api/v1/async/tasks/{task_id}/status")
        status = response.json()
        
        if status["status"] in ["completed", "failed"]:
            return status
        
        # Exponential backoff: start with 2s, max 10s
        poll_interval = min(poll_interval * 1.1, 10)
        time.sleep(poll_interval)
    
    raise TimeoutError(f"Task {task_id} did not complete within {max_wait} seconds")
```

### 2. Error Handling

```python
def safe_synthesis(text, voice_id):
    """Synthesis with proper error handling"""
    try:
        # Submit task
        response = requests.post("http://localhost:8000/api/v1/async/synthesize/sft", json={
            "text": text,
            "voice_id": voice_id,
            "format": "wav"
        })
        response.raise_for_status()
        
        task_id = response.json()["task_id"]
        
        # Wait for completion
        status = wait_for_task(task_id)
        
        if status["status"] == "completed":
            # Get result
            result_response = requests.get(f"http://localhost:8000/api/v1/async/tasks/{task_id}/result")
            result_response.raise_for_status()
            return result_response.json()
        else:
            raise Exception(f"Synthesis failed: {status.get('error')}")
            
    except requests.RequestException as e:
        print(f"HTTP error: {e}")
        return None
    except Exception as e:
        print(f"Synthesis error: {e}")
        return None
```

### 3. Batch Processing

```python
def process_batch(texts, voice_id, max_concurrent=5):
    """Process multiple texts with concurrency limit"""
    import concurrent.futures
    
    def process_single(text):
        return safe_synthesis(text, voice_id)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = [executor.submit(process_single, text) for text in texts]
        results = []
        
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Task failed: {e}")
                results.append(None)
    
    return results
```

## Configuration

You can configure the async synthesis behavior in your `.env` file:

```bash
# Maximum concurrent synthesis tasks
MAX_SYNTHESIS_WORKERS=4

# Task cleanup settings
TASK_CLEANUP_INTERVAL=3600  # 1 hour
MAX_TASK_AGE=7200          # 2 hours

# Task limits
MAX_TASKS_PER_USER=10      # Future feature
```

## Monitoring

Check the health endpoint to see if async synthesis is ready:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "voice_manager_ready": true,
  "async_synthesis_ready": true
}
```

## Comparison: Sync vs Async

| Feature | Sync API | Async API |
|---------|----------|-----------|
| Response time | Slow (waits for completion) | Fast (immediate task_id) |
| Blocking | Yes | No |
| Progress tracking | No | Yes |
| Cancellation | No | Yes |
| Concurrent requests | Limited | High |
| Use case | Simple, single requests | Production, multiple requests |

Choose **Sync API** for:
- Simple testing and development
- Single synthesis requests
- When you can wait for completion

Choose **Async API** for:
- Production applications
- Multiple concurrent requests
- Better user experience
- Progress tracking needs

This async system ensures your voice generation API is scalable and user-friendly! 🚀
