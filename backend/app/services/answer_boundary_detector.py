"""
Boundary detector for continuous interview answers.

The detector combines silence grade, transcript growth, answer sufficiency
and explicit semantic cues before deciding whether to keep waiting, prompt,
or finalize the current answer turn.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.ai.json_tools import parse_json
from app.speech.silence_grader import SilenceEvent, SilenceGrade

logger = logging.getLogger(__name__)


class BoundaryAction(str, Enum):
    WAIT = "wait"
    PROMPT_CONTINUE = "prompt_continue"
    FINALIZE = "finalize"


@dataclass
class BoundaryDecision:
    action: BoundaryAction
    confidence: float = 0.5
    reason: str = ""
    llm_decision: str = ""
    should_wait: bool = True
    should_prompt: bool = False
    answer_complete_estimate: str = "low"


_END_MARKERS = (
    "我说完了",
    "我回答完了",
    "就这些",
    "差不多就是这些",
    "大概就是这样",
    "以上就是",
    "暂时想到的就这些",
    "回答完毕",
)

_SUPPLEMENT_MARKERS = (
    "我再补充",
    "补充一下",
    "我再说一点",
    "另外",
    "还有一个",
    "对了",
    "哦对",
)

_INSUFFICIENT_END_MARKERS = (
    "一下子想不起来",
    "我先想到这些",
    "暂时没有了",
    "有点卡住了",
)


class AnswerBoundaryDetector:
    def __init__(
        self,
        llm_caller: Any = None,
        prompt_provider: Any = None,
        min_speech_ms: int = 2000,
        min_substantive_chars: int = 20,
        medium_pause_finalize_chars: int = 80,
        long_pause_finalize_chars: int = 40,
    ):
        self._llm_caller = llm_caller
        self._prompt_provider = prompt_provider
        self._min_speech_ms = min_speech_ms
        self._min_substantive_chars = min_substantive_chars
        self._medium_pause_finalize_chars = medium_pause_finalize_chars
        self._long_pause_finalize_chars = long_pause_finalize_chars

        self._text_snapshots: list[tuple[float, str]] = []
        self._last_transcript: str = ""
        self._has_been_prompted = False

    def reset(self) -> None:
        self._text_snapshots.clear()
        self._last_transcript = ""
        self._has_been_prompted = False

    def update_transcript(self, transcript: str) -> None:
        normalized = self._normalize_text(transcript)
        if normalized != self._last_transcript:
            self._text_snapshots.append((time.monotonic(), normalized))
            self._last_transcript = normalized

    def mark_prompted(self) -> None:
        self._has_been_prompted = True

    async def evaluate(
        self,
        silence_event: SilenceEvent,
        current_transcript: str,
        question: str,
        question_type: str = "technical",
    ) -> BoundaryDecision:
        transcript = self._normalize_text(current_transcript)
        self.update_transcript(transcript)

        has_substantive_content = len(transcript) >= self._min_substantive_chars
        has_end_markers = self._has_end_markers(transcript)
        has_supplement_markers = self._has_supplement_markers(transcript)
        touched_key_points = self._estimate_key_point_coverage(question, transcript)
        text_growing = self._is_text_growing(window_seconds=3.0)
        recent_growth = len(self._get_recent_text(seconds=5.0))
        completeness = self._estimate_completeness(
            transcript=transcript,
            has_substantive_content=has_substantive_content,
            touched_key_points=touched_key_points,
            has_end_markers=has_end_markers,
        )

        if silence_event.grade == SilenceGrade.SHORT_PAUSE:
            return self._decision(
                BoundaryAction.WAIT,
                confidence=0.96,
                reason="short_pause",
                answer_complete_estimate=completeness,
            )

        if text_growing:
            return self._decision(
                BoundaryAction.WAIT,
                confidence=0.88,
                reason="transcript_still_growing",
                answer_complete_estimate=completeness,
            )

        if has_supplement_markers:
            return self._decision(
                BoundaryAction.WAIT,
                confidence=0.84,
                reason="supplement_signal_detected",
                answer_complete_estimate=completeness,
            )

        if silence_event.grade == SilenceGrade.EXTENDED_SILENCE:
            if not has_substantive_content:
                return self._decision(
                    BoundaryAction.FINALIZE,
                    confidence=0.93,
                    reason="extended_silence_with_insufficient_content",
                    llm_decision="end_with_insufficient_content",
                    answer_complete_estimate="very_low",
                )
            return self._decision(
                BoundaryAction.FINALIZE,
                confidence=0.97,
                reason="extended_silence",
                llm_decision="end_current_answer",
                answer_complete_estimate=completeness,
            )

        if has_end_markers and has_substantive_content:
            return self._decision(
                BoundaryAction.FINALIZE,
                confidence=0.92,
                reason="explicit_end_marker",
                llm_decision="end_current_answer",
                answer_complete_estimate=completeness,
            )

        if silence_event.grade == SilenceGrade.MEDIUM_PAUSE:
            if (
                silence_event.speech_before_ms < self._min_speech_ms
                or not has_substantive_content
                or recent_growth > 0
            ):
                return self._decision(
                    BoundaryAction.WAIT,
                    confidence=0.72,
                    reason="medium_pause_but_answer_not_ready",
                    answer_complete_estimate=completeness,
                )
            if len(transcript) >= self._medium_pause_finalize_chars and touched_key_points:
                return self._decision(
                    BoundaryAction.FINALIZE,
                    confidence=0.75,
                    reason="medium_pause_with_sufficient_content",
                    llm_decision="end_current_answer",
                    answer_complete_estimate=completeness,
                )
            if self._llm_caller and self._prompt_provider:
                return await self._llm_boundary_check(
                    silence_event=silence_event,
                    transcript=transcript,
                    question=question,
                    question_type=question_type,
                    has_substantive_content=has_substantive_content,
                    touched_key_points=touched_key_points,
                    has_end_markers=has_end_markers,
                    completeness=completeness,
                )
            return self._decision(
                BoundaryAction.WAIT,
                confidence=0.55,
                reason="medium_pause_keep_observing",
                answer_complete_estimate=completeness,
            )

        if silence_event.grade == SilenceGrade.LONG_PAUSE:
            if not has_substantive_content:
                if self._has_been_prompted or self._looks_abandoned(transcript):
                    return self._decision(
                        BoundaryAction.FINALIZE,
                        confidence=0.82,
                        reason="long_pause_after_prompt_with_insufficient_content",
                        llm_decision="end_with_insufficient_content",
                        answer_complete_estimate="very_low",
                    )
                return self._decision(
                    BoundaryAction.PROMPT_CONTINUE,
                    confidence=0.8,
                    reason="long_pause_with_insufficient_content",
                    llm_decision="prompt_candidate_to_continue",
                    answer_complete_estimate="low",
                )

            if (
                len(transcript) >= self._long_pause_finalize_chars
                and (touched_key_points or has_end_markers)
            ):
                return self._decision(
                    BoundaryAction.FINALIZE,
                    confidence=0.86,
                    reason="long_pause_with_sufficient_content",
                    llm_decision="end_current_answer",
                    answer_complete_estimate=completeness,
                )

            if self._llm_caller and self._prompt_provider:
                return await self._llm_boundary_check(
                    silence_event=silence_event,
                    transcript=transcript,
                    question=question,
                    question_type=question_type,
                    has_substantive_content=has_substantive_content,
                    touched_key_points=touched_key_points,
                    has_end_markers=has_end_markers,
                    completeness=completeness,
                )

            if self._has_been_prompted:
                return self._decision(
                    BoundaryAction.FINALIZE,
                    confidence=0.67,
                    reason="long_pause_after_prompt",
                    llm_decision="end_current_answer",
                    answer_complete_estimate=completeness,
                )
            return self._decision(
                BoundaryAction.PROMPT_CONTINUE,
                confidence=0.62,
                reason="long_pause_needs_soft_prompt",
                llm_decision="prompt_candidate_to_continue",
                answer_complete_estimate=completeness,
            )

        return self._decision(
            BoundaryAction.WAIT,
            confidence=0.5,
            reason="fallback_wait",
            answer_complete_estimate=completeness,
        )

    async def _llm_boundary_check(
        self,
        silence_event: SilenceEvent,
        transcript: str,
        question: str,
        question_type: str,
        has_substantive_content: bool,
        touched_key_points: bool,
        has_end_markers: bool,
        completeness: str,
    ) -> BoundaryDecision:
        try:
            prompt_template = self._prompt_provider.load("voice_boundary_check")
            user_content = prompt_template
            user_content = user_content.replace("{{ question }}", question)
            user_content = user_content.replace("{{ transcript }}", transcript)
            user_content = user_content.replace(
                "{{ recent_text }}",
                self._get_recent_text(seconds=5.0) or "(无新增文本)",
            )
            user_content = user_content.replace("{{ silence_duration_ms }}", str(silence_event.duration_ms))
            user_content = user_content.replace("{{ answer_length }}", str(len(transcript)))
            user_content = user_content.replace("{{ question_type }}", question_type)
            user_content = user_content.replace("{{ has_been_prompted }}", str(self._has_been_prompted))
            user_content = user_content.replace("{{ speech_before_ms }}", str(silence_event.speech_before_ms))
            user_content = user_content.replace("{{ has_substantive_content }}", str(has_substantive_content))
            user_content = user_content.replace("{{ touched_key_points }}", str(touched_key_points))
            user_content = user_content.replace("{{ has_explicit_end_signal }}", str(has_end_markers))
            user_content = user_content.replace("{{ answer_complete_estimate }}", completeness)

            raw = await self._llm_caller(
                "你是一名专业技术面试官和对话轮次判断器。",
                user_content,
                True,
            )
            result = parse_json(raw)
            decision = result.get("decision", "keep_waiting")
            action_map = {
                "end_current_answer": BoundaryAction.FINALIZE,
                "end_with_insufficient_content": BoundaryAction.FINALIZE,
                "prompt_candidate_to_continue": BoundaryAction.PROMPT_CONTINUE,
                "keep_waiting": BoundaryAction.WAIT,
                "short_pause_continue_waiting": BoundaryAction.WAIT,
            }
            return self._decision(
                action_map.get(decision, BoundaryAction.WAIT),
                confidence=float(result.get("confidence", 0.5)),
                reason=result.get("reason", "llm_boundary_check"),
                llm_decision=decision,
                should_wait=bool(result.get("should_wait", decision in {"keep_waiting", "short_pause_continue_waiting"})),
                should_prompt=bool(result.get("should_prompt", decision == "prompt_candidate_to_continue")),
                answer_complete_estimate=result.get("answer_complete_estimate", completeness),
            )
        except Exception:
            logger.warning("LLM boundary check failed; falling back to rules")
            if silence_event.grade == SilenceGrade.LONG_PAUSE and len(transcript) >= self._long_pause_finalize_chars:
                return self._decision(
                    BoundaryAction.FINALIZE,
                    confidence=0.62,
                    reason="llm_failed_long_pause_finalize",
                    llm_decision="end_current_answer",
                    answer_complete_estimate=completeness,
                )
            return self._decision(
                BoundaryAction.WAIT,
                confidence=0.42,
                reason="llm_failed_keep_waiting",
                answer_complete_estimate=completeness,
            )

    def _decision(
        self,
        action: BoundaryAction,
        confidence: float,
        reason: str,
        llm_decision: str = "",
        should_wait: bool | None = None,
        should_prompt: bool | None = None,
        answer_complete_estimate: str = "low",
    ) -> BoundaryDecision:
        if should_wait is None:
            should_wait = action == BoundaryAction.WAIT
        if should_prompt is None:
            should_prompt = action == BoundaryAction.PROMPT_CONTINUE
        return BoundaryDecision(
            action=action,
            confidence=confidence,
            reason=reason,
            llm_decision=llm_decision,
            should_wait=should_wait,
            should_prompt=should_prompt,
            answer_complete_estimate=answer_complete_estimate,
        )

    def _is_text_growing(self, window_seconds: float = 3.0) -> bool:
        if len(self._text_snapshots) < 2:
            return False
        cutoff = time.monotonic() - window_seconds
        recent = [snapshot for snapshot in self._text_snapshots if snapshot[0] >= cutoff]
        if len(recent) < 2:
            return False
        return len(recent[-1][1]) > len(recent[0][1])

    def _get_recent_text(self, seconds: float = 5.0) -> str:
        if len(self._text_snapshots) < 2:
            return self._last_transcript
        cutoff = time.monotonic() - seconds
        recent = [snapshot for snapshot in self._text_snapshots if snapshot[0] >= cutoff]
        if not recent:
            return ""
        earliest = recent[0][1]
        latest = recent[-1][1]
        if latest.startswith(earliest):
            return latest[len(earliest):].strip()
        prefix_len = 0
        for left_char, right_char in zip(earliest, latest):
            if left_char != right_char:
                break
            prefix_len += 1
        return latest[prefix_len:].strip()

    def _estimate_key_point_coverage(self, question: str, transcript: str) -> bool:
        question_tokens = [
            token for token in self._tokenize(question)
            if len(token) >= 2 and token not in {"什么", "怎么", "如何", "为什么", "一个"}
        ]
        if not question_tokens:
            return len(transcript) >= 60
        transcript_tokens = set(self._tokenize(transcript))
        overlap = sum(1 for token in question_tokens if token in transcript_tokens)
        return overlap >= max(1, min(2, len(question_tokens) // 2))

    def _estimate_completeness(
        self,
        transcript: str,
        has_substantive_content: bool,
        touched_key_points: bool,
        has_end_markers: bool,
    ) -> str:
        length = len(transcript)
        if not has_substantive_content:
            return "very_low" if length < 8 else "low"
        if length >= 140 and touched_key_points:
            return "high"
        if length >= 90 and (touched_key_points or has_end_markers):
            return "medium_high"
        if length >= 45:
            return "medium"
        return "low"

    def _looks_abandoned(self, transcript: str) -> bool:
        tail = transcript[-30:]
        return any(marker in tail for marker in _INSUFFICIENT_END_MARKERS)

    @staticmethod
    def _has_end_markers(text: str) -> bool:
        tail = text[-30:]
        return any(marker in tail for marker in _END_MARKERS)

    @staticmethod
    def _has_supplement_markers(text: str) -> bool:
        tail = text[-24:]
        return any(marker in tail for marker in _SUPPLEMENT_MARKERS)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join((text or "").strip().split())

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        tokens: list[str] = []
        current = []
        for char in text:
            if char.isalnum():
                current.append(char.lower())
                continue
            if current:
                tokens.append("".join(current))
                current = []
            if "\u4e00" <= char <= "\u9fff":
                tokens.append(char)
        if current:
            tokens.append("".join(current))
        return tokens
