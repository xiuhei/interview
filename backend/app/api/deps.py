from fastapi import Depends, Header, status
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.security import TokenDecodeError, get_subject_from_token
from app.db.session import get_db
from app.repositories.user_repository import UserRepository


def get_current_user(db: Session = Depends(get_db), authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise AppException("缺少 Bearer Token", status.HTTP_401_UNAUTHORIZED)
    token = authorization.replace("Bearer ", "", 1).strip()
    try:
        user_id = int(get_subject_from_token(token))
    except (TokenDecodeError, ValueError) as exc:
        raise AppException("无效的登录状态", status.HTTP_401_UNAUTHORIZED) from exc
    user = UserRepository(db).get_by_id(user_id)
    if not user:
        raise AppException("用户不存在", status.HTTP_401_UNAUTHORIZED)
    return user


def get_current_admin(user=Depends(get_current_user)):
    if user.role.value != "admin":
        raise AppException("需要管理员权限", status.HTTP_403_FORBIDDEN)
    return user
