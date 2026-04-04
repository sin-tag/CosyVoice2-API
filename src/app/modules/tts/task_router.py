"""Async task endpoints for TTS generation.

When GPU is busy, tasks queue as 'pending'. Poll status to get result.
"""

import io
import logging

import soundfile as sf
from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.dependencies import DB, ApiKey
from app.core.task_queue import TaskStatus, task_queue
from app.engine.registry import engine_registry
from app.engine.voice_cache import voice_cache
from app.modules.tts.schemas import TTSGenerateRequest
from app.modules.tts.service import generate_speech

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ──── Submit async TTS ────


@router.post("/tts/xtts")
async def submit_xtts_task(body: TTSGenerateRequest, db: DB, _: ApiKey):
    """Submit an OmniVoice TTS task to the queue. Returns task_id + status immediately."""
    task = await task_queue.submit(
        generate_speech,
        db, "xtts", body.text, body.language, body.voice_id,
        temperature=body.temperature, top_p=body.top_p, top_k=body.top_k,
        repetition_penalty=body.repetition_penalty,
        meta={"engine": "xtts", "text": body.text[:80], "language": body.language},
    )
    return _task_response(task)


# ──── Task status & results ────


@router.get("/{task_id}")
async def get_task_status(_: ApiKey, task_id: str):
    """Check task status. Returns pending/processing/completed/failed."""
    task = task_queue.get_task(task_id)
    if task is None:
        from app.core.exceptions import AppError
        raise AppError(404, f"Task '{task_id}' not found", error_code="task_not_found")
    return _task_response(task)


@router.get("/{task_id}/audio")
async def get_task_audio(_: ApiKey, task_id: str):
    """Download audio result of a completed task."""
    task = task_queue.get_task(task_id)
    if task is None:
        from app.core.exceptions import AppError
        raise AppError(404, f"Task '{task_id}' not found", error_code="task_not_found")

    if task.status != TaskStatus.COMPLETED:
        from app.core.exceptions import AppError
        raise AppError(400, f"Task not completed (status: {task.status})", error_code="task_not_ready")

    wav_bytes, sr, history_id = task.result
    return Response(content=wav_bytes, media_type="audio/wav", headers={"X-History-Id": str(history_id)})


@router.get("")
async def list_tasks(
    _: ApiKey,
    status: str | None = Query(None, description="Filter: pending, processing, completed, failed"),
    limit: int = Query(50, ge=1, le=200),
):
    """List tasks with optional status filter."""
    filter_status = TaskStatus(status) if status else None
    tasks = task_queue.list_tasks(status=filter_status, limit=limit)
    return {
        "tasks": [_task_response(t) for t in tasks],
        "total": len(tasks),
        "queue": task_queue.queue_info(),
    }


def _task_response(task) -> dict:
    resp = {
        "task_id": task.task_id,
        "status": task.status.value,
        "queue_position": task.queue_position,
        "progress": task.progress,
        "message": task.message,
        "gpu_id": task.gpu_id,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }
    if task.meta:
        resp["meta"] = task.meta
    if task.error_message:
        resp["error_message"] = task.error_message
    if task.status == TaskStatus.COMPLETED and task.result:
        wav_bytes, sr, history_id = task.result
        resp["audio_url"] = f"/api/v1/tasks/{task.task_id}/audio"
        resp["history_id"] = str(history_id)
        num_samples = (len(wav_bytes) - 44) // 2
        resp["duration"] = round(num_samples / sr, 2) if sr > 0 else 0
        resp["sample_rate"] = sr
    if task.status == TaskStatus.PENDING:
        resp["check_status_url"] = f"/api/v1/tasks/{task.task_id}"
    return resp
