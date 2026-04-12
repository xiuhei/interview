"""
ASR / TTS 抽象接口。
通过配置文件切换实现（Mock / Whisper / 阿里云等）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    text: str
    language: str = "zh"
    confidence: float = 1.0
    duration_ms: int = 0


class SpeechRecognitionService(ABC):
    """ASR 抽象接口"""

    @abstractmethod
    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        ...


class TextToSpeechService(ABC):
    """TTS 抽象接口（后端 TTS，预留）"""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        ...
