from pydantic import BaseModel


class GrowthPoint(BaseModel):
    date: str
    total_score: float


class WeaknessInsight(BaseModel):
    tag: str
    count: int
    avg_score: float


class CompetencyProgress(BaseModel):
    competency: str
    average_score: float
    latest_score: float
    session_count: int


class GrowthSummary(BaseModel):
    completed_sessions: int
    average_score: float | None
    latest_score: float | None
    score_delta: float | None
    strongest_competency: str
    focus_competency: str
    readiness_label: str
    narrative: str
    recommendations: list[str]


class GrowthPlanItem(BaseModel):
    title: str
    focus: str
    action: str
    expected_result: str


class GrowthInsight(BaseModel):
    summary: GrowthSummary
    trends: list[GrowthPoint]
    competency_progress: list[CompetencyProgress]
    weaknesses: list[WeaknessInsight]
    plan: list[GrowthPlanItem]
