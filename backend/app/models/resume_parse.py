from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ResumeParse(Base, TimestampMixin):
    __tablename__ = "resume_parses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), unique=True, index=True)
    summary: Mapped[dict] = mapped_column(JSON)
    raw_result: Mapped[dict] = mapped_column(JSON)

    resume = relationship("Resume", back_populates="parse")
