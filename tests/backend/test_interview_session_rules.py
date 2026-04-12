from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.models.enums import AnalysisJobStatus, AnswerMode, FollowUpType, InterviewStatus, InterviewStyle, QuestionCategory
from app.schemas.interview import InterviewCreateRequest, SubmitAnswerRequest
from app.services.interview_service import InterviewService, run_history_report_task


class DummyDB:
    def __init__(self) -> None:
        self.commits = 0
        self.refreshed = []

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None

    def refresh(self, session) -> None:
        self.refreshed.append(session)


class ActiveRepo:
    def find_active_session(self, user_id: int):
        _ = user_id
        return SimpleNamespace(id=11)

    def cleanup_expired_unfinished_sessions(self, expires_before, user_id=None):
        _ = expires_before, user_id
        return 0


class CompletedOnlyRepo:
    def cleanup_expired_unfinished_sessions(self, expires_before, user_id=None):
        _ = expires_before, user_id
        return 0

    def list_completed_sessions(self, user_id: int):
        _ = user_id
        return [
            SimpleNamespace(
                id=1,
                title="CPP Backend interview",
                position=SimpleNamespace(name="CPP Backend"),
                style=InterviewStyle.medium,
                answer_mode=AnswerMode.text,
                status="completed",
                report=SimpleNamespace(total_score=84.0, created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc)),
                created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
                completed_at=None,
            )
        ]


class ActiveSessionSummaryRepo:
    def cleanup_expired_unfinished_sessions(self, expires_before, user_id=None):
        _ = expires_before, user_id
        return 0

    def find_active_session(self, user_id: int):
        _ = user_id
        return SimpleNamespace(
            id=18,
            title="CPP Backend / Regular interview",
            position=SimpleNamespace(name="CPP Backend"),
            style=InterviewStyle.medium,
            answer_mode=AnswerMode.text,
            status=InterviewStatus.technical_question,
            max_questions=6,
            current_turn=2,
            created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
        )


class DiscardRepo:
    def cleanup_expired_unfinished_sessions(self, expires_before, user_id=None):
        _ = expires_before, user_id
        return 0

    def get_session(self, session_id: int):
        return SimpleNamespace(
            id=session_id,
            user_id=7,
            status=InterviewStatus.technical_question,
        )

    def delete_unfinished_session(self, session_id: int, user_id=None):
        _ = user_id
        return 1 if session_id == 12 else 0


class DeleteHistoryRepo:
    def cleanup_expired_unfinished_sessions(self, expires_before, user_id=None):
        _ = expires_before, user_id
        return 0

    def get_session(self, session_id: int):
        return SimpleNamespace(
            id=session_id,
            user_id=7,
            status=InterviewStatus.completed,
            style=InterviewStyle.medium,
        )

    def delete_completed_session(self, session_id: int, user_id=None):
        _ = user_id
        return 1 if session_id == 21 else 0


def test_create_session_blocks_when_user_has_active_interview():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.settings = SimpleNamespace(immersive_voice_interview_ready=True)
    service.repo = ActiveRepo()
    service.position_repo = SimpleNamespace(get_by_code=lambda code: SimpleNamespace(id=2, code=code, name="CPP Backend"))
    service.resume_repo = SimpleNamespace(get=lambda resume_id: None)

    try:
        service.create_session(
            7,
            InterviewCreateRequest(position_code="cpp_backend", style=InterviewStyle.medium, answer_mode="text"),
        )
    except AppException as exc:
        assert exc.status_code == 409
        assert exc.message
    else:
        raise AssertionError("expected AppException")


def test_list_history_uses_completed_sessions_only():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = CompletedOnlyRepo()

    history = service.list_history(7)

    assert len(history) == 1
    assert history[0].session_id == 1
    assert history[0].total_score == 84.0
    assert history[0].report_ready is True
    assert history[0].completed_at.isoformat() == "2026-03-23T01:00:00+00:00"


