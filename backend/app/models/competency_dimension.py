from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CompetencyDimension(Base, TimestampMixin):
    __tablename__ = "competency_dimensions"
    __table_args__ = (
        UniqueConstraint("position_id", "code", name="uq_competency_dimensions_position_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("job_positions.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    weight: Mapped[float] = mapped_column(Float)
    is_required: Mapped[bool] = mapped_column(default=True)

    position = relationship("JobPosition", back_populates="competencies")
