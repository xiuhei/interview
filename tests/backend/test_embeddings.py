from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.embeddings import OpenAICompatibleEmbeddingClient


class FakeResponse:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self._embeddings = embeddings

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "data": [{"embedding": item} for item in self._embeddings],
        }


class FakeClient:
    def __init__(self, recorder: list[dict]) -> None:
        self.recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: dict, json: dict):
        _ = url, headers
        self.recorder.append(json)
        size = len(json["input"])
        return FakeResponse([[float(size), float(index)] for index in range(size)])


def test_embedding_client_batches_requests_and_passes_dimensions(monkeypatch):
    recorded_payloads: list[dict] = []
    client = object.__new__(OpenAICompatibleEmbeddingClient)
    client.settings = SimpleNamespace(
        embedding_api_key="test",
        embedding_base_url="https://example.com",
        embedding_model="text-embedding-v3",
        embedding_dimension=512,
    )

    monkeypatch.setattr(
        "app.ai.embeddings.httpx.Client",
        lambda timeout=30: FakeClient(recorded_payloads),
    )

    embeddings = client.embed([f"text-{index}" for index in range(23)])

    assert len(recorded_payloads) == 3
    assert [len(item["input"]) for item in recorded_payloads] == [10, 10, 3]
    assert all(item["dimensions"] == 512 for item in recorded_payloads)
    assert len(embeddings) == 23