def test_cleanup_expired_sessions_commits_when_sessions_are_deleted():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = SimpleNamespace(
        cleanup_expired_unfinished_sessions=lambda expires_before, user_id=None: 2,
    )

    deleted = service._cleanup_expired_sessions(user_id=7)

    assert deleted == 2
    assert service.db.commits == 1


def test_get_active_session_returns_unfinished_session_summary():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = ActiveSessionSummaryRepo()

    active = service.get_active_session(7)

    assert active is not None
    assert active.id == 18
    assert active.position == "CPP Backend"
    assert active.status == InterviewStatus.technical_question
    assert active.expires_at.isoformat() == "2026-03-25T00:00:00+00:00"


def test_discard_session_deletes_unfinished_session():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = DiscardRepo()

    result = service.discard_session(7, 12)

    assert result.session_id == 12
    assert service.db.commits == 1


def test_delete_history_deletes_completed_session():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = DeleteHistoryRepo()

    result = service.delete_history(7, 21)

    assert result.session_id == 21
    assert service.db.commits == 1


def test_delete_history_rejects_missing_session():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = DeleteHistoryRepo()

    try:
        service.delete_history(7, 22)
    except AppException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected AppException")


def test_get_history_detail_returns_full_archive():
    question = SimpleNamespace(
        id=101,
        turn_no=1,
        category=QuestionCategory.technical,
        competency_code="system_design",
        question_text="Please describe how you would design a high-concurrency API.",
        follow_up_reason="",
        follow_up_type=FollowUpType.none,
    )
    answer = SimpleNamespace(
        id=201,
        question_id=101,
        turn_no=1,
        answer_mode=AnswerMode.audio,
        answer_text="I would analyze the bottleneck first, then use cache and rate limiting to handle traffic.",
        audio_path="var/uploads/audio/example-answer.webm",
        asr_text="",
        created_at=datetime(2026, 3, 23, 0, 15, tzinfo=timezone.utc),
        audio_features=SimpleNamespace(
            status="available",
            volume_stability=0.82,
            pause_ratio=0.11,
            speech_rate=3.2,
            pitch_variation=0.44,
            voiced_ratio=0.91,
        ),
        score=SimpleNamespace(
            overall_score=88.0,
            text_scores={"accuracy": 90.0, "completeness": 86.0},
            audio_scores={"clarity": 84.0, "stability": 80.0},
            explanation="The answer is well structured and reasonably credible.",
            suggestions=["Add more quantified results."],
            evidence=[],
            debug_payload={},
        ),
    )
    session = SimpleNamespace(
        id=1,
        user_id=7,
        title="CPP Backend interview",
        position=SimpleNamespace(name="CPP Backend"),
        style=InterviewStyle.medium,
        answer_mode=AnswerMode.text,
        status=InterviewStatus.completed,
        created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 23, 0, 30, tzinfo=timezone.utc),
        questions=[question],
        answers=[answer],
        report=SimpleNamespace(
            total_score=86.5,
            report_level="Strong",
            competency_scores={"system_design": 86.5},
            created_at=datetime(2026, 3, 23, 0, 30, tzinfo=timezone.utc),
            report_payload={
                "radar": [{"name": "system_design", "value": 86.5}],
                "suggestions": [
                    {
                        "issue": "system_design needs improvement",
                        "reason": "Needs more concrete capacity planning details.",
                        "improvement": "Add cache and degradation strategy details.",
                        "practice_direction": "Keep practicing system design questions.",
                    }
                ],
                "qa_records": [],
                "next_training_plan": ["Keep practicing system design questions."],
                "summary": "Overall performance is solid.",
            },
        ),
    )
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = SimpleNamespace(
        get_session=lambda session_id: session if session_id == 1 else None,
        cleanup_expired_unfinished_sessions=lambda expires_before, user_id=None: 0,
    )
    service._history_audio_duration_seconds = lambda current_answer: 4.2 if current_answer is answer else None
    service._refresh_history_audio_analysis = lambda current_session: False

    archive = service.get_history_detail(7, 1)

    assert archive.title == "CPP Backend interview"
    assert archive.completed_at.isoformat() == "2026-03-23T00:30:00+00:00"
    assert archive.total_score == 86.5
    assert archive.questions[0].question_text == "Please describe how you would design a high-concurrency API."
    assert archive.questions[0].answer_text == "I would analyze the bottleneck first, then use cache and rate limiting to handle traffic."
    assert archive.questions[0].audio_path == "/uploads/audio/example-answer.webm"
    assert archive.questions[0].answered_at.isoformat() == "2026-03-23T00:15:00+00:00"
    assert archive.questions[0].evaluation_ready is True
    assert archive.questions[0].text_scores["accuracy"] == 90.0
    assert archive.questions[0].audio_scores["clarity"] == 84.0
    assert archive.questions[0].audio_features.status == "available"
    assert archive.questions[0].audio_duration_seconds == 4.2


