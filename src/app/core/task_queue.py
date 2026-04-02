"""In-memory async task queue for TTS generation.

When GPU is busy, tasks queue up as 'pending' instead of being rejected.
Callers can poll task status and retrieve results when ready.
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
    """In-memory task queue with configurable max queue size."""

    def __init__(self, max_queue_size: int = 100):
        self._tasks: dict[str, Task] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max_queue_size)
        self._max_queue_size = max_queue_size
        self._workers_started = False
        self._worker_tasks: list[asyncio.Task] = []

    def start_workers(self, num_workers: int = 1):
        """Start background worker(s) to process queued tasks."""
        if self._workers_started:
            return
        self._workers_started = True
        for i in range(num_workers):
            t = asyncio.create_task(self._worker(i))
            self._worker_tasks.append(t)
        logger.info("Task queue started with %d worker(s), max queue: %d", num_workers, self._max_queue_size)

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
        """Submit a task. Returns Task with status=pending and queue_position."""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = Task(task_id=task_id, meta=meta or {})

        if self._queue.full():
            task.status = TaskStatus.FAILED
            task.error_message = "Queue full"
            task.message = "Queue full — try again later"
            self._tasks[task_id] = task
            return task

        # Store the coroutine factory
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
    def queue_size(self) -> int:
        return self._queue.qsize()

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
        }

    async def _worker(self, worker_id: int):
        logger.info("Task queue worker %d started", worker_id)
        while True:
            try:
                task_id = await self._queue.get()
                task = self._tasks.get(task_id)
                if task is None:
                    continue

                task.status = TaskStatus.PROCESSING
                task.started_at = time.time()
                task.message = "Processing..."
                task.progress = 0.1
                self._update_positions()

                try:
                    result = await task._coro_fn(*task._args, **task._kwargs)
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.progress = 1.0
                    task.message = "Completed"
                    task.completed_at = time.time()
                    logger.info("Task %s completed (%.1fs)", task_id, task.completed_at - task.started_at)
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    task.message = f"Failed: {e}"
                    task.completed_at = time.time()
                    logger.error("Task %s failed: %s", task_id, e, exc_info=True)

                # Cleanup old completed/failed tasks (keep last 200)
                self._cleanup()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Task queue worker %d error", worker_id, exc_info=True)

    def _update_positions(self):
        """Recalculate queue positions for pending tasks."""
        pos = 0
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING:
                task.queue_position = pos
                task.message = f"Queued (position {pos})" if pos > 0 else "Queued (next)"
                pos += 1

    def _cleanup(self):
        """Remove old completed/failed tasks, keep last 200."""
        done = [
            t for t in self._tasks.values()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        ]
        if len(done) > 200:
            done.sort(key=lambda t: t.completed_at or 0)
            for t in done[:-200]:
                self._tasks.pop(t.task_id, None)


# Singleton — lazy init with settings
def _create_queue() -> TaskQueue:
    try:
        from app.core.config import settings
        return TaskQueue(max_queue_size=settings.max_queue_size)
    except Exception:
        return TaskQueue(max_queue_size=100)


task_queue = _create_queue()
