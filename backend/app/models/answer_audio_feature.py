from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AnswerAudioFeature(Base, TimestampMixin):
    __tablename__ = "answer_audio_features"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("interview_answers.id"), unique=True)
    volume_stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    pause_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    speech_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    pitch_variation: Mapped[float | None] = mapped_column(Float, nullable=True)
    voiced_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="unavailable")

    answer = relationship("InterviewAnswer", back_populates="audio_features")
