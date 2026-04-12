import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.ai.json_tools import parse_json
from app.core.config import get_settings
from app.core.exceptions import AppException


class LLMClient(ABC):
    @abstractmethod
    def complete_json(self, prompt: str, variables: dict[str, Any] | str) -> dict[str, Any]:
        raise NotImplementedError


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(self) -> None:
        self.settings = get_settings()

    def complete_json(self, prompt: str, variables: dict[str, Any] | str) -> dict[str, Any]:
        user_content = (
            variables
            if isinstance(variables, str)
            else json.dumps(variables, ensure_ascii=False, sort_keys=True, indent=2)
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.llm_base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.settings.llm_model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return parse_json(content)


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if not settings.llm_ready:
        raise AppException("LLM API 未配置，请先设置 QWEN_API_KEY 和 QWEN_LLM_MODEL。", 400)
    return OpenAICompatibleLLMClient()
