from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import ok
from app.db.session import get_db
from app.schemas.resume import ResumeLibraryItem, ResumeParseRead, ResumeRead
from app.services.resume_service import ResumeService


router = APIRouter()


@router.get("")
def list_resumes(user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = ResumeService(db).list_resumes(user.id)
    return ok([ResumeLibraryItem.model_validate(item) for item in items])


@router.post("/upload")
def upload_resume(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = ResumeService(db).save_upload(user.id, file)
    return ok(ResumeRead.model_validate(resume), message="简历上传成功")


@router.post("/{resume_id}/parse")
def parse_resume(resume_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    resume = ResumeService(db).parse_resume(resume_id, user_id=user.id)
    return ok(ResumeParseRead.model_validate(resume.parse), message="简历解析完成")


@router.get("/{resume_id}/summary")
def get_resume_summary(resume_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    summary = ResumeService(db).get_summary(resume_id, user_id=user.id)
    return ok(summary)
