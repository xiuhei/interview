from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.schemas.position import JobPositionRead, PositionDetail
from app.services.position_service import PositionService


router = APIRouter()


@router.get("")
def list_positions(db: Session = Depends(get_db)):
    items = [JobPositionRead.model_validate(item) for item in PositionService(db).list_positions()]
    return ok(items)


@router.get("/{code}/competencies")
def get_position_competencies(code: str, db: Session = Depends(get_db)):
    position = PositionService(db).get_position(code)
    return ok(PositionDetail.model_validate(position))
