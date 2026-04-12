from pydantic import BaseModel

from app.schemas.common import ORMModel


class CompetencyDimensionRead(ORMModel):
    id: int
    code: str
    name: str
    description: str
    weight: float
    is_required: bool


class JobPositionRead(ORMModel):
    id: int
    code: str
    name: str
    description: str
    weight_config: dict
    question_count_default: int


class PositionDetail(JobPositionRead):
    competencies: list[CompetencyDimensionRead]


class KnowledgeBaseStatus(BaseModel):
    collection_name: str
    configured: bool
    indexed_docs: int
    collection_entities: int
    latest_build_at: str | None
    storage_mode: str
    source_scope: list[str]
