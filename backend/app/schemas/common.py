from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ApiEnvelope(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T
    request_id: str = Field(default="")


class IdResponse(BaseModel):
    id: int


class Timestamped(ORMModel):
    created_at: datetime
    updated_at: datetime
