"""
WebSocket 面试端点 — 实时语音面试的通信通道。
增强版：支持持续语音面试模式的 force_answer_end 消息。
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas.websocket import ClientMessage, ClientMessageType, ServerMessage
from app.services.interview_orchestrator import (
    InterviewOrchestratorService,
    get_orchestrator,
    register_orchestrator,
    remove_orchestrator,
)
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: str):
    """
    面试 WebSocket 端点。
    消息协议参见 schemas/websocket.py。
    """
    ws_session = await ws_manager.connect(websocket, session_id)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                msg = ClientMessage(**data)
            except Exception:
                await ws_session.send(ServerMessage.error("invalid_message", "消息格式错误"))
                continue

            ws_session.touch_heartbeat()

            # 消息分发
            if msg.type == ClientMessageType.HEARTBEAT:
                await ws_session.send(ServerMessage.heartbeat_ack())

            elif msg.type == ClientMessageType.SESSION_START:
                await _handle_session_start(session_id, msg.payload, ws_session)

            elif msg.type == ClientMessageType.AUDIO_CHUNK:
                await _handle_audio_chunk(session_id, msg.payload)

            elif msg.type == ClientMessageType.SPEAK_DONE:
                await _handle_speak_done(session_id)

            elif msg.type == ClientMessageType.USER_STOP:
                # 旧模式：用户主动停止说话（备用）
                pass

            elif msg.type == ClientMessageType.FORCE_ANSWER_END:
                # 持续模式：用户手动标记回答结束
                await _handle_force_answer_end(session_id)

            elif msg.type == ClientMessageType.END_INTERVIEW:
                await _handle_end_interview(session_id)
                break

    except WebSocketDisconnect:
        logger.info("WebSocket 断开 session=%s", session_id)
    except Exception:
        logger.exception("WebSocket 异常 session=%s", session_id)
    finally:
        await ws_manager.disconnect(session_id)


async def _handle_session_start(session_id: str, payload: dict, ws_session):
    """处理面试开始"""
    orch = get_orchestrator(session_id)
    if not orch:
        orch = InterviewOrchestratorService(session_id)
        await orch.create_session(
            job_name=payload.get("job_name", "通用技术"),
            style=payload.get("style", "medium"),
            resume_summary=payload.get("resume_summary"),
            competencies=payload.get("competencies"),
        )
        register_orchestrator(session_id, orch)

    await ws_session.send(ServerMessage.session_ready(session_id))
    await orch.start_interview()


async def _handle_audio_chunk(session_id: str, payload: dict):
    """处理音频块"""
    orch = get_orchestrator(session_id)
    if not orch:
        return
    chunk_b64 = payload.get("data", "")
    if chunk_b64:
        await orch.handle_audio_chunk(chunk_b64)


async def _handle_speak_done(session_id: str):
    """前端 TTS 播完"""
    orch = get_orchestrator(session_id)
    if orch:
        await orch.handle_speak_done()


async def _handle_force_answer_end(session_id: str):
    """持续模式：用户手动标记回答结束"""
    orch = get_orchestrator(session_id)
    if orch:
        await orch.handle_force_answer_end()


async def _handle_end_interview(session_id: str):
    """结束面试"""
    orch = get_orchestrator(session_id)
    if orch:
        await orch.handle_user_end()
        remove_orchestrator(session_id)
