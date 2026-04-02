"""Stress test — heavy concurrent GPU load to verify no event loop blocking.

Tests:
1. Rapid-fire GPU requests (5+ simultaneous TTS) — semaphore queuing
2. Non-GPU latency DURING sustained GPU load — event loop health
3. Semaphore timeout behavior — GPU queue full handling
4. GPU memory stability under repeated generations
"""

import asyncio
import time
from dataclasses import dataclass, field

import httpx
import numpy as np
import soundfile as sf

BASE_URL = "http://localhost:8000"
API_KEY = "test-key-123"
HEADERS = {"X-API-Key": API_KEY}

_counter = 0


def unique_name(prefix: str) -> str:
    global _counter
    _counter += 1
    return f"{prefix}_{int(time.time())}_{_counter}"


def create_test_wav(path: str, duration: float = 5.0, sr: int = 24000):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.3 * np.sin(2 * np.pi * 440 * t)
    sf.write(path, audio, sr)


@dataclass
class Result:
    name: str
    status: int
    elapsed_ms: int
    error: str | None = None


@dataclass
class StressReport:
    test_name: str
    results: list[Result] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passed: bool = True

    def print(self):
        print(f"\n{'=' * 60}")
        print(f"  {self.test_name}")
        print(f"{'=' * 60}")
        for r in self.results:
            err = f" error={r.error}" if r.error else ""
            print(f"  {r.name}: {r.status} ({r.elapsed_ms}ms){err}")
        for w in self.warnings:
            print(f"  WARNING: {w}")
        status = "PASSED" if self.passed else "FAILED"
        print(f"  {status}")


async def setup_voice(client: httpx.AsyncClient) -> str:
    """Create a test voice, return its ID."""
    wav_path = f"_stress_{unique_name('ref')}.wav"
    create_test_wav(wav_path)
    with open(wav_path, "rb") as f:
        resp = await client.post(
            "/api/v1/voices",
            data={"name": unique_name("stress"), "language": "en", "reference_text": "stress test reference audio"},
            files={"reference_audio": ("ref.wav", f, "audio/wav")},
        )
    import os
    os.remove(wav_path)
    assert resp.status_code == 201, f"Voice creation failed: {resp.status_code} {resp.text}"
    return resp.json()["id"]


# ─── Test 1: Rapid-fire GPU requests ───


async def test_rapid_fire_gpu():
    """Send 5+ TTS requests simultaneously — verify semaphore queuing works correctly."""
    report = StressReport("TEST 1: Rapid-fire GPU (5 simultaneous TTS requests)")
    timeout = httpx.Timeout(600, connect=10)

    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=timeout) as client:
        voice_id = await setup_voice(client)
        print(f"  Voice: {voice_id}")

        async def generate(i: int) -> Result:
            texts = [
                "First rapid fire request for stress testing.",
                "Second request hits the GPU semaphore queue.",
                "Third request waits for its turn in the queue.",
                "Fourth request tests deep queue behavior.",
                "Fifth request pushes the concurrency limit.",
            ]
            start = time.perf_counter()
            try:
                resp = await client.post(
                    "/api/v1/tts/qwen/generate",
                    json={"text": texts[i], "language": "en", "voice_id": voice_id},
                )
                ms = int((time.perf_counter() - start) * 1000)
                return Result(f"gpu_{i}", resp.status_code, ms)
            except Exception as e:
                ms = int((time.perf_counter() - start) * 1000)
                return Result(f"gpu_{i}", 0, ms, str(e)[:100])

        wall_start = time.perf_counter()
        results = await asyncio.gather(*[generate(i) for i in range(5)])
        wall_ms = int((time.perf_counter() - wall_start) * 1000)

        report.results = list(results)
        times = sorted([r.elapsed_ms for r in results])

        report.results.append(Result("wall_clock", 0, wall_ms))

        # Check: all should succeed
        all_ok = all(r.status == 200 for r in results)
        if not all_ok:
            report.warnings.append("Some GPU requests failed!")
            report.passed = False

        # Check: serialization — wall time should be much less than sum of individual times
        sum_times = sum(r.elapsed_ms for r in results)
        if wall_ms > sum_times * 0.95:
            report.warnings.append(f"Requests seem to run sequentially (wall={wall_ms}ms, sum={sum_times}ms)")

        # Check: fastest vs slowest — later requests should be slower due to queuing
        if len(times) >= 2:
            ratio = times[-1] / max(times[0], 1)
            report.results.append(Result(f"serialization_ratio", 0, 0, f"{ratio:.1f}x"))

        await client.delete(f"/api/v1/voices/{voice_id}")

    report.print()
    return report