def test_get_history_detail_hides_audio_scores_for_text_answers():
    question = SimpleNamespace(
        id=102,
        turn_no=1,
        category=QuestionCategory.technical,
        competency_code="project_depth",
        question_text="Please introduce one project you worked on.",
        follow_up_reason="",
        follow_up_type=FollowUpType.none,
    )
    answer = SimpleNamespace(
        id=202,
        question_id=102,
        turn_no=1,
        answer_mode=AnswerMode.text,
        answer_text="I owned the core module design.",
        audio_path="",
        asr_text="",
        created_at=datetime(2026, 3, 23, 0, 10, tzinfo=timezone.utc),
        audio_features=SimpleNamespace(status="unavailable"),
        score=SimpleNamespace(
            overall_score=75.0,
            text_scores={"accuracy": 82.0},
            audio_scores={"status": "unavailable", "clarity": None},
            explanation="The text answer is acceptable.",
            suggestions=[],
            evidence=[],
            debug_payload={},
        ),
    )
    session = SimpleNamespace(
        id=2,
        user_id=7,
        title="CPP Backend interview",
        position=SimpleNamespace(name="CPP Backend"),
        style=InterviewStyle.medium,
        answer_mode=AnswerMode.text,
        status=InterviewStatus.completed,
        created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 23, 0, 20, tzinfo=timezone.utc),
        questions=[question],
        answers=[answer],
        report=SimpleNamespace(
            total_score=75.0,
            report_level="Passing",
            competency_scores={"project_depth": 75.0},
            created_at=datetime(2026, 3, 23, 0, 20, tzinfo=timezone.utc),
            report_payload={
                "radar": [],
                "suggestions": [],
                "qa_records": [],
                "next_training_plan": [],
                "summary": "ok",
            },
        ),
    )
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = SimpleNamespace(
        get_session=lambda session_id: session if session_id == 2 else None,
        cleanup_expired_unfinished_sessions=lambda expires_before, user_id=None: 0,
    )
    service._refresh_history_audio_analysis = lambda current_session: False

    archive = service.get_history_detail(7, 2)

    assert archive.questions[0].audio_scores == {}
    assert archive.questions[0].audio_features is None
    assert archive.questions[0].evaluation_ready is True


