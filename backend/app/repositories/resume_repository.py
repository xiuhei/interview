from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Resume, ResumeParse


class ResumeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> Resume:
        resume = Resume(**kwargs)
        self.db.add(resume)
        self.db.flush()
        return resume

    def get(self, resume_id: int) -> Resume | None:
        stmt = select(Resume).options(joinedload(Resume.parse)).where(Resume.id == resume_id)
        return self.db.scalar(stmt)

    def get_for_user(self, user_id: int, resume_id: int) -> Resume | None:
        stmt = (
            select(Resume)
            .options(joinedload(Resume.parse))
            .where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        return self.db.scalar(stmt)

    def list_for_user(self, user_id: int) -> list[Resume]:
        stmt = (
            select(Resume)
            .options(joinedload(Resume.parse))
            .where(Resume.user_id == user_id)
            .order_by(Resume.updated_at.desc(), Resume.id.desc())
        )
        return list(self.db.scalars(stmt).unique())

    def create_parse(self, **kwargs) -> ResumeParse:
        parse = ResumeParse(**kwargs)
        self.db.add(parse)
        self.db.flush()
        return parse
