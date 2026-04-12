from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import ok
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, UserProfile
from app.services.auth_service import AuthService


router = APIRouter()


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return ok(AuthService(db).register(payload))


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return ok(AuthService(db).login(payload))


@router.get("/me")
def me(user=Depends(get_current_user)):
    return ok(UserProfile.model_validate(user))
