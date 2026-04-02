"""GPU-aware async task queue.

Each GPU gets its own worker. Tasks are dispatched to the least-busy GPU.
When all GPUs busy, tasks queue as 'pending' until a GPU frees up.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    queue_position: int = 0
    progress: float = 0.0
    message: str = "Queued"
    gpu_id: int | None = None  # Which GPU is processing this task

    # Result
    result: Any = None
    error_message: str | None = None

    # Timestamps
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None

    # Metadata
    meta: dict = field(default_factory=dict)


class TaskQueue:
    """GPU-aware task queue. One worker per GPU, shared pending queue."""

    def __init__(self, max_queue_size: int = 100):
        self._tasks: dict[str, Task] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max_queue_size)
        self._max_queue_size = max_queue_size
        self._workers_started = False
        self._worker_tasks: list[asyncio.Task] = []
        self._num_gpus = 0
        # Per-GPU counters
        self._gpu_processing: dict[int, int] = {}  # gpu_id → active task count
        self._gpu_completed: dict[int, int] = {}  # gpu_id → total completed
        self._gpu_devices: dict[int, str] = {}  # gpu_id → device name

    def start_workers(self, num_gpus: int = 1, concurrency_per_gpu: int = 1, gpu_devices: list[str] | None = None):
        """Start one worker per GPU.

        Args:
            num_gpus: Number of GPUs (= number of workers)
            concurrency_per_gpu: Max concurrent tasks per GPU worker
            gpu_devices: Device names for logging (e.g. ["cuda:0", "cuda:1"])
        """
        if self._workers_started:
            return
        self._workers_started = True
        self._num_gpus = num_gpus

        for gpu_id in range(num_gpus):
            self._gpu_processing[gpu_id] = 0
            self._gpu_completed[gpu_id] = 0
            device = (gpu_devices[gpu_id] if gpu_devices and gpu_id < len(gpu_devices) else f"gpu:{gpu_id}")
            self._gpu_devices[gpu_id] = device

            for _ in range(concurrency_per_gpu):
                t = asyncio.create_task(self._gpu_worker(gpu_id))
                self._worker_tasks.append(t)

        total_workers = num_gpus * concurrency_per_gpu
        logger.info(
            "Task queue: %d GPU(s) x %d worker(s) = %d parallel slots, max queue: %d",
            num_gpus, concurrency_per_gpu, total_workers, self._max_queue_size,
        )

    async def stop(self):
        for t in self._worker_tasks:
            t.cancel()
        self._worker_tasks.clear()
        self._workers_started = False

    async def submit(
        self,
        coro_fn: Callable[..., Coroutine],
        *args,
        meta: dict | None = None,
        **kwargs,
    ) -> Task:
        """Submit a task to the queue."""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = Task(task_id=task_id, meta=meta or {})

        if self._queue.full():
            task.status = TaskStatus.FAILED
            task.error_message = "Queue full"
            task.message = "Queue full — try again later"
            self._tasks[task_id] = task
            return task

        task._coro_fn = coro_fn
        task._args = args
        task._kwargs = kwargs
        task.queue_position = self._queue.qsize()
        task.message = f"Queued (position {task.queue_position})" if task.queue_position > 0 else "Queued (next)"

        self._tasks[task_id] = task
        await self._queue.put(task_id)
        self._update_positions()

        logger.info("Task %s queued (position %d)", task_id, task.queue_position)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None, limit: int = 50) -> list[Task]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)

    @property
    def processing_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PROCESSING)

    def queue_info(self) -> dict:
        return {
            "pending": self.pending_count,
            "processing": self.processing_count,
            "max_queue_size": self._max_queue_size,
            "gpus": [
                {
                    "gpu_id": gpu_id,
                    "device": self._gpu_devices.get(gpu_id, "?"),
                    "active_tasks": self._gpu_processing.get(gpu_id, 0),
                    "total_completed": self._gpu_completed.get(gpu_id, 0),
                }
                for gpu_id in range(self._num_gpus)
            ],
        }

    async def _gpu_worker(self, gpu_id: int):
        """Worker bound to a specific GPU. Picks tasks from shared queue."""
        device = self._gpu_devices.get(gpu_id, f"gpu:{gpu_id}")
        logger.info("GPU worker started: %s (gpu_id=%d)", device, gpu_id)

        while True:
            try:
                task_id = await self._queue.get()
                task = self._tasks.get(task_id)
                if task is None:
                    continue

                task.status = TaskStatus.PROCESSING
                task.started_at = time.time()
                task.gpu_id = gpu_id
                task.message = f"Processing on {device}..."
                task.progress = 0.1
                self._gpu_processing[gpu_id] = self._gpu_processing.get(gpu_id, 0) + 1
                self._update_positions()

                try:
                    result = await task._coro_fn(*task._args, **task._kwargs)
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.progress = 1.0
                    task.message = f"Completed on {device}"
                    task.completed_at = time.time()
                    self._gpu_completed[gpu_id] = self._gpu_completed.get(gpu_id, 0) + 1
                    logger.info("Task %s completed on %s (%.1fs)", task_id, device, task.completed_at - task.started_at)
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    task.message = f"Failed on {device}"
                    task.completed_at = time.time()
                    logger.error("Task %s failed on %s: %s", task_id, device, e, exc_info=True)
                finally:
                    self._gpu_processing[gpu_id] = max(0, self._gpu_processing.get(gpu_id, 1) - 1)

                self._cleanup()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("GPU worker %s error", device, exc_info=True)

    def _update_positions(self):
        pos = 0
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING:
                task.queue_position = pos
                task.message = f"Queued (position {pos})" if pos > 0 else "Queued (next)"
                pos += 1

    def _cleanup(self):
        done = [t for t in self._tasks.values() if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)]
        if len(done) > 200:
            done.sort(key=lambda t: t.completed_at or 0)
            for t in done[:-200]:
                self._tasks.pop(t.task_id, None)


# Singleton
def _create_queue() -> TaskQueue:
    try:
        from app.core.config import settings
        return TaskQueue(max_queue_size=settings.max_queue_size)
    except Exception:
        return TaskQueue(max_queue_size=100)


task_queue = _create_queue()