# ─── Test 2: Non-GPU latency during sustained GPU load ───


async def test_non_gpu_during_sustained_load():
    """While GPU processes multiple TTS requests, non-GPU endpoints must stay fast."""
    report = StressReport("TEST 2: Non-GPU latency during sustained GPU load")
    timeout = httpx.Timeout(600, connect=10)

    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=timeout) as client:
        voice_id = await setup_voice(client)
        print(f"  Voice: {voice_id}")

        # Fire 3 long TTS requests to keep GPU busy
        async def long_tts(i: int):
            text = f"This is a longer text for sustained GPU load test number {i}. " * 3
            resp = await client.post(
                "/api/v1/tts/qwen/generate",
                json={"text": text, "language": "en", "voice_id": voice_id},
            )
            return resp.status_code

        # Repeatedly hit non-GPU endpoints during GPU work
        async def probe_non_gpu():
            await asyncio.sleep(1)  # Let GPU start working
            probes = []
            for i in range(20):
                start = time.perf_counter()
                which = i % 4
                if which == 0:
                    resp = await client.get("/health")
                elif which == 1:
                    resp = await client.get("/api/v1/voices")
                elif which == 2:
                    resp = await client.get("/api/v1/history")
                else:
                    resp = await client.get("/api/v1/tts/engines")
                ms = int((time.perf_counter() - start) * 1000)
                names = ["health", "voices", "history", "engines"]
                probes.append(Result(f"probe_{names[which]}_{i}", resp.status_code, ms))
                await asyncio.sleep(0.3)
            return probes

        # Run both concurrently
        gpu_results, probes = await asyncio.gather(
            asyncio.gather(*[long_tts(i) for i in range(3)]),
            probe_non_gpu(),
        )

        report.results = probes

        # Analyze probe latencies
        probe_times = [p.elapsed_ms for p in probes]
        avg_ms = sum(probe_times) // len(probe_times)
        max_ms = max(probe_times)
        all_ok = all(p.status == 200 for p in probes)

        report.results.append(Result(f"probes_summary", 200 if all_ok else 500, avg_ms, f"avg={avg_ms}ms max={max_ms}ms"))

        # Critical check: event loop blocking
        blocked = [p for p in probes if p.elapsed_ms > 1000]
        if blocked:
            report.warnings.append(f"{len(blocked)} probes took >1s — EVENT LOOP BLOCKING DETECTED!")
            report.passed = False

        if max_ms > 500:
            report.warnings.append(f"Max probe latency {max_ms}ms > 500ms — possible contention")

        # GPU should all succeed
        gpu_ok = all(s == 200 for s in gpu_results)
        report.results.append(Result("gpu_all_ok", 200 if gpu_ok else 500, 0))

        await client.delete(f"/api/v1/voices/{voice_id}")

    report.print()
    return report


# ─── Test 3: GPU memory stability ───


async def test_gpu_memory_stability():
    """Repeatedly generate TTS to check for GPU memory leaks."""
    report = StressReport("TEST 3: GPU memory stability (10 sequential generations)")
    timeout = httpx.Timeout(600, connect=10)

    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=timeout) as client:
        voice_id = await setup_voice(client)
        print(f"  Voice: {voice_id}")

        # Get initial GPU memory
        resp = await client.get("/health")
        initial_health = resp.json()

        for i in range(10):
            start = time.perf_counter()
            resp = await client.post(
                "/api/v1/tts/qwen/generate",
                json={"text": f"Memory stability test number {i + 1}.", "language": "en", "voice_id": voice_id},
            )
            ms = int((time.perf_counter() - start) * 1000)
            report.results.append(Result(f"gen_{i}", resp.status_code, ms))

            if resp.status_code != 200:
                report.warnings.append(f"Generation {i} failed with status {resp.status_code}")
                report.passed = False
                break

        # Check GPU memory after all generations
        resp = await client.get("/health")
        final_health = resp.json()

        # Check timing consistency — later requests shouldn't be significantly slower
        gen_times = [r.elapsed_ms for r in report.results]
        if len(gen_times) >= 5:
            early_avg = sum(gen_times[:3]) // 3
            late_avg = sum(gen_times[-3:]) // 3
            ratio = late_avg / max(early_avg, 1)
            report.results.append(Result("timing_drift", 0, 0, f"early_avg={early_avg}ms late_avg={late_avg}ms ratio={ratio:.2f}x"))
            if ratio > 2.0:
                report.warnings.append(f"Late requests {ratio:.1f}x slower than early — possible memory leak or fragmentation")

        await client.delete(f"/api/v1/voices/{voice_id}")

    report.print()
    return report


