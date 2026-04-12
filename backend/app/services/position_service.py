from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.repositories.position_repository import PositionRepository


class PositionService:
    def __init__(self, db: Session) -> None:
        self.repo = PositionRepository(db)

    def list_positions(self):
        return self.repo.list_positions()

    def get_position(self, code: str):
        position = self.repo.get_by_code(code)
        if not position:
            raise AppException("岗位不存在", 404)
        return position
