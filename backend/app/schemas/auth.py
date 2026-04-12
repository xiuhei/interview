from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=20)
    full_name: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=50)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserProfile(ORMModel):
    id: int
    email: EmailStr
    username: str
    full_name: str
    role: UserRole


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
