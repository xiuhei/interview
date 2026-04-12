from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ResumeStatus
from app.schemas.common import ORMModel


class ResumeScoreBreakdown(BaseModel):
    clarity: float = 0.0
    project_depth: float = 0.0
    impact: float = 0.0
    role_relevance: float = 0.0
    credibility: float = 0.0


class ResumeJobMatch(BaseModel):
    position_code: str
    position_name: str
    score: float
    level: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    matched_projects: list[str] = Field(default_factory=list)
    interview_focuses: list[str] = Field(default_factory=list)
    summary: str = ""


class ResumeRead(ORMModel):
    id: int
    filename: str
    stored_path: str
    mime_type: str
    status: ResumeStatus
    created_at: datetime
    updated_at: datetime


class ResumeSummary(BaseModel):
    candidate_name: str | None = None
    background: str
    project_experiences: list[str]
    tech_stack: list[str]
    highlights: list[str]
    risk_points: list[str]
    years_of_experience: int | None = None
    overall_score: float = 0.0
    score_breakdown: ResumeScoreBreakdown = Field(default_factory=ResumeScoreBreakdown)
    job_matches: list[ResumeJobMatch] = Field(default_factory=list)
    best_job_match: ResumeJobMatch | None = None
    resume_suggestions: list[str] = Field(default_factory=list)
    interview_focuses: list[str] = Field(default_factory=list)


class ResumeLibraryItem(ResumeRead):
    summary: ResumeSummary | None = None


class ResumeParseRead(ORMModel):
    id: int
    summary: ResumeSummary
    raw_result: dict
