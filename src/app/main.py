import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.database import async_session_factory, engine as db_engine
from app.core.task_queue import task_queue
from app.core.exceptions import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.engine.registry import engine_registry

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load models, warm cache on startup; cleanup on shutdown."""
    logger.info("Starting %s...", settings.app_name)

    # 0. Auto-create SQLite tables if they don't exist
    from app.models.base import Base
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    # 1. Initialize TTS engines (loads models to GPU)
    await engine_registry.initialize(settings)
    logger.info("Engines loaded: %s", engine_registry.available_engines)

    # 2. Warm voice cache from DB
    async with async_session_factory() as db:
        await engine_registry.warm_cache(db)
    logger.info("Voice cache warmed")

    # 3. Log GPU status
    try:
        import torch
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(i) / 1024**3
                total = torch.cuda.get_device_properties(i).total_memory / 1024**3
                logger.info("GPU %d: %.1f/%.1f GB used", i, allocated, total)
    except ImportError:
        pass

    # 4. Start task queue workers
    task_queue.start_workers(num_workers=settings.max_concurrent_generations)
    logger.info("Task queue started")

    logger.info("%s started successfully", settings.app_name)
    yield

    # Shutdown
    await task_queue.stop()
    logger.info("Shutting down %s...", settings.app_name)
    await engine_registry.shutdown()
    await db_engine.dispose()
    logger.info("Shutdown complete")


# ──── Pure ASGI Middlewares (non-blocking) ────


class IPWhitelistMiddleware:
    """Pure ASGI middleware — does NOT block the event loop like BaseHTTPMiddleware."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self.allowed: set[str] = {
            ip.strip() for ip in settings.allowed_ips.split(",") if ip.strip()
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] in ("http", "websocket") and self.allowed:
            client = scope.get("client")
            client_ip = client[0] if client else None
            if client_ip not in self.allowed:
                logger.warning("Blocked request from %s", client_ip)
                if scope["type"] == "http":
                    resp = JSONResponse(status_code=403, content={"error": "access_denied", "message": "Access denied"})
                    await resp(scope, receive, send)
                    return
                # WebSocket: reject by closing before accept
                await send({"type": "websocket.close", "code": 4003})
                return
        await self.app(scope, receive, send)


class ConcurrencyLimitMiddleware:
    """Limit total concurrent requests so the server doesn't get overwhelmed."""

    def __init__(self, app: ASGIApp, max_concurrent: int):
        self.app = app
        self._sem = asyncio.Semaphore(max_concurrent)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if self._sem.locked():
            if scope["type"] == "http":
                resp = JSONResponse(
                    status_code=503,
                    content={"error": "server_busy", "message": "Too many concurrent requests"},
                )
                await resp(scope, receive, send)
                return
            await send({"type": "websocket.close", "code": 4013})
            return

        async with self._sem:
            await self.app(scope, receive, send)


# ──── App ────

app = FastAPI(
    title=settings.app_name,
    description="High-speed voice streaming & cloning API with MOSS-TTS-Realtime and Qwen3-TTS",
    version="0.1.0",
    lifespan=lifespan,
)

# Exception handlers — standardized {"error", "message", "details"} format
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Middleware order: outermost runs first
# 1. IP whitelist (reject bad IPs immediately)
app.add_middleware(IPWhitelistMiddleware)
# 2. Concurrency limit (reject when overloaded)
app.add_middleware(ConcurrencyLimitMiddleware, max_concurrent=settings.max_concurrent_requests)
# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from app.modules.voices.router import router as voices_router
from app.modules.tts.router import router as tts_router
from app.modules.tts.task_router import router as task_router
from app.modules.comic.router import router as comic_router
from app.modules.history.router import router as history_router
from app.ws.stream_handler import router as ws_router

app.include_router(voices_router)
app.include_router(tts_router)
app.include_router(task_router)
app.include_router(comic_router)
app.include_router(history_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "engines": engine_registry.list_engines(),
        "concurrency": {
            "max_requests": settings.max_concurrent_requests,
            "gpu_slots": engine_registry.all_gpu_slots(),
        },
        "queue": task_queue.queue_info(),
    }
