from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AnswerMode, InterviewStatus, InterviewStyle


class InterviewSession(Base, TimestampMixin):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("job_positions.id"), index=True)
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    style: Mapped[InterviewStyle] = mapped_column(Enum(InterviewStyle))
    answer_mode: Mapped[AnswerMode] = mapped_column(Enum(AnswerMode))
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus), default=InterviewStatus.opening, index=True
    )
    min_questions: Mapped[int] = mapped_column(Integer, default=3)
    max_questions: Mapped[int] = mapped_column(Integer, default=7)
    early_reject_score_threshold: Mapped[float] = mapped_column(Float, default=30.0)
    early_accept_score_threshold: Mapped[float] = mapped_column(Float, default=75.0)
    current_turn: Mapped[int] = mapped_column(Integer, default=0)
    weakness_tags: Mapped[str] = mapped_column(String(500), default="")
    end_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    end_decided_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="sessions")
    position = relationship("JobPosition", back_populates="sessions")
    resume = relationship("Resume", back_populates="sessions")
    questions = relationship("InterviewQuestion", back_populates="session", order_by="InterviewQuestion.turn_no")
    answers = relationship("InterviewAnswer", back_populates="session", order_by="InterviewAnswer.turn_no")
    report = relationship("InterviewReport", back_populates="session", uselist=False)
    analysis_jobs = relationship("AnalysisJob", back_populates="session")
