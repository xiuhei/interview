from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.interview_termination_policy import InterviewTerminationPolicy


def build_policy() -> InterviewTerminationPolicy:
    return InterviewTerminationPolicy(
        min_questions=3,
        max_questions=7,
        early_reject_score=30,
        early_accept_score=75,
        min_questions_for_accept=5,
        low_value_gain_threshold=0.2,
    )


def test_cannot_end_before_minimum_questions():
    decision = build_policy().evaluate(
        answered_main_questions=2,
        rolling_score=12,
        latest_score=10,
        competency_coverage_ratio=0.2,
        evidence_sufficient=False,
        expected_incremental_value=0.05,
        candidate_fit="clearly_not_fit",
        suggested_next_action="switch_dimension",
    )

    assert decision.should_end is False
    assert decision.end_reason == "none"


def test_early_reject_after_minimum_questions():
    decision = build_policy().evaluate(
        answered_main_questions=3,
        rolling_score=24,
        latest_score=20,
        competency_coverage_ratio=0.4,
        evidence_sufficient=False,
        expected_incremental_value=0.1,
        candidate_fit="clearly_not_fit",
        suggested_next_action="switch_dimension",
    )

    assert decision.should_end is True
    assert decision.end_reason == "early_reject"


def test_early_accept_requires_enough_questions():
    decision = build_policy().evaluate(
        answered_main_questions=4,
        rolling_score=86,
        latest_score=88,
        competency_coverage_ratio=0.8,
        evidence_sufficient=True,
        expected_incremental_value=0.1,
        candidate_fit="fit",
        suggested_next_action="switch_dimension",
    )

    assert decision.should_end is False


def test_early_accept_after_sufficient_questions():
    decision = build_policy().evaluate(
        answered_main_questions=5,
        rolling_score=82,
        latest_score=84,
        competency_coverage_ratio=0.8,
        evidence_sufficient=True,
        expected_incremental_value=0.1,
        candidate_fit="fit",
        suggested_next_action="switch_dimension",
    )

    assert decision.should_end is True
    assert decision.end_reason == "early_accept"


def test_hard_stop_at_maximum_questions():
    decision = build_policy().evaluate(
        answered_main_questions=7,
        rolling_score=55,
        latest_score=58,
        competency_coverage_ratio=0.5,
        evidence_sufficient=False,
        expected_incremental_value=0.6,
        candidate_fit="borderline",
        suggested_next_action="follow_up",
    )

    assert decision.should_end is True
    assert decision.end_reason == "completed_max_questions"
