"""WebSocket endpoints for CosyVoice2 - v2 Real-time bidirectional streaming"""
import asyncio
import json
import logging
import time
import uuid
import base64
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.websockets import WebSocketState

from app.models.streaming import (
    WebSocketMessage, WebSocketMessageType, WebSocketSynthesisRequest,
    WebSocketAudioChunk, WebSocketSynthesisStart, WebSocketSynthesisComplete,
    WebSocketError, WebSocketStatus, StreamingSession, StreamingSynthesisRequest
)
from app.core.streaming_synthesis_engine import StreamingSynthesisEngine
from app.core.synthesis_engine import SynthesisEngine
from app.dependencies import get_synthesis_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket (v2)"])

active_connections: Dict[str, WebSocket] = {}
active_sessions: Dict[str, StreamingSession] = {}

_streaming_engine: Optional[StreamingSynthesisEngine] = None


def get_streaming_engine(
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
) -> StreamingSynthesisEngine:
    """Get or create streaming synthesis engine"""
    global _streaming_engine
    if _streaming_engine is None:
        _streaming_engine = StreamingSynthesisEngine(synthesis_engine)
    return _streaming_engine


class WebSocketManagerV2:
    """Manage WebSocket connections and sessions for v2"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.active_sessions: Dict[str, StreamingSession] = {}

    async def connect(self, websocket: WebSocket, client_id: str = None) -> str:
        """Accept WebSocket connection and create session"""
        await websocket.accept()

        session_id = f"ws_v2_{uuid.uuid4().hex[:12]}"

        session = StreamingSession(
            session_id=session_id,
            client_id=client_id,
            created_at=time.time(),
            last_activity=time.time(),
            connection_type="websocket"
        )

        self.active_connections[session_id] = websocket
        self.active_sessions[session_id] = session

        logger.info(f"WebSocket connected (v2): session_id={session_id}, client_id={client_id}")
        return session_id

    def disconnect(self, session_id: str):
        """Remove connection and session"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        logger.info(f"WebSocket disconnected (v2): session_id={session_id}")

    async def send_message(self, session_id: str, message: WebSocketMessage):
        """Send message to specific session"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(message.json())
                if session_id in self.active_sessions:
                    self.active_sessions[session_id].last_activity = time.time()
            except Exception as e:
                logger.error(f"Failed to send message to {session_id}: {e}")
                self.disconnect(session_id)

    async def send_error(self, session_id: str, error_code: str, error_message: str, request_id: str = None):
        """Send error message to session"""
        error_msg = WebSocketError(
            request_id=request_id,
            timestamp=time.time(),
            error_code=error_code,
            error_message=error_message
        )
        await self.send_message(session_id, error_msg)


ws_manager_v2 = WebSocketManagerV2()


@router.websocket("/stream")
async def websocket_streaming_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = None
):
    """WebSocket endpoint for real-time streaming synthesis (CosyVoice2)"""

    session_id = None
    streaming_engine = None

    try:
        from app.dependencies import get_synthesis_engine
        synthesis_engine = get_synthesis_engine()
        streaming_engine = StreamingSynthesisEngine(synthesis_engine)

        session_id = await ws_manager_v2.connect(websocket, client_id)

        await ws_manager_v2.send_message(session_id, WebSocketStatus(
            timestamp=time.time(),
            status="connected",
            message=f"WebSocket session {session_id} established (CosyVoice2)"
        ))

        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                message_type = message_data.get("message_type")
                request_id = message_data.get("request_id")

                if message_type == WebSocketMessageType.TEXT_REQUEST:
                    await handle_synthesis_request_v2(
                        session_id, message_data, streaming_engine, request_id
                    )

                elif message_type == WebSocketMessageType.PING:
                    await ws_manager_v2.send_message(session_id, WebSocketMessage(
                        message_type=WebSocketMessageType.PONG,
                        request_id=request_id,
                        timestamp=time.time()
                    ))

                else:
                    await ws_manager_v2.send_error(
                        session_id, "UNKNOWN_MESSAGE_TYPE",
                        f"Unknown message type: {message_type}", request_id
                    )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {session_id}")
                break
            except json.JSONDecodeError:
                await ws_manager_v2.send_error(
                    session_id, "INVALID_JSON", "Invalid JSON message format"
                )
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await ws_manager_v2.send_error(
                    session_id, "MESSAGE_PROCESSING_ERROR", str(e)
                )

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")

    finally:
        if session_id:
            ws_manager_v2.disconnect(session_id)


async def handle_synthesis_request_v2(
    session_id: str,
    message_data: dict,
    streaming_engine: StreamingSynthesisEngine,
    request_id: str = None
):
    """Handle synthesis request from WebSocket client (v2)"""

    try:
        synthesis_request = WebSocketSynthesisRequest(**message_data)

        await ws_manager_v2.send_message(session_id, WebSocketSynthesisStart(
            request_id=request_id,
            timestamp=time.time(),
            text=synthesis_request.text,
            voice_id=synthesis_request.voice_id
        ))

        streaming_request = StreamingSynthesisRequest(
            text=synthesis_request.text,
            voice_id=synthesis_request.voice_id,
            format=synthesis_request.format,
            speed=synthesis_request.speed,
            quality=synthesis_request.quality
        )

        chunk_count = 0
        total_duration = 0.0
        start_time = time.time()

        async for chunk_bytes, metadata in streaming_engine.stream_cross_lingual_synthesis(streaming_request):
            audio_data_b64 = base64.b64encode(chunk_bytes).decode('utf-8')

            audio_chunk = WebSocketAudioChunk(
                request_id=request_id,
                timestamp=time.time(),
                audio_data=audio_data_b64,
                metadata=metadata
            )

            await ws_manager_v2.send_message(session_id, audio_chunk)
            chunk_count += 1

            if metadata.is_final:
                total_duration = chunk_count * (metadata.sample_rate / 1000.0)
                break

        synthesis_time = time.time() - start_time
        await ws_manager_v2.send_message(session_id, WebSocketSynthesisComplete(
            request_id=request_id,
            timestamp=time.time(),
            total_chunks=chunk_count,
            total_duration=total_duration,
            synthesis_time=synthesis_time
        ))

        logger.info(f"WebSocket synthesis completed (v2): {chunk_count} chunks, {synthesis_time:.2f}s")

    except Exception as e:
        logger.error(f"WebSocket synthesis error: {e}")
        await ws_manager_v2.send_error(
            session_id, "SYNTHESIS_ERROR", f"Synthesis failed: {str(e)}", request_id
        )


@router.get("/sessions")
async def get_active_sessions():
    """Get information about active WebSocket sessions (v2)"""
    sessions_info = []
    for session_id, session in ws_manager_v2.active_sessions.items():
        sessions_info.append({
            "session_id": session_id,
            "client_id": session.client_id,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "active_requests": session.active_requests,
            "total_requests": session.total_requests
        })

    return {
        "version": "v2",
        "active_sessions": len(sessions_info),
        "sessions": sessions_info,
        "timestamp": time.time()
    }
