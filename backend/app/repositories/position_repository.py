from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import JobPosition


class PositionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_positions(self) -> list[JobPosition]:
        stmt = select(JobPosition).options(selectinload(JobPosition.competencies)).order_by(JobPosition.id)
        return list(self.db.scalars(stmt).unique())

    def get_by_code(self, code: str) -> JobPosition | None:
        stmt = (
            select(JobPosition)
            .options(selectinload(JobPosition.competencies))
            .where(JobPosition.code == code)
        )
        return self.db.scalar(stmt)
