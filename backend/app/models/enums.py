from enum import Enum


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class ResumeStatus(str, Enum):
    uploaded = "uploaded"
    parsed = "parsed"
    failed = "failed"


class InterviewStyle(str, Enum):
    simple = "simple"
    medium = "medium"
    hard = "hard"


class AnswerMode(str, Enum):
    text = "text"
    audio = "audio"


class InterviewStatus(str, Enum):
    opening = "opening"
    resume_clarification = "resume_clarification"
    technical_question = "technical_question"
    deep_follow_up = "deep_follow_up"
    candidate_question = "candidate_question"
    summary = "summary"
    completed = "completed"


class QuestionCategory(str, Enum):
    opening = "opening"
    clarification = "clarification"
    technical = "technical"
    follow_up = "follow_up"
    wrap_up = "wrap_up"


class FollowUpType(str, Enum):
    none = "none"
    deepen = "deepen"
    redirect = "redirect"
    credibility = "credibility"
    switch_dimension = "switch_dimension"


class ReportLevel(str, Enum):
    weak = "较弱"
    medium = "中等"
    good = "良好"
    excellent = "优秀"


class AnalysisJobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"
    dead = "dead"