def test_get_history_detail_recovers_unavailable_audio_scores_for_audio_answers():
    question = SimpleNamespace(
        id=103,
        turn_no=1,
        category=QuestionCategory.technical,
        competency_code="system_design",
        question_text="Describe the traffic control strategy for a gateway service.",
        follow_up_reason="",
        follow_up_type=FollowUpType.none,
    )
    answer = SimpleNamespace(
        id=203,
        question_id=103,
        turn_no=1,
        answer_mode=AnswerMode.audio,
        answer_text="I would combine rate limiting and degradation policies.",
        audio_path="uploads/audio/recoverable.webm",
        asr_text="I would combine rate limiting and degradation policies.",
        created_at=datetime(2026, 3, 23, 0, 10, tzinfo=timezone.utc),
        audio_features=SimpleNamespace(status="unavailable"),
        score=SimpleNamespace(
            overall_score=75.0,
            text_scores={"accuracy": 82.0},
            audio_scores={"status": "unavailable", "clarity": None},
            explanation="The answer is acceptable.",
            suggestions=[],
            evidence=[],
            debug_payload={},
        ),
    )
    session = SimpleNamespace(
        id=3,
        user_id=7,
        title="CPP Backend interview",
        position=SimpleNamespace(name="CPP Backend"),
        style=InterviewStyle.medium,
        answer_mode=AnswerMode.audio,
        status=InterviewStatus.completed,
        created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 23, 0, 20, tzinfo=timezone.utc),
        questions=[question],
        answers=[answer],
        report=SimpleNamespace(
            total_score=75.0,
            report_level="Passing",
            competency_scores={"system_design": 75.0},
            created_at=datetime(2026, 3, 23, 0, 20, tzinfo=timezone.utc),
            report_payload={
                "radar": [],
                "suggestions": [],
                "qa_records": [],
                "next_training_plan": [],
                "summary": "ok",
            },
        ),
    )
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = SimpleNamespace(
        get_session=lambda session_id: session if session_id == 3 else None,
        cleanup_expired_unfinished_sessions=lambda expires_before, user_id=None: 0,
    )

    def fake_refresh(current_session):
        assert current_session is session
        answer.score.audio_scores = {"status": "available", "clarity": 88.0, "confidence": 85.0}
        answer.audio_features = SimpleNamespace(
            status="available",
            volume_stability=81.0,
            pause_ratio=14.0,
            speech_rate=3.3,
            pitch_variation=21.0,
            voiced_ratio=86.0,
        )
        answer.score.overall_score = 79.0
        return True

    service._refresh_history_audio_analysis = fake_refresh

    archive = service.get_history_detail(7, 3)

    assert archive.questions[0].audio_scores["clarity"] == 88.0
    assert archive.questions[0].audio_features.status == "available"
    assert archive.questions[0].overall_score == 79.0


def test_should_recover_audio_evaluation_for_legacy_audio_signature():
    answer = SimpleNamespace(
        id=301,
        answer_mode=AnswerMode.audio,
        score=SimpleNamespace(audio_scores={"status": "available", "fluency": 88.0}),
        audio_features=SimpleNamespace(
            status="available",
            pause_ratio=25.1,
            speech_rate=25.4,
            voiced_ratio=74.9,
        ),
        audio_path="uploads/audio/legacy.webm",
    )
    service = object.__new__(InterviewService)
    service._resolve_answer_audio_path = lambda current_answer: Path("legacy.webm") if current_answer is answer else None

    assert service._should_recover_audio_evaluation(answer) is True


def test_get_history_detail_rejects_unfinished_session():
    session = SimpleNamespace(
        id=1,
        user_id=7,
        status=InterviewStatus.technical_question,
    )
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = SimpleNamespace(
        get_session=lambda session_id: session if session_id == 1 else None,
        cleanup_expired_unfinished_sessions=lambda expires_before, user_id=None: 0,
    )

    try:
        service.get_history_detail(7, 1)
    except AppException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected AppException")


