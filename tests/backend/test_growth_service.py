from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.enums import AnswerMode, InterviewStyle
from app.services.growth_service import GrowthService


def build_session(
    created_at: str,
    total_score: float,
    competency_scores: dict,
    weaknesses: list[dict],
    style: InterviewStyle = InterviewStyle.medium,
    answer_mode: AnswerMode = AnswerMode.text,
):
    return SimpleNamespace(
        created_at=SimpleNamespace(strftime=lambda fmt: created_at),
        style=style,
        answer_mode=answer_mode,
        report=SimpleNamespace(
            total_score=total_score,
            competency_scores=competency_scores,
            report_payload={"weaknesses": weaknesses},
        ),
    )


def test_growth_insight_builds_summary_from_completed_sessions_only():
    service = object.__new__(GrowthService)
    service.db = None
    service.interview_repo = SimpleNamespace(
        list_completed_sessions=lambda user_id: [
            build_session(
                "2026-03-22",
                80.0,
                {"system_design": 84.0, "project_depth": 76.0},
                [{"tag": "system_design", "score": 68.0}],
            ),
            build_session(
                "2026-03-20",
                72.0,
                {"system_design": 70.0, "project_depth": 74.0},
                [{"tag": "project_depth", "score": 62.0}],
            ),
        ],
    )
    service.system_repo = None
    service._cleanup_expired_unfinished_sessions = lambda user_id=None: 0

    insight = service.get_growth_insight(7)

    assert insight.summary.completed_sessions == 2
    assert insight.summary.average_score == 76.0
    assert insight.summary.latest_score == 80.0
    assert insight.summary.score_delta == 8.0
    assert insight.summary.strongest_competency == "system_design"
    assert insight.summary.focus_competency == "project_depth"
    assert insight.trends[-1].date == "2026-03-22"
    assert len(insight.plan) >= 1


def test_growth_insight_includes_voice_sessions():
    service = object.__new__(GrowthService)
    service.db = None
    service.interview_repo = SimpleNamespace(
        list_completed_sessions=lambda user_id: [
            build_session(
                "2026-03-22",
                82.0,
                {"system_design": 82.0},
                [],
                style=InterviewStyle.hard,
                answer_mode=AnswerMode.audio,
            ),
            build_session(
                "2026-03-20",
                74.0,
                {"project_depth": 74.0},
                [{"tag": "project_depth", "score": 62.0}],
            ),
        ],
    )
    service.system_repo = None
    service._cleanup_expired_unfinished_sessions = lambda user_id=None: 0

    insight = service.get_growth_insight(7)

    assert insight.summary.completed_sessions == 2
    assert insight.summary.average_score == 78.0
    assert insight.summary.latest_score == 82.0
    assert insight.summary.score_delta == 8.0
    assert insight.trends[0].date == "2026-03-20"
    assert insight.trends[1].date == "2026-03-22"
