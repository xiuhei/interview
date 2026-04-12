from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    AnswerMode,
    FollowUpType,
    InterviewStatus,
    InterviewStyle,
    QuestionCategory,
)
from app.schemas.common import ORMModel
from app.schemas.position import CompetencyDimensionRead
from app.schemas.resume import ResumeSummary


class InterviewCreateRequest(BaseModel):
    position_code: str
    resume_id: int | None = None
    style: InterviewStyle = InterviewStyle.medium
    answer_mode: AnswerMode = AnswerMode.text


class InterviewQuestionRead(BaseModel):
    id: int
    turn_no: int
    round_no: int
    counts_toward_total: bool
    category: QuestionCategory
    competency_code: str
    question_text: str
    follow_up_reason: str
    follow_up_type: FollowUpType
    evidence_summary: str


class AudioFeatureSummary(BaseModel):
    status: str
    volume_stability: float | None = None
    pause_ratio: float | None = None
    speech_rate: float | None = None
    pitch_variation: float | None = None
    voiced_ratio: float | None = None


class RetrievalEvidence(BaseModel):
    doc_id: str
    role_code: str
    doc_type: str
    competency_code: str
    title: str
    snippet: str
    score: float


class AnswerEvaluation(BaseModel):
    answer_id: int
    question_id: int | None = None
    competency_code: str
    overall_score: float
    text_scores: dict
    audio_scores: dict
    explanation: str
    suggestions: list[str]
    evidence: list[RetrievalEvidence]
    audio_features: AudioFeatureSummary
    answer_text: str = ""
    asr_text: str = ""
    ai_generated: bool = True
    degraded: bool = False


class SubmitAnswerRequest(BaseModel):
    question_id: int
    answer_mode: AnswerMode
    text_answer: str = ""
    audio_file_id: str = ""
    client_duration_ms: int | None = None


class QuestionPrefetchRequest(BaseModel):
    partial_answer: str = ""
    partial_answer_version: int | None = None


class PrefetchCandidateRead(BaseModel):
    question_text: str
    follow_up_type: str
    competency_code: str
    category: str
    angle: str
    confidence: float
    source: str
    quality_score: float | None = None
    referenced_facts: list[str] = Field(default_factory=list)


class QuestionPrefetchResponse(BaseModel):
    ready: bool
    status: str
    based_on: str
    suggested_question: str | None = None
    suggested_follow_up_type: str | None = None
    answer_summary: str = ""
    buffer_quality: float | None = None
    replacement_happened: bool = False
    rejected_count: int = 0
    candidates: list[PrefetchCandidateRead] = Field(default_factory=list)
    updated_at: datetime | None = None


class InterviewProgress(BaseModel):
    current_round: int
    min_rounds: int
    max_rounds: int
    total_questions_asked: int
    can_finish_early: bool


class SubmitAnswerResponse(BaseModel):
    answer_id: int
    evaluation_ready: bool = False
    evaluation: AnswerEvaluation | None = None
    next_action: str
    next_question: InterviewQuestionRead | None = None
    progress: InterviewProgress
    report_ready: bool = False
    report_id: int | None = None
    next_question_preview: str | None = None
    next_question_id: int | None = None


class InterviewNextStepResponse(BaseModel):
    next_action: str
    next_question: InterviewQuestionRead | None = None
    progress: InterviewProgress
    report_ready: bool = False
    report_id: int | None = None
    next_question_preview: str | None = None
    next_question_id: int | None = None


class AnswerEvaluationStatusRead(BaseModel):
    ready: bool
    evaluation: AnswerEvaluation | None = None


class InterviewSessionRead(ORMModel):
    id: int
    title: str
    style: InterviewStyle
    answer_mode: AnswerMode
    status: InterviewStatus
    min_questions: int
    max_questions: int
    current_turn: int
    ai_controls_rounds: bool = True


class ActiveInterviewRead(BaseModel):
    id: int
    title: str
    position: str
    style: InterviewStyle
    answer_mode: AnswerMode
    status: InterviewStatus
    min_questions: int
    max_questions: int
    current_turn: int
    ai_controls_rounds: bool = True
    created_at: datetime
    expires_at: datetime


class InterviewDiscardResult(BaseModel):
    session_id: int


class InterviewDetail(BaseModel):
    session: InterviewSessionRead
    position: str
    competencies: list[CompetencyDimensionRead]
    resume_summary: ResumeSummary | None
    questions: list[InterviewQuestionRead]


class ReportSuggestion(BaseModel):
    issue: str
    reason: str
    improvement: str
    practice_direction: str


class InterviewReportRead(BaseModel):
    session_id: int
    total_score: float
    report_level: str
    competency_scores: dict[str, float]
    radar: list[dict]
    suggestions: list[ReportSuggestion]
    qa_records: list[dict]
    next_training_plan: list[str]
    summary: str
    voice_scores: dict[str, float] = Field(default_factory=dict)
    style: InterviewStyle | None = None
    answer_mode: AnswerMode | None = None
    analysis_status: str | None = None
    analysis_started_at: datetime | None = None
    analysis_job_id: int | None = None
    analysis_stage: str | None = None


class HistoryItem(BaseModel):
    session_id: int
    title: str
    position: str
    style: InterviewStyle
    answer_mode: AnswerMode
    status: InterviewStatus
    total_score: float | None = None
    report_ready: bool = False
    created_at: datetime
    completed_at: datetime | None = None


class HistoryQuestionRecord(BaseModel):
    question_id: int
    answer_id: int | None = None
    turn_no: int
    round_no: int
    counts_toward_total: bool
    category: QuestionCategory
    competency_code: str
    question_text: str
    follow_up_reason: str
    follow_up_type: FollowUpType
    answer_mode: AnswerMode | None = None
    audio_path: str = ""
    audio_duration_seconds: float | None = None
    answer_text: str = ""
    asr_text: str = ""
    answered_at: datetime | None = None
    evaluation_ready: bool = False
    overall_score: float | None = None
    text_scores: dict = Field(default_factory=dict)
    audio_scores: dict = Field(default_factory=dict)
    audio_features: AudioFeatureSummary | None = None
    explanation: str = ""
    suggestions: list[str] = Field(default_factory=list)


class HistoryInterviewDetailRead(InterviewReportRead):
    title: str
    position: str
    style: InterviewStyle
    answer_mode: AnswerMode
    status: InterviewStatus
    created_at: datetime
    completed_at: datetime | None = None
    report_ready: bool = False
    questions: list[HistoryQuestionRecord]



