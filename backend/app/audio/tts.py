from __future__ import annotations

import base64
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException


@dataclass
class TTSResult:
    audio_base64: str
    mime_type: str
    model: str
    voice: str


class TTSService(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> TTSResult:
        raise NotImplementedError


class RemoteQwenTTSService(TTSService):
    def __init__(self) -> None:
        self.settings = get_settings()

    def synthesize(self, text: str) -> TTSResult:
        normalized_text = _normalize_tts_text(text)
        if not normalized_text:
            raise AppException("TTS text is empty", 400)

        headers = {
            "Authorization": f"Bearer {self.settings.tts_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.tts_model,
            "input": {
                "text": normalized_text,
                "voice": self.settings.tts_voice,
                "language_type": self.settings.tts_language,
            },
        }
        with httpx.Client(timeout=90) as client:
            try:
                response = client.post(
                    self.settings.tts_base_url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = _extract_http_error_detail(exc.response)
                status_code = 400 if exc.response.status_code < 500 else 502
                raise AppException(f"TTS request failed: {detail}", status_code) from exc

            body = response.json()
            audio_base64 = _extract_audio_base64(body)
            mime_type = _audio_format_to_mime(self.settings.tts_format)
            if not audio_base64:
                audio_url = _extract_audio_url(body)
                if not audio_url:
                    raise AppException("TTS service returned no audio payload", 502)
                audio_base64, mime_type = _download_audio_payload(client, audio_url, mime_type)

        _ensure_base64(audio_base64)
        return TTSResult(
            audio_base64=audio_base64,
            mime_type=mime_type,
            model=self.settings.tts_model,
            voice=self.settings.tts_voice,
        )


def get_tts_service() -> TTSService:
    settings = get_settings()
    if not settings.tts_ready:
        raise AppException("TTS API 未配置，请先设置 QWEN_API_KEY、QWEN_TTS_MODEL 和 QWEN_TTS_VOICE。", 400)
    return RemoteQwenTTSService()


def _normalize_tts_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = normalized.replace("...", "，").replace("..", "，")
    normalized = normalized.replace("——", "，").replace("--", "，")
    return normalized


def _extract_audio_base64(payload: dict) -> str:
    output = payload.get("output") or {}
    audio = output.get("audio") or {}
    return str(
        audio.get("data")
        or audio.get("audio_base64")
        or output.get("audio_base64")
        or payload.get("audio_base64")
        or ""
    ).strip()


def _extract_audio_url(payload: dict) -> str:
    output = payload.get("output") or {}
    audio = output.get("audio") or {}
    return str(audio.get("url") or payload.get("audio_url") or "").strip()


def _download_audio_payload(client: httpx.Client, audio_url: str, default_mime_type: str) -> tuple[str, str]:
    try:
        response = client.get(audio_url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = _extract_http_error_detail(exc.response)
        raise AppException(f"TTS audio download failed: {detail}", 502) from exc

    content = response.content
    if not content:
        raise AppException("TTS audio download returned empty content", 502)

    mime_type = response.headers.get("Content-Type", "").split(";")[0].strip() or default_mime_type
    if mime_type == "application/octet-stream":
        mime_type = _mime_type_from_url(audio_url, default_mime_type)
    return base64.b64encode(content).decode("ascii"), mime_type


def _mime_type_from_url(audio_url: str, default_mime_type: str) -> str:
    path = urlparse(audio_url).path.lower()
    if path.endswith(".mp3"):
        return "audio/mpeg"
    if path.endswith(".wav"):
        return "audio/wav"
    if path.endswith(".pcm"):
        return "audio/pcm"
    return default_mime_type


def _ensure_base64(audio_base64: str) -> None:
    try:
        base64.b64decode(audio_base64, validate=True)
    except Exception as exc:  # pragma: no cover - defensive parsing guard
        raise AppException("TTS audio payload is invalid", 502) from exc


def _audio_format_to_mime(audio_format: str) -> str:
    normalized = audio_format.strip().lower()
    if normalized == "mp3":
        return "audio/mpeg"
    if normalized == "wav":
        return "audio/wav"
    if normalized == "pcm":
        return "audio/pcm"
    return "application/octet-stream"


def _extract_http_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or payload)
    if isinstance(error, str):
        return error
    return str(payload)
