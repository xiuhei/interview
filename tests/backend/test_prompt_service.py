from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.prompt_service import PromptService


class StubPromptProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def load(self, name: str, version: str = "v1") -> str:
        self.calls.append((name, version))
        return f"prompt::{name}::{version}"


class StubLLMClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, prompt: str, variables: str) -> dict:
        self.calls.append((prompt, variables))
        return {"ok": True, "prompt": prompt}


def test_prompt_service_uses_injected_prompt_provider_and_llm_factory():
    prompt_provider = StubPromptProvider()
    llm_client = StubLLMClient()
    service = PromptService(
        prompt_provider=prompt_provider,
        llm_client_factory=lambda: llm_client,
    )

    payload, fallback_used = service.run_json_prompt(
        "score_answer",
        {"question": "Explain cache consistency."},
    )

    assert fallback_used is False
    assert payload["ok"] is True
    assert payload["prompt"] == "prompt::score_answer::v1"
    assert prompt_provider.calls == [("score_answer", "v1")]
    assert llm_client.calls
    assert "Explain cache consistency." in llm_client.calls[0][1]


def test_prompt_service_returns_fallback_when_llm_call_fails():
    prompt_provider = StubPromptProvider()

    class FailingLLMClient:
        def complete_json(self, prompt: str, variables: str) -> dict:
            _ = prompt, variables
            raise RuntimeError("boom")

    service = PromptService(
        prompt_provider=prompt_provider,
        llm_client_factory=lambda: FailingLLMClient(),
    )

    payload, fallback_used = service.run_json_prompt(
        "resume_parse",
        {"resume_text": "sample"},
        fallback_result={"source": "fallback"},
    )

    assert fallback_used is True
    assert payload == {"source": "fallback"}
    assert prompt_provider.calls == [("resume_parse", "v1")]