def test_run_history_report_task_rebuilds_missing_report_for_completed_session():
    question = SimpleNamespace(
        id=103,
        turn_no=1,
        category=QuestionCategory.technical,
        competency_code="project_depth",
        question_text="Tell me about a difficult project tradeoff.",
        follow_up_reason="",
        follow_up_type=FollowUpType.none,
    )
    answer = SimpleNamespace(
        id=203,
        question_id=103,
        turn_no=1,
        answer_mode=AnswerMode.audio,
        answer_text="I compared latency and complexity before choosing the simpler方案。",
        audio_path="audio/example-recovery.webm",
        asr_text="I compared latency and complexity before choosing the simpler solution.",
        created_at=datetime(2026, 3, 23, 0, 12, tzinfo=timezone.utc),
        audio_features=SimpleNamespace(
            status="available",
            volume_stability=0.8,
            pause_ratio=0.1,
            speech_rate=3.0,
            pitch_variation=0.35,
            voiced_ratio=0.9,
        ),
        score=SimpleNamespace(
            overall_score=82.0,
            text_scores={"accuracy": 82.0},
            audio_scores={"clarity": 81.0},
            explanation="Good answer.",
            suggestions=["Add one concrete metric."],
            evidence=[],
            debug_payload={},
        ),
    )
    session = SimpleNamespace(
        id=9,
        user_id=7,
        title="Recovered interview",
        position=SimpleNamespace(name="CPP Backend"),
        style=InterviewStyle.hard,
        answer_mode=AnswerMode.audio,
        status=InterviewStatus.completed,
        created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 23, 0, 30, tzinfo=timezone.utc),
        questions=[question],
        answers=[answer],
        report=None,
    )
    job = SimpleNamespace(
        id=91,
        session_id=9,
        session=session,
        retry_count=0,
        max_retries=5,
        status=AnalysisJobStatus.pending,
        current_stage="queued",
        stage_payload={},
    )
    rebuilt_report = SimpleNamespace(
        total_score=82.0,
        report_level="Strong",
        competency_scores={"project_depth": 82.0},
        created_at=datetime(2026, 3, 23, 0, 31, tzinfo=timezone.utc),
        report_payload={
            "radar": [],
            "suggestions": [],
            "qa_records": [],
            "next_training_plan": [],
            "summary": "Recovered summary.",
            "voice_scores": {"speech_clarity": 81.0},
        },
    )

    original_session_local = run_history_report_task.__globals__["SessionLocal"]
    original_interview_service = run_history_report_task.__globals__["InterviewService"]

    class FakeSessionLocal:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    fake_service = object.__new__(InterviewService)
    fake_repo = SimpleNamespace(
        claim_analysis_job=lambda job_id, worker_id, now, heartbeat_timeout_before: job if job_id == 91 else None,
        heartbeat_analysis_job=lambda current_job, now, stage=None, payload=None: (
            setattr(current_job, "current_stage", stage or current_job.current_stage),
            setattr(current_job, "stage_payload", payload if payload is not None else current_job.stage_payload),
            current_job,
        )[-1],
        get_analysis_job=lambda job_id: job if job_id == 91 else None,
        mark_analysis_job_success=lambda current_job, now, payload=None: (
            setattr(current_job, "status", AnalysisJobStatus.success),
            setattr(current_job, "stage_payload", payload if payload is not None else current_job.stage_payload),
            current_job,
        )[-1],
        mark_analysis_job_failed=lambda current_job, now, error_reason, next_retry_at: (
            setattr(current_job, "status", AnalysisJobStatus.dead if next_retry_at is None else AnalysisJobStatus.failed),
            current_job,
        )[-1],
    )
    fake_service.repo = fake_repo
    fake_service._get_session = lambda session_id: session if session_id == 9 else None
    fake_service._is_report_ready = lambda current_session: current_session.report is not None
    fake_service._ensure_session_scores = lambda current_session: None
    fake_service._analysis_retry_at = lambda retry_count, now: None

    def build_report(current_session):
        current_session.report = rebuilt_report
        return rebuilt_report

    fake_service._build_report = build_report

    try:
        run_history_report_task.__globals__["SessionLocal"] = lambda: FakeSessionLocal()
        run_history_report_task.__globals__["InterviewService"] = lambda db: fake_service
        run_history_report_task(91)
    finally:
        run_history_report_task.__globals__["SessionLocal"] = original_session_local
        run_history_report_task.__globals__["InterviewService"] = original_interview_service

    assert session.report is rebuilt_report
    assert job.status == AnalysisJobStatus.success


