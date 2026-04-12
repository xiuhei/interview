from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class InterviewTerminationDecision:
    decision: str
    end_reason: str
    confidence: float
    reason: str
    suggested_next_action: str
    low_value_gain: bool
    information_sufficient: bool
    candidate_fit: str
    rolling_score: float | None
    latest_score: float | None

    @property
    def should_end(self) -> bool:
        return self.decision == "end"


class InterviewTerminationPolicy:
    def __init__(
        self,
        *,
        min_questions: int,
        max_questions: int,
        early_reject_score: float,
        early_accept_score: float,
        min_questions_for_accept: int = 5,
        low_value_gain_threshold: float = 0.2,
    ) -> None:
        self.min_questions = min_questions
        self.max_questions = max_questions
        self.early_reject_score = early_reject_score
        self.early_accept_score = early_accept_score
        self.min_questions_for_accept = max(min_questions_for_accept, min_questions)
        self.low_value_gain_threshold = low_value_gain_threshold

    def evaluate(
        self,
        *,
        answered_main_questions: int,
        rolling_score: float | None,
        latest_score: float | None,
        competency_coverage_ratio: float,
        evidence_sufficient: bool,
        expected_incremental_value: float,
        candidate_fit: str,
        suggested_next_action: str,
    ) -> InterviewTerminationDecision:
        low_value_gain = expected_incremental_value <= self.low_value_gain_threshold
        information_sufficient = evidence_sufficient or competency_coverage_ratio >= 0.7

        if answered_main_questions >= self.max_questions:
            return InterviewTerminationDecision(
                decision="end",
                end_reason="completed_max_questions",
                confidence=1.0,
                reason="已达到本场面试最大题数，必须结束。",
                suggested_next_action="close_interview",
                low_value_gain=True,
                information_sufficient=True,
                candidate_fit=candidate_fit,
                rolling_score=rolling_score,
                latest_score=latest_score,
            )

        if answered_main_questions < self.min_questions:
            return InterviewTerminationDecision(
                decision="continue",
                end_reason="none",
                confidence=0.95,
                reason="主问题数量尚未达到最小样本数，继续提问。",
                suggested_next_action=suggested_next_action,
                low_value_gain=low_value_gain,
                information_sufficient=information_sufficient,
                candidate_fit=candidate_fit,
                rolling_score=rolling_score,
                latest_score=latest_score,
            )

        if (
            rolling_score is not None
            and rolling_score < self.early_reject_score
            and candidate_fit == "clearly_not_fit"
            and low_value_gain
        ):
            return InterviewTerminationDecision(
                decision="end",
                end_reason="early_reject",
                confidence=0.88,
                reason="候选人与岗位明显不匹配，继续提问的增量价值很低。",
                suggested_next_action="close_interview",
                low_value_gain=low_value_gain,
                information_sufficient=information_sufficient,
                candidate_fit=candidate_fit,
                rolling_score=rolling_score,
                latest_score=latest_score,
            )

        if (
            answered_main_questions >= self.min_questions_for_accept
            and rolling_score is not None
            and rolling_score >= self.early_accept_score
            and candidate_fit == "fit"
            and information_sufficient
            and low_value_gain
        ):
            return InterviewTerminationDecision(
                decision="end",
                end_reason="early_accept",
                confidence=0.84,
                reason="候选人已经达到目标要求，当前信息足以支撑判断。",
                suggested_next_action="close_interview",
                low_value_gain=low_value_gain,
                information_sufficient=information_sufficient,
                candidate_fit=candidate_fit,
                rolling_score=rolling_score,
                latest_score=latest_score,
            )

        return InterviewTerminationDecision(
            decision="continue",
            end_reason="none",
            confidence=0.72,
            reason="当前样本仍有继续提问的价值，继续推进面试。",
            suggested_next_action=suggested_next_action,
            low_value_gain=low_value_gain,
            information_sufficient=information_sufficient,
            candidate_fit=candidate_fit,
            rolling_score=rolling_score,
            latest_score=latest_score,
        )
