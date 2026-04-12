from sqlalchemy import Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InterviewReport(Base, TimestampMixin):
    __tablename__ = "interview_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"), unique=True)
    total_score: Mapped[float] = mapped_column(Float)
    competency_scores: Mapped[dict] = mapped_column(JSON)
    report_level: Mapped[str] = mapped_column(String(20))
    report_payload: Mapped[dict] = mapped_column(JSON)

    session = relationship("InterviewSession", back_populates="report")