def test_get_history_detail_returns_pending_archive_without_triggering_analysis():
    question = SimpleNamespace(
        id=104,
        turn_no=1,
        category=QuestionCategory.technical,
        competency_code="project_depth",
        question_text="Describe one system design tradeoff.",
        follow_up_reason="",
        follow_up_type=FollowUpType.none,
    )
    answer = SimpleNamespace(
        id=204,
        question_id=104,
        turn_no=1,
        answer_mode=AnswerMode.audio,
        answer_text="",
        audio_path="audio/background-task.webm",
        asr_text="The answer is still being transcribed.",
        created_at=datetime(2026, 3, 23, 0, 12, tzinfo=timezone.utc),
        audio_features=None,
        score=None,
    )
    session = SimpleNamespace(
        id=10,
        user_id=7,
        title="Pending report interview",
        position=SimpleNamespace(name="CPP Backend"),
        style=InterviewStyle.hard,
        answer_mode=AnswerMode.audio,
        status=InterviewStatus.completed,
        created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 23, 0, 30, tzinfo=timezone.utc),
        questions=[question],
        answers=[answer],
        report=None,
        analysis_jobs=[
            SimpleNamespace(
                id=1010,
                status=AnalysisJobStatus.pending,
                current_stage="queued",
            )
        ],
    )
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = SimpleNamespace(
        get_session=lambda session_id: session if session_id == 10 else None,
        cleanup_expired_unfinished_sessions=lambda expires_before, user_id=None: 0,
    )

    archive = service.get_history_detail(7, 10)

    assert archive.report_ready is False
    assert archive.report_level
    assert archive.questions[0].evaluation_ready is False
    assert archive.questions[0].audio_path == "/uploads/audio/background-task.webm"


def test_process_pending_history_reports_marks_pending_and_runs_task():
    InterviewService.process_pending_history_reports.__globals__["REPORT_REBUILDING_SESSIONS"].clear()
    session = SimpleNamespace(
        id=11,
        user_id=7,
        title="Retry interview",
        position=SimpleNamespace(name="CPP Backend"),
        style=InterviewStyle.hard,
        answer_mode=AnswerMode.audio,
        status=InterviewStatus.completed,
        created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 23, 0, 30, tzinfo=timezone.utc),
        questions=[],
        answers=[],
        report=None,
    )
    job = SimpleNamespace(id=111, session=session)
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    schedule_calls = []
    task_calls = []

    service.repo = SimpleNamespace(
        list_sessions_needing_report=lambda limit=10: [session],
        list_due_analysis_jobs=lambda now, heartbeat_timeout_before, limit=10: [job],
    )
    service._is_report_ready = lambda current_session: False
    service._schedule_history_report = lambda current_session: schedule_calls.append(current_session.id)

    original_task = InterviewService.process_pending_history_reports.__globals__["run_history_report_task"]

    def fake_task(job_id):
        task_calls.append(job_id)
        InterviewService.process_pending_history_reports.__globals__["REPORT_REBUILDING_SESSIONS"].discard(job_id)

    try:
        InterviewService.process_pending_history_reports.__globals__["run_history_report_task"] = fake_task
        processed = service.process_pending_history_reports(limit=3)
    finally:
        InterviewService.process_pending_history_reports.__globals__["run_history_report_task"] = original_task

    assert schedule_calls == [11]
    assert task_calls == [111]
    assert processed == 1
    InterviewService.process_pending_history_reports.__globals__["REPORT_REBUILDING_SESSIONS"].clear()


def test_finalize_session_sets_completed_at():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service._build_report = lambda current_session: SimpleNamespace(total_score=90.0, report_level="Strong")
    session = SimpleNamespace(
        id=3,
        user_id=7,
        status=InterviewStatus.summary,
        completed_at=None,
    )

    report = service._finalize_session(session)

    assert report.total_score == 90.0
    assert session.status == InterviewStatus.completed
    assert session.completed_at is not None
    assert service.db.commits == 1


