"""
Answer segmentation for continuous voice interviews.

The service tracks transcript growth across pauses so we can persist:
- main answer segments
- supplement segments after long pauses / explicit supplement cues
- ignored noise-only fragments
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.ai.json_tools import parse_json

logger = logging.getLogger(__name__)


@dataclass
class AnswerSegment:
    index: int
    text: str
    start_ms: int
    end_ms: int
    gap_before_ms: int = 0
    is_supplement: bool = False
    is_ignored: bool = False
    source: str = "candidate"


@dataclass
class SegmentationResult:
    main_segments: list[int] = field(default_factory=list)
    supplement_segments: list[int] = field(default_factory=list)
    ignored_segments: list[int] = field(default_factory=list)
    merged_text: str = ""
    main_answer_text: str = ""
    supplement_text: str = ""
    reason: str = ""


_NOISE_PATTERNS = {
    "嗯",
    "啊",
    "额",
    "呃",
    "那个",
    "就是",
    "然后",
    "哦",
    "嗯嗯",
    "啊啊",
}

_SUPPLEMENT_SIGNALS = (
    "我补充一下",
    "我再补充一点",
    "我再说一点",
    "补充一下",
    "另外",
    "还有一点",
    "对了",
    "哦对",
)


class AnswerSegmentationService:
    def __init__(
        self,
        llm_caller: Any = None,
        prompt_provider: Any = None,
    ):
        self._llm_caller = llm_caller
        self._prompt_provider = prompt_provider
        self._segments: list[AnswerSegment] = []
        self._committed_text: str = ""

    def reset(self, question_start_ms: int = 0) -> None:
        self._segments.clear()
        self._committed_text = ""

    @property
    def segments(self) -> list[AnswerSegment]:
        return list(self._segments)

    @property
    def segment_count(self) -> int:
        return len(self._segments)

    def add_segment(
        self,
        text: str,
        start_ms: int,
        end_ms: int,
        gap_before_ms: int = 0,
        is_supplement: bool = False,
        source: str = "candidate",
    ) -> AnswerSegment | None:
        cleaned = self._normalize_text(text)
        if not cleaned:
            return None

        is_noise = self._is_noise(cleaned)
        segment = AnswerSegment(
            index=len(self._segments),
            text=cleaned,
            start_ms=start_ms,
            end_ms=end_ms,
            gap_before_ms=gap_before_ms,
            is_supplement=is_supplement,
            is_ignored=is_noise,
            source=source,
        )
        self._segments.append(segment)
        return segment

    def append_from_transcript(
        self,
        transcript: str,
        start_ms: int,
        end_ms: int,
        gap_before_ms: int = 0,
        force_supplement: bool = False,
    ) -> AnswerSegment | None:
        delta = self.extract_incremental_text(transcript)
        if not delta:
            return None

        is_supplement = force_supplement or self.should_mark_as_supplement(
            gap_before_ms=gap_before_ms,
            text=delta,
        )
        segment = self.add_segment(
            text=delta,
            start_ms=start_ms,
            end_ms=end_ms,
            gap_before_ms=gap_before_ms,
            is_supplement=is_supplement,
        )
        self._committed_text = self._normalize_text(transcript)
        return segment

    def extract_incremental_text(self, transcript: str) -> str:
        normalized = self._normalize_text(transcript)
        if not normalized:
            return ""
        if not self._committed_text:
            return normalized
        if normalized.startswith(self._committed_text):
            return normalized[len(self._committed_text):].strip()

        prefix_len = self._common_prefix_len(self._committed_text, normalized)
        delta = normalized[prefix_len:].strip()
        if not delta:
            return ""

        # If ASR rewrote too much, keep only the tail that was not already committed.
        overlap_words = self._suffix_overlap_words(self._committed_text, delta)
        if overlap_words:
            delta_words = delta.split()
            delta = " ".join(delta_words[overlap_words:]).strip()
        return delta

    def get_merged_transcript(self) -> str:
        return " ".join(
            segment.text for segment in self._segments if not segment.is_ignored
        ).strip()

    def get_main_answer_text(self) -> str:
        texts = [
            segment.text
            for segment in self._segments
            if not segment.is_ignored and not segment.is_supplement
        ]
        return " ".join(texts).strip()

    def get_supplement_text(self) -> str:
        texts = [
            segment.text
            for segment in self._segments
            if not segment.is_ignored and segment.is_supplement
        ]
        return " ".join(texts).strip()

    def should_mark_as_supplement(self, gap_before_ms: int, text: str) -> bool:
        normalized = self._normalize_text(text)
        if gap_before_ms >= 5000:
            return True
        if any(signal in normalized[:24] for signal in _SUPPLEMENT_SIGNALS):
            return True
        if len(self.get_main_answer_text()) >= 80 and gap_before_ms >= 3000:
            return True
        return False

    async def llm_segmentation(self, question: str) -> SegmentationResult:
        if not self._llm_caller or not self._prompt_provider or not self._segments:
            return self._rule_based_segmentation()

        try:
            prompt_template = self._prompt_provider.load("voice_answer_segmentation")
            segments_payload = [
                {
                    "index": segment.index,
                    "text": segment.text,
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "gap_before_ms": segment.gap_before_ms,
                    "source": segment.source,
                }
                for segment in self._segments
            ]

            user_content = prompt_template.replace("{{ question }}", question)
            user_content = user_content.replace(
                "{{ segments_json }}",
                json.dumps(segments_payload, ensure_ascii=False, indent=2),
            )
            raw = await self._llm_caller("你是一名语音面试回答切分器。", user_content, True)
            result = parse_json(raw)
            merged = result.get("merged_answer_text", self.get_merged_transcript())
            return SegmentationResult(
                main_segments=result.get("main_answer_segments", []),
                supplement_segments=result.get("supplement_segments", []),
                ignored_segments=result.get("ignored_segments", []),
                merged_text=merged,
                main_answer_text=self._merge_by_indexes(result.get("main_answer_segments", [])),
                supplement_text=self._merge_by_indexes(result.get("supplement_segments", [])),
                reason=result.get("reason", ""),
            )
        except Exception:
            logger.warning("LLM segmentation failed, falling back to rules")
            return self._rule_based_segmentation()

    def _rule_based_segmentation(self) -> SegmentationResult:
        main_ids: list[int] = []
        supplement_ids: list[int] = []
        ignored_ids: list[int] = []

        for segment in self._segments:
            if segment.is_ignored:
                ignored_ids.append(segment.index)
            elif segment.is_supplement:
                supplement_ids.append(segment.index)
            else:
                main_ids.append(segment.index)

        return SegmentationResult(
            main_segments=main_ids,
            supplement_segments=supplement_ids,
            ignored_segments=ignored_ids,
            merged_text=self.get_merged_transcript(),
            main_answer_text=self.get_main_answer_text(),
            supplement_text=self.get_supplement_text(),
            reason="rule_based_segmentation",
        )

    def get_analysis_ready_text(self) -> str:
        return self.get_merged_transcript()

    def get_segment_metadata(self) -> dict:
        return {
            "total_segments": len(self._segments),
            "valid_segments": sum(1 for segment in self._segments if not segment.is_ignored),
            "supplement_segments": sum(
                1 for segment in self._segments if segment.is_supplement and not segment.is_ignored
            ),
            "main_answer_text": self.get_main_answer_text(),
            "supplement_text": self.get_supplement_text(),
            "merged_text": self.get_merged_transcript(),
            "segments": [
                {
                    "index": segment.index,
                    "text": segment.text,
                    "text_length": len(segment.text),
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "duration_ms": max(0, segment.end_ms - segment.start_ms),
                    "gap_before_ms": segment.gap_before_ms,
                    "is_supplement": segment.is_supplement,
                    "is_ignored": segment.is_ignored,
                    "source": segment.source,
                }
                for segment in self._segments
            ],
        }

    def _merge_by_indexes(self, indexes: list[int]) -> str:
        selected = [segment.text for segment in self._segments if segment.index in indexes]
        return " ".join(selected).strip()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join((text or "").strip().split())

    @staticmethod
    def _common_prefix_len(left: str, right: str) -> int:
        limit = min(len(left), len(right))
        idx = 0
        while idx < limit and left[idx] == right[idx]:
            idx += 1
        return idx

    @staticmethod
    def _suffix_overlap_words(committed: str, delta: str) -> int:
        committed_words = committed.split()
        delta_words = delta.split()
        max_overlap = min(4, len(committed_words), len(delta_words))
        for overlap in range(max_overlap, 0, -1):
            if committed_words[-overlap:] == delta_words[:overlap]:
                return overlap
        return 0

    @staticmethod
    def _is_noise(text: str) -> bool:
        cleaned = text.strip().rstrip("。 ， 、 ？ ！ , . ? !")
        return cleaned in _NOISE_PATTERNS or len(cleaned) <= 1
