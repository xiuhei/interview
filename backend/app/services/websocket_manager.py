"""
WebSocket 会话管理器 — 管理连接池、消息收发、心跳。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.schemas.websocket import ServerMessage

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15  # 秒
HEARTBEAT_TIMEOUT = 60   # 秒


class WebSocketSession:
    """单个 WebSocket 会话"""

    def __init__(self, ws: WebSocket, session_id: str):
        self.ws = ws
        self.session_id = session_id
        self.last_heartbeat = time.time()
        self.connected = True

    async def send(self, msg: ServerMessage) -> None:
        if not self.connected:
            return
        try:
            await self.ws.send_text(msg.to_json())
        except Exception:
            logger.warning("发送消息失败 session=%s", self.session_id)
            self.connected = False

    async def close(self, code: int = 1000) -> None:
        self.connected = False
        try:
            await self.ws.close(code=code)
        except Exception:
            pass

    def touch_heartbeat(self) -> None:
        self.last_heartbeat = time.time()

    def is_alive(self) -> bool:
        return self.connected and (time.time() - self.last_heartbeat < HEARTBEAT_TIMEOUT)


class WebSocketManager:
    """全局 WebSocket 连接管理器"""

    def __init__(self):
        self._sessions: dict[str, WebSocketSession] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, session_id: str) -> WebSocketSession:
        await ws.accept()
        session = WebSocketSession(ws, session_id)
        async with self._lock:
            # 如果已有连接，先关闭旧的
            old = self._sessions.get(session_id)
            if old and old.connected:
                logger.info("替换旧连接 session=%s", session_id)
                await old.close(code=4001)
            self._sessions[session_id] = session
        logger.info("WebSocket 连接建立 session=%s", session_id)
        return session

    async def disconnect(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            session.connected = False
            logger.info("WebSocket 连接断开 session=%s", session_id)

    def get_session(self, session_id: str) -> WebSocketSession | None:
        return self._sessions.get(session_id)

    async def send_to(self, session_id: str, msg: ServerMessage) -> bool:
        session = self._sessions.get(session_id)
        if session and session.connected:
            await session.send(msg)
            return True
        return False

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.connected)


# 全局单例
ws_manager = WebSocketManager()
