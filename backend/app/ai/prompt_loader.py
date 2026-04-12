from pathlib import Path
from typing import Protocol

from app.core.config import BACKEND_DIR


PROMPT_DIR = BACKEND_DIR / "prompts"


class PromptTemplateProvider(Protocol):
    def load(self, name: str, version: str = "v1") -> str:
        ...


class FilePromptTemplateProvider:
    def __init__(self, prompt_dir: Path = PROMPT_DIR) -> None:
        self.prompt_dir = prompt_dir

    def load(self, name: str, version: str = "v1") -> str:
        path = self.prompt_dir / name / f"{version}.md"
        return path.read_text(encoding="utf-8-sig")


class PromptLoader(FilePromptTemplateProvider):
    """Backward-compatible alias for the default file-based prompt provider."""
