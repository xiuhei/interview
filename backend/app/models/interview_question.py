from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import FollowUpType, QuestionCategory


class InterviewQuestion(Base, TimestampMixin):
    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    turn_no: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[QuestionCategory] = mapped_column(Enum(QuestionCategory))
    competency_code: Mapped[str] = mapped_column(String(80), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    follow_up_reason: Mapped[str] = mapped_column(String(500), default="")
    follow_up_type: Mapped[FollowUpType] = mapped_column(
        Enum(FollowUpType), default=FollowUpType.none
    )
    evidence_summary: Mapped[str] = mapped_column(String(1000), default="")

    session = relationship("InterviewSession", back_populates="questions")
    answer = relationship("InterviewAnswer", back_populates="question", uselist=False)
