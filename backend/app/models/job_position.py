from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class JobPosition(Base, TimestampMixin):
    __tablename__ = "job_positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    weight_config: Mapped[dict] = mapped_column(JSON)
    question_count_default: Mapped[int] = mapped_column(default=6)

    competencies = relationship("CompetencyDimension", back_populates="position")
    sessions = relationship("InterviewSession", back_populates="position")
