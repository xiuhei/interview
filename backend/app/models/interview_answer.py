from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AnswerMode


class InterviewAnswer(Base, TimestampMixin):
    __tablename__ = "interview_answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id"), unique=True)
    turn_no: Mapped[int] = mapped_column(Integer, index=True)
    answer_mode: Mapped[AnswerMode] = mapped_column(Enum(AnswerMode))
    answer_text: Mapped[str] = mapped_column(Text, default="")
    audio_path: Mapped[str] = mapped_column(String(255), default="")
    asr_text: Mapped[str] = mapped_column(Text, default="")

    session = relationship("InterviewSession", back_populates="answers")
    question = relationship("InterviewQuestion", back_populates="answer")
    audio_features = relationship("AnswerAudioFeature", back_populates="answer", uselist=False)
    score = relationship("AnswerScore", back_populates="answer", uselist=False)
