from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import ok
from app.db.session import get_db
from app.schemas.interview import InterviewCreateRequest, InterviewSessionRead, QuestionPrefetchRequest, SubmitAnswerRequest
from app.services.interview_service import InterviewService


router = APIRouter()


@router.post("")
def create_interview(payload: InterviewCreateRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    session = InterviewService(db).create_session(user.id, payload)
    return ok(InterviewSessionRead.model_validate(session), message="面试创建成功")


@router.post("/audio/upload")
def upload_audio(file: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    payload = InterviewService(db).upload_audio(file)
    return ok(payload, message="语音上传成功")


@router.get("/active")
def get_active_interview(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(InterviewService(db).get_active_session(user.id))


@router.post("/{session_id}/discard")
def discard_interview(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    payload = InterviewService(db).discard_session(user.id, session_id)
    return ok(payload, message="未完成面试已结束")


@router.get("/{session_id}/first-question")
def get_first_question(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    question = InterviewService(db).get_first_question(session_id)
    return ok(question)


@router.post("/{session_id}/answers")
def submit_answer(session_id: int, payload: SubmitAnswerRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    return ok(InterviewService(db).submit_answer(session_id, payload), message="答案已保存")


@router.post("/{session_id}/questions/{question_id}/prefetch")
def prefetch_question(
    session_id: int,
    question_id: int,
    payload: QuestionPrefetchRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    return ok(InterviewService(db).prefetch_next_question(session_id, question_id, payload))


@router.get("/{session_id}/answers/{answer_id}/evaluation")
def get_answer_evaluation(session_id: int, answer_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    return ok(InterviewService(db).get_answer_evaluation(session_id, answer_id))


@router.get("/{session_id}/next-question")
def get_next_question(
    session_id: int,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    return ok(InterviewService(db).get_next_question(session_id, background_tasks=background_tasks))


@router.post("/{session_id}/complete")
def complete_session(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    return ok(InterviewService(db).complete_session(session_id), message="面试已结束")


@router.get("/{session_id}/report")
def get_report(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    return ok(InterviewService(db).get_report(session_id))


@router.get("/{session_id}")
def get_session_detail(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    return ok(InterviewService(db).get_detail(session_id))
