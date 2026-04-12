from fastapi import status
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.security import create_access_token, get_password_hash, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthToken, LoginRequest, RegisterRequest, UserProfile


class AuthService:
    def __init__(self, db: Session) -> None:
        self.repo = UserRepository(db)
        self.db = db

    def register(self, payload: RegisterRequest) -> AuthToken:
        if self.repo.get_by_username(payload.username):
            raise AppException("用户名已存在", status.HTTP_409_CONFLICT)
        if self.repo.get_by_email(payload.email):
            raise AppException("邮箱已存在", status.HTTP_409_CONFLICT)
        user = self.repo.create(
            email=payload.email,
            username=payload.username,
            full_name=payload.full_name,
            hashed_password=get_password_hash(payload.password),
        )
        self.db.commit()
        self.db.refresh(user)
        return AuthToken(access_token=create_access_token(str(user.id)), user=UserProfile.model_validate(user))

    def login(self, payload: LoginRequest) -> AuthToken:
        user = self.repo.get_by_username(payload.username)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AppException("用户名或密码错误", status.HTTP_401_UNAUTHORIZED)
        return AuthToken(access_token=create_access_token(str(user.id)), user=UserProfile.model_validate(user))