def test_submit_answer_reuses_existing_answer_when_question_already_answered():
    current_question = SimpleNamespace(
        id=301,
        session_id=9,
        turn_no=1,
        category=QuestionCategory.technical,
        competency_code="system_design",
        question_text="Design a high-concurrency API.",
        follow_up_reason="",
        follow_up_type=FollowUpType.none,
        evidence_summary="",
    )
    next_question = SimpleNamespace(
        id=302,
        session_id=9,
        turn_no=2,
        category=QuestionCategory.follow_up,
        competency_code="system_design",
        question_text="Go deeper into the cache invalidation strategy.",
        follow_up_reason="Need more detail",
        follow_up_type=FollowUpType.deepen,
        evidence_summary="",
    )
    existing_answer = SimpleNamespace(
        id=401,
        question_id=301,
        turn_no=1,
        answer_mode=AnswerMode.text,
        audio_features=None,
        score=SimpleNamespace(
            competency_code="system_design",
            overall_score=82.5,
            text_scores={"accuracy": 84.0},
            audio_scores={},
            explanation="Existing answer already scored.",
            suggestions=["Add trade-off details."],
            evidence=[],
            debug_payload={},
        ),
    )
    session = SimpleNamespace(
        id=9,
        style=InterviewStyle.medium,
        status=InterviewStatus.deep_follow_up,
        current_turn=1,
        max_questions=6,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        questions=[current_question, next_question],
        answers=[existing_answer],
        report=None,
    )

    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = SimpleNamespace(get_question=lambda question_id: current_question if question_id == 301 else None)
    service.settings = SimpleNamespace(upload_dir=Path('var/uploads'))
    service.speech_service = SimpleNamespace(transcribe=lambda _: "")
    service._cleanup_expired_sessions = lambda user_id=None: 0
    service._get_session = lambda session_id: session

    response = service.submit_answer(
        9,
        SubmitAnswerRequest(question_id=301, answer_mode=AnswerMode.text, text_answer="duplicate"),
    )

    assert response.answer_id == 401
    assert response.evaluation is not None
    assert response.evaluation.answer_id == 401
    assert response.evaluation_ready is True
    assert response.next_action == "awaiting_next_question"
    assert response.next_question_id is None
    assert response.report_ready is False


def test_submit_answer_replaces_pending_audio_answer_when_retrying_recording(tmp_path):
    upload_dir = tmp_path / "uploads"
    audio_dir = upload_dir / "audio"
    audio_dir.mkdir(parents=True)
    replacement_file = audio_dir / "retry-answer.webm"
    replacement_file.write_bytes(b"audio")

    current_question = SimpleNamespace(
        id=311,
        session_id=10,
        turn_no=1,
        category=QuestionCategory.technical,
        competency_code="system_design",
        question_text="Design a high-concurrency API.",
        follow_up_reason="",
        follow_up_type=FollowUpType.none,
        evidence_summary="",
    )
    existing_answer = SimpleNamespace(
        id=411,
        question_id=311,
        turn_no=1,
        answer_mode=AnswerMode.audio,
        answer_text="",
        asr_text="",
        audio_path="audio/old-answer.webm",
        audio_features=None,
        score=None,
    )
    session = SimpleNamespace(
        id=10,
        style=InterviewStyle.medium,
        status=InterviewStatus.technical_question,
        current_turn=1,
        max_questions=6,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        questions=[current_question],
        answers=[existing_answer],
        report=None,
    )

    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = SimpleNamespace(get_question=lambda question_id: current_question if question_id == 311 else None)
    service.settings = SimpleNamespace(upload_dir=upload_dir)
    service.speech_service = SimpleNamespace(transcribe=lambda _: "")
    service._cleanup_expired_sessions = lambda user_id=None: 0
    service._get_session = lambda session_id: session

    response = service.submit_answer(
        10,
        SubmitAnswerRequest(
            question_id=311,
            answer_mode=AnswerMode.audio,
            text_answer="",
            audio_file_id="retry-answer.webm",
        ),
    )

    assert response.answer_id == 411
    assert response.evaluation_ready is False
    assert response.next_action == "awaiting_next_question"
    assert existing_answer.audio_path.replace("\\", "/").endswith("audio/retry-answer.webm")
    assert service.db.commits == 1


