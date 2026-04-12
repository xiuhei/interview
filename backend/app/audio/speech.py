import base64
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException


OPENAI_COMPATIBLE_TRANSCRIPTION_PATHS = ("/chat/completions",)


class SpeechService(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> str:
        raise NotImplementedError


class RemoteSpeechService(SpeechService):
    def __init__(self) -> None:
        self.settings = get_settings()

    def _build_request_url(self) -> str:
        base_url = self.settings.speech_base_url.strip().rstrip("/")
        if any(base_url.endswith(path) for path in OPENAI_COMPATIBLE_TRANSCRIPTION_PATHS):
            return base_url
        return f"{base_url}/chat/completions"

    def _build_data_url(self, audio_path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(audio_path.name)
        resolved_mime_type = mime_type or "application/octet-stream"
        encoded_audio = base64.b64encode(audio_path.read_bytes()).decode("ascii")
        return f"data:{resolved_mime_type};base64,{encoded_audio}"

    def transcribe(self, audio_path: Path) -> str:
        headers = {"Authorization": f"Bearer {self.settings.speech_api_key}"}
        request_url = self._build_request_url()
        request_payload = {
            "model": self.settings.speech_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": self._build_data_url(audio_path),
                            },
                        }
                    ],
                }
            ],
            "stream": False,
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(
                request_url,
                headers=headers,
                json=request_payload,
            )
            response.raise_for_status()
            payload = response.json()
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not text:
            raise AppException("语音识别服务返回了空转写结果。", 400)
        return text


def get_speech_service() -> SpeechService:
    settings = get_settings()
    if not settings.speech_ready:
        raise AppException("语音识别 API 未配置，请先设置 QWEN_API_KEY 和 QWEN_ASR_MODEL。", 400)
    return RemoteSpeechService()
