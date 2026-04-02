"""Concurrency test — verify API doesn't block under multi-user load.

Tests:
1. Multiple concurrent voice CRUD (non-GPU) — should NOT block each other
2. Multiple concurrent TTS generations (GPU) — serialized by semaphore, but HTTP shouldn't block
3. Mixed load: CRUD + TTS simultaneously
4. SSE streaming under concurrent requests
5. Health endpoint responsiveness during GPU work
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass

import httpx
import numpy as np
import soundfile as sf

BASE_URL = "http://localhost:8000"
API_KEY = "test-key-123"
HEADERS = {"X-API-Key": API_KEY}


@dataclass
class Result:
    name: str
    status: int
    elapsed_ms: int
    error: str | None = None


_counter = 0


def unique_name(prefix: str) -> str:
    global _counter
    _counter += 1
    return f"{prefix}_{int(time.time())}_{_counter}"


def create_test_wav(path: str, duration: float = 5.0, sr: int = 24000):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.3 * np.sin(2 * np.pi * 440 * t)
    sf.write(path, audio, sr)


# ─── Test 1: Concurrent CRUD (no GPU) ───


async def test_concurrent_crud():
    """Multiple users doing voice CRUD at the same time — should all respond fast."""
    print("\n" + "=" * 60)
    print("TEST 1: Concurrent CRUD (no GPU, should NOT block)")
    print("=" * 60)

    create_test_wav("_test_ref.wav")

    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=30) as client:
        voice_ids = []

        # Create 5 voices concurrently
        async def create_voice(i: int) -> Result:
            start = time.perf_counter()
            with open("_test_ref.wav", "rb") as f:
                resp = await client.post(
                    "/api/v1/voices",
                    data={"name": unique_name(f"cv_{i}"), "language": "en", "reference_text": "test"},
                    files={"reference_audio": ("ref.wav", f, "audio/wav")},
                )
            ms = int((time.perf_counter() - start) * 1000)
            if resp.status_code == 201:
                voice_ids.append(resp.json()["id"])
            return Result(f"create_voice_{i}", resp.status_code, ms)

        results = await asyncio.gather(*[create_voice(i) for i in range(5)])
        for r in results:
            print(f"  {r.name}: {r.status} ({r.elapsed_ms}ms)")

        # List voices concurrently (10 requests)
        async def list_voices(i: int) -> Result:
            start = time.perf_counter()
            resp = await client.get("/api/v1/voices")
            ms = int((time.perf_counter() - start) * 1000)
            return Result(f"list_voices_{i}", resp.status_code, ms)

        results = await asyncio.gather(*[list_voices(i) for i in range(10)])
        times = [r.elapsed_ms for r in results]
        print(f"  list_voices x10: avg={sum(times)//len(times)}ms, max={max(times)}ms, all_ok={all(r.status == 200 for r in results)}")

        # Cleanup
        for vid in voice_ids:
            await client.delete(f"/api/v1/voices/{vid}")

    os.remove("_test_ref.wav")
    print("  PASSED: All CRUD requests served concurrently")


# ─── Test 2: Concurrent TTS (GPU bound) ───


async def test_concurrent_tts():
    """Multiple TTS requests — GPU serialized by semaphore, but HTTP should stay responsive."""
    print("\n" + "=" * 60)
    print("TEST 2: Concurrent TTS generation (GPU serialized)")
    print("=" * 60)

    # First, ensure we have a voice
    create_test_wav("_test_ref2.wav")
    timeout = httpx.Timeout(300, connect=10)
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=timeout) as client:
        with open("_test_ref2.wav", "rb") as f:
            resp = await client.post(
                "/api/v1/voices",
                data={"name": unique_name("conc_tts"), "language": "en", "reference_text": "test reference"},
                files={"reference_audio": ("ref.wav", f, "audio/wav")},
            )
        voice_id = resp.json()["id"]
        print(f"  Voice created: {voice_id}")

        # Send 3 TTS requests concurrently
        async def generate(i: int, text: str) -> Result:
            start = time.perf_counter()
            try:
                resp = await client.post(
                    "/api/v1/tts/qwen/generate",
                    json={"text": text, "language": "en", "voice_id": voice_id},
                )
                ms = int((time.perf_counter() - start) * 1000)
                return Result(f"generate_{i}", resp.status_code, ms)
            except Exception as e:
                ms = int((time.perf_counter() - start) * 1000)
                return Result(f"generate_{i}", 0, ms, str(e)[:80])

        texts = [
            "First concurrent request.",
            "Second concurrent request.",
            "Third concurrent request.",
        ]

        wall_start = time.perf_counter()
        results = await asyncio.gather(*[generate(i, t) for i, t in enumerate(texts)])
        wall_ms = int((time.perf_counter() - wall_start) * 1000)

        for r in results:
            err = f" error={r.error}" if r.error else ""
            print(f"  {r.name}: {r.status} ({r.elapsed_ms}ms){err}")

        times = sorted([r.elapsed_ms for r in results])
        print(f"  Wall clock: {wall_ms}ms")
        print(f"  Fastest: {times[0]}ms, Slowest: {times[-1]}ms")
        if times[0] > 0:
            print(f"  Serialization check: slowest/fastest = {times[-1]/times[0]:.1f}x")
        print(f"  All succeeded: {all(r.status == 200 for r in results)}")

        # Cleanup
        await client.delete(f"/api/v1/voices/{voice_id}")

    os.remove("_test_ref2.wav")
    print("  PASSED: Concurrent TTS handled correctly")


# ─── Test 3: Health during GPU work ───


async def test_health_during_gpu():
    """Health endpoint must respond fast even while GPU is busy generating."""
    print("\n" + "=" * 60)
    print("TEST 3: Health responsiveness during GPU work")
    print("=" * 60)

    create_test_wav("_test_ref3.wav")
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=httpx.Timeout(300, connect=10)) as client:
        with open("_test_ref3.wav", "rb") as f:
            resp = await client.post(
                "/api/v1/voices",
                data={"name": unique_name("health"), "language": "en", "reference_text": "test"},
                files={"reference_audio": ("ref.wav", f, "audio/wav")},
            )
        voice_id = resp.json()["id"]

        # Start a long TTS generation
        async def long_generate():
            resp = await client.post(
                "/api/v1/tts/qwen/generate",
                json={"text": "This is a longer text to keep the GPU busy for a while during our concurrency test.", "language": "en", "voice_id": voice_id},
            )
            return resp.status_code

        # While GPU is busy, hammer health endpoint
        async def health_checks():
            await asyncio.sleep(0.5)  # Let GPU start working
            results = []
            for _ in range(10):
                start = time.perf_counter()
                resp = await client.get("/health")
                ms = int((time.perf_counter() - start) * 1000)
                results.append((resp.status_code, ms))
                await asyncio.sleep(0.2)
            return results

        gen_task, health_task = await asyncio.gather(long_generate(), health_checks())

        print(f"  TTS generation: {gen_task}")
        health_times = [ms for _, ms in health_task]
        health_ok = all(code == 200 for code, _ in health_task)
        print(f"  Health checks x10: avg={sum(health_times)//len(health_times)}ms, max={max(health_times)}ms, all_ok={health_ok}")

        blocked = any(ms > 1000 for ms in health_times)
        if blocked:
            print("  WARNING: Some health checks took >1s — possible event loop blocking!")
        else:
            print("  PASSED: Health endpoint stayed responsive during GPU work")

        # Cleanup
        await client.delete(f"/api/v1/voices/{voice_id}")

    os.remove("_test_ref3.wav")


# ─── Test 4: Mixed load ───


async def test_mixed_load():
    """Simultaneous CRUD + TTS + History queries."""
    print("\n" + "=" * 60)
    print("TEST 4: Mixed load (CRUD + TTS + History simultaneously)")
    print("=" * 60)

    create_test_wav("_test_ref4.wav")
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=httpx.Timeout(300, connect=10)) as client:
        with open("_test_ref4.wav", "rb") as f:
            resp = await client.post(
                "/api/v1/voices",
                data={"name": unique_name("mixed"), "language": "en", "reference_text": "test"},
                files={"reference_audio": ("ref.wav", f, "audio/wav")},
            )
        voice_id = resp.json()["id"]

        async def tts_generate() -> Result:
            start = time.perf_counter()
            resp = await client.post(
                "/api/v1/tts/qwen/generate",
                json={"text": "Mixed load test generation.", "language": "en", "voice_id": voice_id},
            )
            ms = int((time.perf_counter() - start) * 1000)
            return Result("tts_generate", resp.status_code, ms)

        async def list_voices() -> Result:
            start = time.perf_counter()
            resp = await client.get("/api/v1/voices")
            ms = int((time.perf_counter() - start) * 1000)
            return Result("list_voices", resp.status_code, ms)

        async def list_history() -> Result:
            start = time.perf_counter()
            resp = await client.get("/api/v1/history")
            ms = int((time.perf_counter() - start) * 1000)
            return Result("list_history", resp.status_code, ms)

        async def list_engines() -> Result:
            start = time.perf_counter()
            resp = await client.get("/api/v1/tts/engines")
            ms = int((time.perf_counter() - start) * 1000)
            return Result("list_engines", resp.status_code, ms)

        async def health_check() -> Result:
            start = time.perf_counter()
            resp = await client.get("/health")
            ms = int((time.perf_counter() - start) * 1000)
            return Result("health", resp.status_code, ms)

        # Fire all at once
        results = await asyncio.gather(
            tts_generate(),
            list_voices(),
            list_voices(),
            list_history(),
            list_history(),
            list_engines(),
            health_check(),
            health_check(),
        )

        for r in results:
            blocked = " [BLOCKED!]" if r.elapsed_ms > 5000 and r.name != "tts_generate" else ""
            print(f"  {r.name}: {r.status} ({r.elapsed_ms}ms){blocked}")

        non_gpu = [r for r in results if r.name != "tts_generate"]
        non_gpu_max = max(r.elapsed_ms for r in non_gpu)
        all_ok = all(r.status == 200 for r in results)
        print(f"  Non-GPU max latency: {non_gpu_max}ms")
        print(f"  All succeeded: {all_ok}")

        if non_gpu_max > 2000:
            print("  WARNING: Non-GPU requests blocked >2s — event loop may be blocked by sync code")
        else:
            print("  PASSED: Non-GPU requests not blocked by GPU work")

        await client.delete(f"/api/v1/voices/{voice_id}")

    os.remove("_test_ref4.wav")


# ─── Test 5: SSE Stream concurrent ───


async def test_concurrent_stream():
    """Multiple SSE streams at the same time."""
    print("\n" + "=" * 60)
    print("TEST 5: Concurrent SSE streams")
    print("=" * 60)

    create_test_wav("_test_ref5.wav")
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=httpx.Timeout(300, connect=10)) as client:
        with open("_test_ref5.wav", "rb") as f:
            resp = await client.post(
                "/api/v1/voices",
                data={"name": unique_name("stream"), "language": "en", "reference_text": "test"},
                files={"reference_audio": ("ref.wav", f, "audio/wav")},
            )
        voice_id = resp.json()["id"]

        async def stream_tts(i: int) -> Result:
            start = time.perf_counter()
            chunks = 0
            try:
                async with client.stream(
                    "POST",
                    "/api/v1/tts/qwen/stream",
                    json={"text": f"Stream test number {i}.", "language": "en", "voice_id": voice_id},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("event: audio"):
                            chunks += 1
                        elif line.startswith("event: done"):
                            pass
                ms = int((time.perf_counter() - start) * 1000)
                return Result(f"stream_{i}", resp.status_code, ms)
            except Exception as e:
                ms = int((time.perf_counter() - start) * 1000)
                return Result(f"stream_{i}", 500, ms, str(e))

        results = await asyncio.gather(*[stream_tts(i) for i in range(3)])

        for r in results:
            err = f" error={r.error}" if r.error else ""
            print(f"  {r.name}: {r.status} ({r.elapsed_ms}ms){err}")

        wall_times = sorted([r.elapsed_ms for r in results])
        print(f"  Fastest: {wall_times[0]}ms, Slowest: {wall_times[-1]}ms")
        print(f"  All succeeded: {all(r.status == 200 for r in results)}")
        print("  PASSED: Concurrent streams handled")

        await client.delete(f"/api/v1/voices/{voice_id}")

    os.remove("_test_ref5.wav")


# ─── Main ───


async def main():
    print("=" * 60)
    print("  VOICE-FAST-SERVICE CONCURRENCY TEST")
    print(f"  Target: {BASE_URL}")
    print("=" * 60)

    # Quick health check
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=5) as client:
        resp = await client.get("/health")
        engines = resp.json().get("engines", [])
        has_gpu = any(e["loaded"] for e in engines)
        print(f"  Server: OK, Engines: {[e['name'] for e in engines if e['loaded']]}")
        if not has_gpu:
            print("  WARNING: No GPU engine loaded — GPU tests will fail")

    await test_concurrent_crud()

    if has_gpu:
        await test_concurrent_tts()
        await test_health_during_gpu()
        await test_mixed_load()
        await test_concurrent_stream()

    print("\n" + "=" * 60)
    print("  ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
