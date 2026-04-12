from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import ok
from app.db.session import get_db
from app.services.interview_service import InterviewService


router = APIRouter()


@router.get("/interviews")
def list_interviews(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(InterviewService(db).list_history(user.id))


@router.get("/interviews/{session_id}")
def get_interview_archive(
    session_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(InterviewService(db).get_history_detail(user.id, session_id))


@router.delete("/interviews/{session_id}")
def delete_interview_archive(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(InterviewService(db).delete_history(user.id, session_id), message="面试记录已删除")


@router.get("/reports/{session_id}")
def get_report_detail(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    return ok(InterviewService(db).get_report(session_id))
