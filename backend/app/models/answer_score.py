from sqlalchemy import Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AnswerScore(Base, TimestampMixin):
    __tablename__ = "answer_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("interview_answers.id"), unique=True)
    competency_code: Mapped[str] = mapped_column(String(80), index=True)
    overall_score: Mapped[float] = mapped_column(Float)
    text_scores: Mapped[dict] = mapped_column(JSON)
    audio_scores: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(String(2000))
    suggestions: Mapped[list] = mapped_column(JSON)
    evidence: Mapped[list] = mapped_column(JSON)
    debug_payload: Mapped[dict] = mapped_column(JSON)

    answer = relationship("InterviewAnswer", back_populates="score")