def test_submit_answer_returns_existing_result_after_integrity_conflict():
    current_question = SimpleNamespace(
        id=501,
        session_id=12,
        turn_no=1,
        category=QuestionCategory.technical,
        competency_code="project_depth",
        question_text="Describe a project you truly owned.",
        follow_up_reason="",
        follow_up_type=FollowUpType.none,
        evidence_summary="",
    )
    next_question = SimpleNamespace(
        id=502,
        session_id=12,
        turn_no=2,
        category=QuestionCategory.follow_up,
        competency_code="project_depth",
        question_text="What metrics prove the impact?",
        follow_up_reason="Need quantified result",
        follow_up_type=FollowUpType.credibility,
        evidence_summary="",
    )
    persisted_answer = SimpleNamespace(
        id=601,
        question_id=501,
        turn_no=1,
        answer_mode=AnswerMode.text,
        audio_features=None,
        score=SimpleNamespace(
            competency_code="project_depth",
            overall_score=79.0,
            text_scores={"credibility": 78.0},
            audio_scores={},
            explanation="Persisted answer reused after conflict.",
            suggestions=["Clarify personal ownership."],
            evidence=[],
            debug_payload={},
        ),
    )
    initial_session = SimpleNamespace(
        id=12,
        style=InterviewStyle.medium,
        status=InterviewStatus.technical_question,
        current_turn=1,
        max_questions=6,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        questions=[current_question, next_question],
        answers=[],
        report=None,
    )
    refreshed_session = SimpleNamespace(
        id=12,
        style=InterviewStyle.medium,
        status=InterviewStatus.deep_follow_up,
        current_turn=1,
        max_questions=6,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        questions=[current_question, next_question],
        answers=[persisted_answer],
        report=None,
    )
    sessions = [initial_session, refreshed_session]

    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.settings = SimpleNamespace(upload_dir=Path('var/uploads'))
    service.speech_service = SimpleNamespace(transcribe=lambda _: "")
    service.retrieval_service = SimpleNamespace(retrieve_with_meta=lambda query, role_code: SimpleNamespace(evidence=[], backend="milvus"))
    service.scoring_service = SimpleNamespace(
        score_answer=lambda **kwargs: (
            {
                "competency_code": "project_depth",
                "overall_score": 79.0,
                "text_scores": {"credibility": 78.0},
                "audio_scores": {},
                "explanation": "fresh",
                "suggestions": [],
            },
            {
                "status": "unavailable",
                "volume_stability": None,
                "pause_ratio": None,
                "speech_rate": None,
                "pitch_variation": None,
                "voiced_ratio": None,
            },
            {},
        )
    )
    service._cleanup_expired_sessions = lambda user_id=None: 0
    service._get_session = lambda session_id: sessions.pop(0)
    service.repo = SimpleNamespace(
        get_question=lambda question_id: current_question if question_id == 501 else None,
        create_answer=lambda **kwargs: (_ for _ in ()).throw(IntegrityError("insert", {}, Exception("dup"))),
    )

    response = service.submit_answer(
        12,
        SubmitAnswerRequest(question_id=501, answer_mode=AnswerMode.text, text_answer="duplicate race"),
    )

    assert response.answer_id == 601
    assert response.evaluation is not None
    assert response.evaluation.answer_id == 601
    assert response.evaluation_ready is True
    assert response.next_action == "awaiting_next_question"
    assert response.next_question_id is None



class MixedCompletedRepo:
    def cleanup_expired_unfinished_sessions(self, expires_before, user_id=None):
        _ = expires_before, user_id
        return 0

    def list_completed_sessions(self, user_id: int):
        _ = user_id
        return [
            SimpleNamespace(
                id=1,
                title="Regular interview",
                position=SimpleNamespace(name="CPP Backend"),
        style=InterviewStyle.medium,
                status=InterviewStatus.completed,
                report=SimpleNamespace(total_score=84.0, created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc)),
                created_at=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
                completed_at=None,
            ),
            SimpleNamespace(
                id=2,
                title="Pressure interview",
                position=SimpleNamespace(name="CPP Backend"),
        style=InterviewStyle.hard,
                status=InterviewStatus.completed,
                report=SimpleNamespace(total_score=88.0, created_at=datetime(2026, 3, 23, 2, 0, tzinfo=timezone.utc)),
                created_at=datetime(2026, 3, 23, 1, 0, tzinfo=timezone.utc),
                completed_at=None,
            ),
        ]


def test_list_history_includes_pressure_voice_sessions():
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = MixedCompletedRepo()

    history = service.list_history(7)

    assert [item.session_id for item in history] == [1, 2]
