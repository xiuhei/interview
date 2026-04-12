"""
WebSocket 消息协议 — 前后端统一的消息类型定义。
增强版：支持持续语音面试模式的新消息类型。
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ---- 前端 → 后端 消息类型 ----

class ClientMessageType(str, Enum):
    SESSION_START = "session_start"
    AUDIO_CHUNK = "audio_chunk"
    USER_STOP = "user_stop"
    SPEAK_DONE = "speak_done"               # 前端 TTS 播报完毕
    END_INTERVIEW = "end_interview"
    HEARTBEAT = "heartbeat"
    # ---- 持续模式新增 ----
    FORCE_ANSWER_END = "force_answer_end"   # 用户手动标记回答结束（可选）


class ClientMessage(BaseModel):
    type: ClientMessageType
    payload: dict[str, Any] = Field(default_factory=dict)


# ---- 后端 → 前端 消息类型 ----

class ServerMessageType(str, Enum):
    SESSION_READY = "session_ready"
    STATE_CHANGED = "state_changed"
    INTERVIEWER_SPEAK = "interviewer_speak"
    LISTENING = "listening"
    REPORT_READY = "report_ready"
    ERROR = "error"
    HEARTBEAT_ACK = "heartbeat_ack"
    # ---- 持续模式新增 ----
    SILENCE_NUDGE = "silence_nudge"         # 沉默提醒
    CONTINUOUS_MODE = "continuous_mode"      # 通知前端持续模式状态
    ANSWER_BOUNDARY = "answer_boundary"     # 通知前端检测到回答结束


class ServerMessage(BaseModel):
    type: ServerMessageType
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def session_ready(cls, session_id: str) -> "ServerMessage":
        return cls(type=ServerMessageType.SESSION_READY, payload={"session_id": session_id})

    @classmethod
    def state_changed(cls, state: str, round_no: int = 0) -> "ServerMessage":
        return cls(type=ServerMessageType.STATE_CHANGED, payload={"state": state, "round_no": round_no})

    @classmethod
    def interviewer_speak(
        cls,
        text: str,
        is_question: bool = False,
        audio_base64: str | None = None,
        mime_type: str | None = None,
    ) -> "ServerMessage":
        payload = {"text": text, "is_question": is_question}
        if audio_base64:
            payload["audio_base64"] = audio_base64
        if mime_type:
            payload["mime_type"] = mime_type
        return cls(type=ServerMessageType.INTERVIEWER_SPEAK, payload=payload)

    @classmethod
    def listening(cls) -> "ServerMessage":
        return cls(type=ServerMessageType.LISTENING)

    @classmethod
    def report_ready(cls, report: dict) -> "ServerMessage":
        return cls(type=ServerMessageType.REPORT_READY, payload={"report": report})

    @classmethod
    def error(cls, code: str, message: str) -> "ServerMessage":
        return cls(type=ServerMessageType.ERROR, payload={"code": code, "message": message})

    @classmethod
    def heartbeat_ack(cls) -> "ServerMessage":
        return cls(type=ServerMessageType.HEARTBEAT_ACK)

    # ---- 持续模式新增工厂方法 ----

    @classmethod
    def silence_nudge(cls, text: str, reminder_count: int) -> "ServerMessage":
        return cls(
            type=ServerMessageType.SILENCE_NUDGE,
            payload={"text": text, "reminder_count": reminder_count},
        )

    @classmethod
    def continuous_mode(cls, enabled: bool) -> "ServerMessage":
        return cls(
            type=ServerMessageType.CONTINUOUS_MODE,
            payload={"enabled": enabled},
        )

    @classmethod
    def answer_boundary(cls, round_no: int, confidence: float = 0.0) -> "ServerMessage":
        return cls(
            type=ServerMessageType.ANSWER_BOUNDARY,
            payload={"round_no": round_no, "confidence": confidence},
        )
