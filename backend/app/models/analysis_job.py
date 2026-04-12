from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AnalysisJobStatus


class AnalysisJob(Base, TimestampMixin):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        UniqueConstraint("session_id", "version", name="uq_analysis_jobs_session_id_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    status: Mapped[AnalysisJobStatus] = mapped_column(Enum(AnalysisJobStatus), default=AnalysisJobStatus.pending, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=4)
    current_stage: Mapped[str] = mapped_column(String(50), default="queued")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    locked_by: Mapped[str] = mapped_column(String(100), default="")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_reason: Mapped[str] = mapped_column(String(500), default="")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    stage_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    session = relationship("InterviewSession", back_populates="analysis_jobs")
