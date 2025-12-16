"""WebSocket endpoints for CosyVoice3 - v3 Real-time bidirectional streaming"""
import asyncio
import json
import logging
import time
import uuid
import base64
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.websockets import WebSocketState

from app.models.streaming import (
    WebSocketMessage, WebSocketMessageType, WebSocketSynthesisRequest,
    WebSocketAudioChunk, WebSocketSynthesisStart, WebSocketSynthesisComplete,
    WebSocketError, WebSocketStatus, StreamingSession, StreamingSynthesisRequest
)
from app.core.streaming_synthesis_engine import StreamingSynthesisEngine
from app.core.synthesis_engine import SynthesisEngine
from app.core.voice_manager_v3 import VoiceManagerV3

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket (v3)"])

_streaming_engine_v3: Optional[StreamingSynthesisEngine] = None


class WebSocketManagerV3:
    """Manage WebSocket connections and sessions for CosyVoice3"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.active_sessions: Dict[str, StreamingSession] = {}

    async def connect(self, websocket: WebSocket, client_id: str = None) -> str:
        """Accept WebSocket connection and create session"""
        await websocket.accept()

        session_id = f"ws_v3_{uuid.uuid4().hex[:12]}"

        session = StreamingSession(
            session_id=session_id,
            client_id=client_id,
            created_at=time.time(),
            last_activity=time.time(),
            connection_type="websocket"
        )

        self.active_connections[session_id] = websocket
        self.active_sessions[session_id] = session

        logger.info(f"WebSocket connected (v3): session_id={session_id}, client_id={client_id}")
        return session_id

    def disconnect(self, session_id: str):
        """Remove connection and session"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        logger.info(f"WebSocket disconnected (v3): session_id={session_id}")

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


ws_manager_v3 = WebSocketManagerV3()


def get_voice_manager_v3(request: Request) -> VoiceManagerV3:
    """Dependency to get voice manager v3 from app state"""
    voice_manager = getattr(request.app.state, 'voice_manager_v3', None)
    return voice_manager


def get_streaming_engine_v3(voice_manager: VoiceManagerV3) -> StreamingSynthesisEngine:
    """Get or create streaming synthesis engine for v3"""
    global _streaming_engine_v3

    if voice_manager is None:
        return None

    # Create a synthesis engine adapter for v3
    from app.core.synthesis_engine import SynthesisEngine

    class SynthesisEngineV3Adapter(SynthesisEngine):
        def __init__(self, voice_manager_v3):
            self.voice_manager = voice_manager_v3

    if _streaming_engine_v3 is None:
        synthesis_engine = SynthesisEngineV3Adapter(voice_manager)
        _streaming_engine_v3 = StreamingSynthesisEngine(synthesis_engine)

    return _streaming_engine_v3


@router.websocket("/stream")
async def websocket_streaming_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = None
):
    """WebSocket endpoint for real-time streaming synthesis (CosyVoice3)

    CosyVoice3 provides:
    - ~150ms latency for streaming
    - Better content consistency
    - Improved speaker similarity
    - More natural prosody
    """

    session_id = None
    streaming_engine = None

    try:
        # Get voice manager from app state
        voice_manager = getattr(websocket.app.state, 'voice_manager_v3', None)
        if voice_manager is None:
            await websocket.close(code=1011, reason="CosyVoice3 voice manager not available")
            return

        streaming_engine = get_streaming_engine_v3(voice_manager)
        if streaming_engine is None:
            await websocket.close(code=1011, reason="CosyVoice3 streaming engine not available")
            return

        session_id = await ws_manager_v3.connect(websocket, client_id)

        await ws_manager_v3.send_message(session_id, WebSocketStatus(
            timestamp=time.time(),
            status="connected",
            message=f"WebSocket session {session_id} established (CosyVoice3)"
        ))

        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                message_type = message_data.get("message_type")
                request_id = message_data.get("request_id")

                if message_type == WebSocketMessageType.TEXT_REQUEST:
                    await handle_synthesis_request_v3(
                        session_id, message_data, streaming_engine, request_id
                    )

                elif message_type == WebSocketMessageType.PING:
                    await ws_manager_v3.send_message(session_id, WebSocketMessage(
                        message_type=WebSocketMessageType.PONG,
                        request_id=request_id,
                        timestamp=time.time()
                    ))

                else:
                    await ws_manager_v3.send_error(
                        session_id, "UNKNOWN_MESSAGE_TYPE",
                        f"Unknown message type: {message_type}", request_id
                    )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected (v3): {session_id}")
                break
            except json.JSONDecodeError:
                await ws_manager_v3.send_error(
                    session_id, "INVALID_JSON", "Invalid JSON message format"
                )
            except Exception as e:
                logger.error(f"Error handling WebSocket message (v3): {e}")
                await ws_manager_v3.send_error(
                    session_id, "MESSAGE_PROCESSING_ERROR", str(e)
                )

    except Exception as e:
        logger.error(f"WebSocket connection error (v3): {e}")

    finally:
        if session_id:
            ws_manager_v3.disconnect(session_id)


async def handle_synthesis_request_v3(
    session_id: str,
    message_data: dict,
    streaming_engine: StreamingSynthesisEngine,
    request_id: str = None
):
    """Handle synthesis request from WebSocket client (CosyVoice3)"""

    try:
        synthesis_request = WebSocketSynthesisRequest(**message_data)

        await ws_manager_v3.send_message(session_id, WebSocketSynthesisStart(
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

            await ws_manager_v3.send_message(session_id, audio_chunk)
            chunk_count += 1

            if metadata.is_final:
                total_duration = chunk_count * (metadata.sample_rate / 1000.0)
                break

        synthesis_time = time.time() - start_time
        await ws_manager_v3.send_message(session_id, WebSocketSynthesisComplete(
            request_id=request_id,
            timestamp=time.time(),
            total_chunks=chunk_count,
            total_duration=total_duration,
            synthesis_time=synthesis_time
        ))

        logger.info(f"WebSocket synthesis (v3) completed: {chunk_count} chunks, {synthesis_time:.2f}s")

    except Exception as e:
        logger.error(f"WebSocket synthesis error (v3): {e}")
        await ws_manager_v3.send_error(
            session_id, "SYNTHESIS_ERROR", f"CosyVoice3 synthesis failed: {str(e)}", request_id
        )


@router.get("/sessions")
async def get_active_sessions():
    """Get information about active WebSocket sessions (CosyVoice3)"""
    sessions_info = []
    for session_id, session in ws_manager_v3.active_sessions.items():
        sessions_info.append({
            "session_id": session_id,
            "client_id": session.client_id,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "active_requests": session.active_requests,
            "total_requests": session.total_requests
        })

    return {
        "version": "v3",
        "model": "CosyVoice3",
        "active_sessions": len(sessions_info),
        "sessions": sessions_info,
        "timestamp": time.time()
    }
