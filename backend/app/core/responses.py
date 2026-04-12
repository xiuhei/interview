from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.request_context import ensure_request_id


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T
    request_id: str = Field(default_factory=ensure_request_id)


def ok(data: T, message: str = "ok") -> ApiResponse[T]:
    return ApiResponse[T](data=data, message=message)