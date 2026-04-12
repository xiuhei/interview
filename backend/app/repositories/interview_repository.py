from datetime import datetime

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    AnalysisJob,
    AnswerAudioFeature,
    AnswerScore,
    InterviewAnswer,
    InterviewQuestion,
    InterviewReport,
    InterviewSession,
    JobPosition,
    Resume,
)
from app.models.enums import AnalysisJobStatus, InterviewStatus


class InterviewRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, **kwargs) -> InterviewSession:
        session = InterviewSession(**kwargs)
        self.db.add(session)
        self.db.flush()
        return session

    def get_session(self, session_id: int) -> InterviewSession | None:
        stmt = (
            select(InterviewSession)
            .options(
                joinedload(InterviewSession.position).selectinload(JobPosition.competencies),
                joinedload(InterviewSession.resume).joinedload(Resume.parse),
                selectinload(InterviewSession.questions),
                selectinload(InterviewSession.answers).joinedload(InterviewAnswer.score),
                selectinload(InterviewSession.answers).joinedload(InterviewAnswer.audio_features),
                selectinload(InterviewSession.answers).joinedload(InterviewAnswer.question),
                joinedload(InterviewSession.report),
            )
            .where(InterviewSession.id == session_id)
        )
        return self.db.scalar(stmt)

    def list_sessions(self, user_id: int) -> list[InterviewSession]:
        stmt = (
            select(InterviewSession)
            .options(joinedload(InterviewSession.position), joinedload(InterviewSession.report))
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique())

    def list_completed_sessions(self, user_id: int) -> list[InterviewSession]:
        stmt = (
            select(InterviewSession)
            .options(joinedload(InterviewSession.position), joinedload(InterviewSession.report))
            .where(
                InterviewSession.user_id == user_id,
                InterviewSession.status == InterviewStatus.completed,
            )
            .order_by(InterviewSession.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique())

    def list_sessions_needing_report(self, limit: int = 10) -> list[InterviewSession]:
        stmt = (
            select(InterviewSession)
            .outerjoin(InterviewReport, InterviewReport.session_id == InterviewSession.id)
            .options(
                joinedload(InterviewSession.position).selectinload(JobPosition.competencies),
                joinedload(InterviewSession.resume).joinedload(Resume.parse),
                selectinload(InterviewSession.questions),
                selectinload(InterviewSession.answers).joinedload(InterviewAnswer.score),
                selectinload(InterviewSession.answers).joinedload(InterviewAnswer.audio_features),
                selectinload(InterviewSession.answers).joinedload(InterviewAnswer.question),
                joinedload(InterviewSession.report),
            )
            .where(
                InterviewSession.status == InterviewStatus.completed,
                or_(
                    InterviewReport.id.is_(None),
                    InterviewReport.report_level == "分析中",
                ),
            )
            .order_by(InterviewSession.completed_at.asc(), InterviewSession.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique())

    def get_latest_analysis_job(self, session_id: int) -> AnalysisJob | None:
        stmt = (
            select(AnalysisJob)
            .where(AnalysisJob.session_id == session_id)
            .order_by(AnalysisJob.version.desc(), AnalysisJob.id.desc())
        )
        return self.db.scalar(stmt)

    def get_analysis_job(self, job_id: int) -> AnalysisJob | None:
        return self.db.scalar(
            select(AnalysisJob)
            .options(
                joinedload(AnalysisJob.session).joinedload(InterviewSession.position).selectinload(JobPosition.competencies),
                joinedload(AnalysisJob.session).joinedload(InterviewSession.resume).joinedload(Resume.parse),
                joinedload(AnalysisJob.session).selectinload(InterviewSession.questions),
                joinedload(AnalysisJob.session).selectinload(InterviewSession.answers).joinedload(InterviewAnswer.score),
                joinedload(AnalysisJob.session).selectinload(InterviewSession.answers).joinedload(InterviewAnswer.audio_features),
                joinedload(AnalysisJob.session).selectinload(InterviewSession.answers).joinedload(InterviewAnswer.question),
                joinedload(AnalysisJob.session).joinedload(InterviewSession.report),
            )
            .where(AnalysisJob.id == job_id)
        )

    def create_analysis_job(self, **kwargs) -> AnalysisJob:
        job = AnalysisJob(**kwargs)
        self.db.add(job)
        self.db.flush()
        return job

    def claim_analysis_job(
        self,
        job_id: int,
        worker_id: str,
        now: datetime,
        heartbeat_timeout_before: datetime,
    ) -> AnalysisJob | None:
        stmt = (
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                or_(
                    AnalysisJob.status == AnalysisJobStatus.pending,
                    and_(
                        AnalysisJob.status == AnalysisJobStatus.failed,
                        AnalysisJob.next_retry_at.is_not(None),
                        AnalysisJob.next_retry_at <= now,
                    ),
                    and_(
                        AnalysisJob.status == AnalysisJobStatus.processing,
                        or_(
                            AnalysisJob.heartbeat_at.is_(None),
                            AnalysisJob.heartbeat_at <= heartbeat_timeout_before,
                        ),
                    ),
                ),
            )
            .values(
                status=AnalysisJobStatus.processing,
                locked_by=worker_id,
                locked_at=now,
                heartbeat_at=now,
                next_retry_at=None,
                error_reason="",
            )
        )
        result = self.db.execute(stmt)
        if not result.rowcount:
            return None
        self.db.flush()
        return self.get_analysis_job(job_id)

    def heartbeat_analysis_job(self, job: AnalysisJob, now: datetime, stage: str | None = None, payload: dict | None = None) -> AnalysisJob:
        job.heartbeat_at = now
        if stage:
            job.current_stage = stage
        if payload is not None:
            job.stage_payload = payload
        self.db.flush()
        return job

    def mark_analysis_job_success(self, job: AnalysisJob, now: datetime, payload: dict | None = None) -> AnalysisJob:
        job.status = AnalysisJobStatus.success
        job.finished_at = now
        job.next_retry_at = None
        job.locked_by = ""
        job.locked_at = None
        job.heartbeat_at = now
        job.error_reason = ""
        if payload is not None:
            job.stage_payload = payload
        self.db.flush()
        return job

    def mark_analysis_job_failed(
        self,
        job: AnalysisJob,
        now: datetime,
        error_reason: str,
        next_retry_at: datetime | None,
    ) -> AnalysisJob:
        job.retry_count += 1
        job.error_reason = error_reason[:500]
        job.locked_by = ""
        job.locked_at = None
        job.heartbeat_at = now
        job.next_retry_at = next_retry_at
        if next_retry_at is None or job.retry_count >= job.max_retries:
            job.status = AnalysisJobStatus.dead
            job.finished_at = now
        else:
            job.status = AnalysisJobStatus.failed
        self.db.flush()
        return job

    def list_due_analysis_jobs(
        self,
        now: datetime,
        heartbeat_timeout_before: datetime,
        limit: int = 10,
    ) -> list[AnalysisJob]:
        stmt = (
            select(AnalysisJob)
            .options(
                joinedload(AnalysisJob.session).joinedload(InterviewSession.position).selectinload(JobPosition.competencies),
                joinedload(AnalysisJob.session).joinedload(InterviewSession.resume).joinedload(Resume.parse),
                joinedload(AnalysisJob.session).selectinload(InterviewSession.questions),
                joinedload(AnalysisJob.session).selectinload(InterviewSession.answers).joinedload(InterviewAnswer.score),
                joinedload(AnalysisJob.session).selectinload(InterviewSession.answers).joinedload(InterviewAnswer.audio_features),
                joinedload(AnalysisJob.session).selectinload(InterviewSession.answers).joinedload(InterviewAnswer.question),
                joinedload(AnalysisJob.session).joinedload(InterviewSession.report),
            )
            .where(
                or_(
                    AnalysisJob.status == AnalysisJobStatus.pending,
                    and_(
                        AnalysisJob.status == AnalysisJobStatus.failed,
                        AnalysisJob.next_retry_at.is_not(None),
                        AnalysisJob.next_retry_at <= now,
                    ),
                    and_(
                        AnalysisJob.status == AnalysisJobStatus.processing,
                        or_(AnalysisJob.heartbeat_at.is_(None), AnalysisJob.heartbeat_at <= heartbeat_timeout_before),
                    ),
                )
            )
            .order_by(AnalysisJob.created_at.asc(), AnalysisJob.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique())

    def find_active_session(self, user_id: int) -> InterviewSession | None:
        stmt = (
            select(InterviewSession)
            .options(joinedload(InterviewSession.position))
            .where(
                InterviewSession.user_id == user_id,
                InterviewSession.status != InterviewStatus.completed,
            )
            .order_by(InterviewSession.created_at.desc())
        )
        return self.db.scalar(stmt)

    def cleanup_expired_unfinished_sessions(self, expires_before: datetime, user_id: int | None = None) -> int:
        return self._delete_unfinished_sessions(before=expires_before, user_id=user_id)

    def delete_all_unfinished_sessions(self, user_id: int | None = None) -> int:
        return self._delete_unfinished_sessions(before=None, user_id=user_id)

    def delete_unfinished_session(self, session_id: int, user_id: int | None = None) -> int:
        stmt = select(InterviewSession.id).where(
            InterviewSession.id == session_id,
            InterviewSession.status != InterviewStatus.completed,
        )
        if user_id is not None:
            stmt = stmt.where(InterviewSession.user_id == user_id)
        return self._delete_session_ids(list(self.db.scalars(stmt)))

    def delete_completed_session(self, session_id: int, user_id: int | None = None) -> int:
        stmt = select(InterviewSession.id).where(
            InterviewSession.id == session_id,
            InterviewSession.status == InterviewStatus.completed,
        )
        if user_id is not None:
            stmt = stmt.where(InterviewSession.user_id == user_id)
        return self._delete_session_ids(list(self.db.scalars(stmt)))

    def create_question(self, **kwargs) -> InterviewQuestion:
        question = InterviewQuestion(**kwargs)
        self.db.add(question)
        self.db.flush()
        return question

    def get_question(self, question_id: int) -> InterviewQuestion | None:
        return self.db.get(InterviewQuestion, question_id)

    def create_answer(self, **kwargs) -> InterviewAnswer:
        answer = InterviewAnswer(**kwargs)
        self.db.add(answer)
        self.db.flush()
        return answer

    def create_audio_features(self, **kwargs) -> AnswerAudioFeature:
        features = AnswerAudioFeature(**kwargs)
        self.db.add(features)
        self.db.flush()
        return features

    def upsert_audio_features(self, answer_id: int, **kwargs) -> AnswerAudioFeature:
        existing = self.db.scalar(select(AnswerAudioFeature).where(AnswerAudioFeature.answer_id == answer_id))
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            self.db.flush()
            return existing
        return self.create_audio_features(answer_id=answer_id, **kwargs)

    def create_score(self, **kwargs) -> AnswerScore:
        score = AnswerScore(**kwargs)
        self.db.add(score)
        self.db.flush()
        return score

    def upsert_score(self, answer_id: int, **kwargs) -> AnswerScore:
        existing = self.db.scalar(select(AnswerScore).where(AnswerScore.answer_id == answer_id))
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            self.db.flush()
            return existing
        return self.create_score(answer_id=answer_id, **kwargs)

    def get_answer(self, answer_id: int) -> InterviewAnswer | None:
        stmt = (
            select(InterviewAnswer)
            .options(
                joinedload(InterviewAnswer.audio_features),
                joinedload(InterviewAnswer.score),
                joinedload(InterviewAnswer.question),
            )
            .where(InterviewAnswer.id == answer_id)
        )
        return self.db.scalar(stmt)

    def upsert_report(
        self,
        session_id: int,
        total_score: float,
        competency_scores: dict,
        report_level: str,
        report_payload: dict,
    ) -> InterviewReport:
        existing = self.db.scalar(select(InterviewReport).where(InterviewReport.session_id == session_id))
        if existing:
            existing.total_score = total_score
            existing.competency_scores = competency_scores
            existing.report_level = report_level
            existing.report_payload = report_payload
            self.db.flush()
            return existing
        report = InterviewReport(
            session_id=session_id,
            total_score=total_score,
            competency_scores=competency_scores,
            report_level=report_level,
            report_payload=report_payload,
        )
        self.db.add(report)
        self.db.flush()
        return report

    def _delete_unfinished_sessions(self, before: datetime | None, user_id: int | None) -> int:
        session_ids_stmt = select(InterviewSession.id).where(InterviewSession.status != InterviewStatus.completed)
        if before is not None:
            session_ids_stmt = session_ids_stmt.where(InterviewSession.created_at < before)
        if user_id is not None:
            session_ids_stmt = session_ids_stmt.where(InterviewSession.user_id == user_id)
        return self._delete_session_ids(list(self.db.scalars(session_ids_stmt)))

    def _delete_session_ids(self, session_ids: list[int]) -> int:
        if not session_ids:
            return 0

        answer_ids_stmt = select(InterviewAnswer.id).where(InterviewAnswer.session_id.in_(session_ids))
        self.db.execute(delete(AnswerAudioFeature).where(AnswerAudioFeature.answer_id.in_(answer_ids_stmt)))
        self.db.execute(delete(AnswerScore).where(AnswerScore.answer_id.in_(answer_ids_stmt)))
        self.db.execute(delete(AnalysisJob).where(AnalysisJob.session_id.in_(session_ids)))
        self.db.execute(delete(InterviewReport).where(InterviewReport.session_id.in_(session_ids)))
        self.db.execute(delete(InterviewAnswer).where(InterviewAnswer.session_id.in_(session_ids)))
        self.db.execute(delete(InterviewQuestion).where(InterviewQuestion.session_id.in_(session_ids)))
        self.db.execute(delete(InterviewSession).where(InterviewSession.id.in_(session_ids)))
        self.db.flush()
        return len(session_ids)
