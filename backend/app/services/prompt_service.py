import json
import logging
from typing import Any

from app.ai.llm import get_llm_client
from app.ai.prompt_loader import FilePromptTemplateProvider, PromptTemplateProvider


logger = logging.getLogger(__name__)


class PromptService:
    def __init__(
        self,
        prompt_provider: PromptTemplateProvider | None = None,
        llm_client_factory=get_llm_client,
    ) -> None:
        self.prompt_provider = prompt_provider or FilePromptTemplateProvider()
        self.llm_client_factory = llm_client_factory
        self.llm = None

    def run_json_prompt(self, name: str, variables: dict[str, Any], fallback_result: dict[str, Any] | None = None) -> tuple[dict, bool]:
        prompt = self.prompt_provider.load(name)
        serialized_variables = self._serialize_variables(variables)
        try:
            payload = self._get_llm().complete_json(prompt, serialized_variables)
            logger.info(
                "prompt completed | name=%s fallback_used=%s variable_keys=%s",
                name,
                False,
                sorted(variables.keys()),
            )
            return payload, False
        except Exception:
            logger.exception(
                "prompt request failed | name=%s variable_keys=%s",
                name,
                sorted(variables.keys()),
            )
            if fallback_result is None:
                raise
            logger.warning(
                "prompt fallback used | name=%s variable_keys=%s",
                name,
                sorted(variables.keys()),
            )
            return fallback_result, True

    def _get_llm(self):
        if self.llm is None:
            self.llm = self.llm_client_factory()
        return self.llm

    def _serialize_variables(self, variables: dict[str, Any]) -> str:
        return json.dumps(variables, ensure_ascii=False, sort_keys=True, indent=2)
