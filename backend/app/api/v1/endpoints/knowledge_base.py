from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.responses import ok
from app.db.session import get_db
from app.services.knowledge_base_service import KnowledgeBaseService


router = APIRouter()


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    return ok(KnowledgeBaseService(db).get_status())


@router.post("/rebuild")
def rebuild_kb(_: object = Depends(get_current_admin), db: Session = Depends(get_db)):
    return ok(KnowledgeBaseService(db).rebuild(), message="知识库已重建")