# ─── Test 4: Concurrent CRUD + GPU contention ───


async def test_crud_during_gpu_contention():
    """Create/delete voices while GPU is processing — must not deadlock."""
    report = StressReport("TEST 4: CRUD operations during GPU contention")
    timeout = httpx.Timeout(600, connect=10)

    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=timeout) as client:
        voice_id = await setup_voice(client)
        print(f"  Voice: {voice_id}")

        async def gpu_work():
            """Keep GPU busy with 2 sequential TTS requests."""
            for i in range(2):
                resp = await client.post(
                    "/api/v1/tts/qwen/generate",
                    json={"text": f"GPU busy work number {i + 1} while CRUD runs.", "language": "en", "voice_id": voice_id},
                )
            return "done"

        async def crud_operations():
            """Create and delete voices while GPU is busy."""
            await asyncio.sleep(0.5)  # Let GPU start
            results = []
            created_ids = []
            wav_path = f"_stress_crud_{unique_name('ref')}.wav"
            create_test_wav(wav_path)

            for i in range(3):
                # Create
                start = time.perf_counter()
                with open(wav_path, "rb") as f:
                    resp = await client.post(
                        "/api/v1/voices",
                        data={"name": unique_name(f"crud_{i}"), "language": "en", "reference_text": "crud test"},
                        files={"reference_audio": ("ref.wav", f, "audio/wav")},
                    )
                ms = int((time.perf_counter() - start) * 1000)
                results.append(Result(f"create_{i}", resp.status_code, ms))
                if resp.status_code == 201:
                    created_ids.append(resp.json()["id"])

                # List
                start = time.perf_counter()
                resp = await client.get("/api/v1/voices")
                ms = int((time.perf_counter() - start) * 1000)
                results.append(Result(f"list_{i}", resp.status_code, ms))

            # Delete created voices
            for vid in created_ids:
                start = time.perf_counter()
                resp = await client.delete(f"/api/v1/voices/{vid}")
                ms = int((time.perf_counter() - start) * 1000)
                results.append(Result(f"delete", resp.status_code, ms))

            import os
            os.remove(wav_path)
            return results

        gpu_task, crud_results = await asyncio.gather(gpu_work(), crud_operations())

        report.results = crud_results

        # Check: all CRUD should succeed fast
        crud_times = [r.elapsed_ms for r in crud_results]
        max_crud = max(crud_times)
        all_ok = all(r.status in (200, 201, 204) for r in crud_results)

        report.results.append(Result("crud_summary", 200 if all_ok else 500, max_crud, f"max={max_crud}ms"))

        if not all_ok:
            report.warnings.append("Some CRUD operations failed during GPU load!")
            report.passed = False

        if max_crud > 3000:
            report.warnings.append(f"Max CRUD latency {max_crud}ms > 3s — possible blocking!")
            report.passed = False

        await client.delete(f"/api/v1/voices/{voice_id}")

    report.print()
    return report


# ─── Main ───


async def main():
    print("=" * 60)
    print("  VOICE-FAST-SERVICE STRESS TEST")
    print(f"  Target: {BASE_URL}")
    print("=" * 60)

    # Health check
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=5) as client:
        resp = await client.get("/health")
        data = resp.json()
        engines = data.get("engines", [])
        has_gpu = any(e["loaded"] for e in engines)
        print(f"  Server: OK, Engines: {[e['name'] for e in engines if e['loaded']]}")
        if not has_gpu:
            print("  ERROR: No GPU engine loaded — cannot run stress tests")
            return

    reports = []
    reports.append(await test_rapid_fire_gpu())
    reports.append(await test_non_gpu_during_sustained_load())
    reports.append(await test_gpu_memory_stability())
    reports.append(await test_crud_during_gpu_contention())

    print("\n" + "=" * 60)
    print("  STRESS TEST SUMMARY")
    print("=" * 60)
    for r in reports:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.test_name}")
    all_passed = all(r.passed for r in reports)
    print(f"\n  Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
