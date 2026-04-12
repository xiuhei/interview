"""
Decides whether prolonged silence should trigger a soft interviewer nudge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.ai.json_tools import parse_json

logger = logging.getLogger(__name__)


@dataclass
class SilencePromptDecision:
    should_prompt: bool
    prompt_text: str = ""
    reason: str = ""
    next_action_if_no_response: str = "keep_waiting"


class SilencePromptDecider:
    def __init__(self, llm_caller: Any = None, prompt_provider: Any = None):
        self._llm_caller = llm_caller
        self._prompt_provider = prompt_provider

    async def decide(
        self,
        question: str,
        transcript: str,
        silence_duration_ms: int,
        reminder_count: int,
        completeness_estimate: str,
        question_type: str = "technical",
    ) -> SilencePromptDecision:
        if reminder_count >= 2:
            return SilencePromptDecision(
                should_prompt=False,
                reason="reminder_limit_reached",
                next_action_if_no_response="end_current_answer",
            )

        if silence_duration_ms < 6500:
            return SilencePromptDecision(
                should_prompt=False,
                reason="silence_not_long_enough",
                next_action_if_no_response="keep_waiting",
            )

        if self._llm_caller and self._prompt_provider:
            try:
                prompt = self._prompt_provider.load("voice_silence_nudge")
                user_content = prompt.replace("{{ question }}", question or "")
                user_content = user_content.replace("{{ transcript }}", transcript or "(尚未回答)")
                user_content = user_content.replace("{{ silence_duration_ms }}", str(silence_duration_ms))
                user_content = user_content.replace("{{ reminder_count }}", str(reminder_count))
                user_content = user_content.replace("{{ completeness_estimate }}", completeness_estimate)
                user_content = user_content.replace("{{ question_type }}", question_type)
                raw = await self._llm_caller("你是一名自然语音面试官。", user_content, True)
                result = parse_json(raw)
                return SilencePromptDecision(
                    should_prompt=bool(result.get("should_prompt", False)),
                    prompt_text=result.get("prompt_text", ""),
                    reason=result.get("reason", "llm_prompt_decision"),
                    next_action_if_no_response=result.get(
                        "next_action_if_no_response",
                        "end_current_answer" if reminder_count >= 1 else "keep_waiting",
                    ),
                )
            except Exception:
                logger.warning("Silence prompt decision via LLM failed")

        if completeness_estimate in {"very_low", "low"}:
            return SilencePromptDecision(
                should_prompt=True,
                prompt_text="你可以先说说你的初步思路，想到哪里就说到哪里。",
                reason="fallback_prompt_for_incomplete_answer",
                next_action_if_no_response="end_current_answer",
            )

        return SilencePromptDecision(
            should_prompt=False,
            reason="fallback_no_prompt_for_complete_answer",
            next_action_if_no_response="end_current_answer",
        )
