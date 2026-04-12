from abc import ABC, abstractmethod

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException


MAX_EMBED_BATCH_SIZE = 10


class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OpenAICompatibleEmbeddingClient(EmbeddingClient):
    def __init__(self) -> None:
        self.settings = get_settings()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        headers = {"Authorization": f"Bearer {self.settings.embedding_api_key}"}
        embeddings: list[list[float]] = []
        with httpx.Client(timeout=30) as client:
            for start in range(0, len(texts), MAX_EMBED_BATCH_SIZE):
                batch = texts[start:start + MAX_EMBED_BATCH_SIZE]
                response = client.post(
                    f"{self.settings.embedding_base_url}/embeddings",
                    headers=headers,
                    json={
                        "model": self.settings.embedding_model,
                        "input": batch,
                        "dimensions": self.settings.embedding_dimension,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                embeddings.extend(item["embedding"] for item in payload["data"])
        return embeddings


def get_embedding_client() -> EmbeddingClient:
    settings = get_settings()
    if not settings.embedding_ready:
        raise AppException("Embedding API 未配置，请先设置 QWEN_API_KEY 和 QWEN_EMBEDDING_MODEL。", 400)
    return OpenAICompatibleEmbeddingClient()
