from __future__ import annotations

import hashlib
import json
import logging
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedding_client
from app.audio.analysis import analyze_audio, map_audio_scores, measure_audio_duration_seconds
from app.audio.speech import get_speech_service
from app.db.session import SessionLocal
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.enums import AnalysisJobStatus, AnswerMode, FollowUpType, InterviewStatus, InterviewStyle, QuestionCategory
from app.repositories.interview_repository import InterviewRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.system_repository import SystemRepository
from app.rag.service import RetrievalService
from app.schemas.interview import (
    ActiveInterviewRead,
    AnswerEvaluation,
    AnswerEvaluationStatusRead,
    AudioFeatureSummary,
    HistoryItem,
    InterviewCreateRequest,
    InterviewDiscardResult,
    InterviewDetail,
    InterviewNextStepResponse,
    InterviewProgress,
    InterviewQuestionRead,
    HistoryInterviewDetailRead,
    HistoryQuestionRecord,
    InterviewReportRead,
    InterviewSessionRead,
    PrefetchCandidateRead,
    QuestionPrefetchRequest,
    QuestionPrefetchResponse,
    ReportSuggestion,
    RetrievalEvidence,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.schemas.position import CompetencyDimensionRead
from app.schemas.resume import ResumeJobMatch, ResumeSummary
from app.services.interview_difficulty import get_difficulty_profile, normalize_difficulty
from app.services.interview_termination_policy import InterviewTerminationDecision, InterviewTerminationPolicy
from app.services.metadata_service import get_competency_label
from app.services.prompt_service import PromptService
from app.services.question_seed_service import QuestionSeedService
from app.services.scoring_service import ScoringService


logger = logging.getLogger(__name__)
SESSION_TTL_HOURS = 48
REPORT_REBUILDING_SESSIONS: set[int] = set()
REPORT_PENDING_LEVEL = "分析中"
REPORT_PENDING_STATUS = "pending"
REPORT_READY_STATUS = "ready"
ANALYSIS_JOB_VERSION = 1
ANALYSIS_JOB_HEARTBEAT_TIMEOUT = timedelta(minutes=5)
ANALYSIS_JOB_RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
)
ANALYSIS_WORKER_ID = f"{socket.gethostname()}:{uuid4().hex[:8]}"

MAIN_QUESTION_CATEGORIES = {
    QuestionCategory.opening,
    QuestionCategory.clarification,
    QuestionCategory.technical,
}
STYLE_LABELS = {
    InterviewStyle.simple: "简单",
    InterviewStyle.medium: "中等",
    InterviewStyle.hard: "困难",
}
CONFUSION_MARKERS = [
    "不知道",
    "不太清楚",
    "不清楚",
    "不理解",
    "没听懂",
    "没看懂",
    "什么意思",
    "啥意思",
    "不会",
    "答不上来",
    "不懂",
    "don't know",
    "not sure",
    "i don't know",
    "i do not know",
]
LOW_SIGNAL_MARKERS = [
    "随便",
    "乱说",
    "胡说",
    "瞎说",
    "哈哈",
    "呵呵",
]
QUESTION_PIPELINE_CACHE: dict[int, dict] = {}
WARMUP_MAIN_QUESTION_COUNT = 4
WARMUP_FOLLOW_UP_COUNT = 3
PREFETCH_MIN_ANSWER_CHARS = 24
PREFETCH_MATCH_PREFIX_CHARS = 16
SEMANTIC_DUPLICATE_THRESHOLD = 0.85
SEMANTIC_SOFT_THRESHOLD = 0.75
BUFFER_REPLACE_MARGIN = 0.05
GENERIC_FOLLOW_UP_MARKERS = ["请再详细说说", "展开讲讲", "再说清楚一点", "你刚刚的回答不清晰", "请具体一点"]
MAX_CREDIBILITY_FOLLOW_UPS_PER_SESSION = 1



class InterviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.repo = InterviewRepository(db)
        self.position_repo = PositionRepository(db)
        self.resume_repo = ResumeRepository(db)
        self.system_repo = SystemRepository(db)
        self.seed_service = QuestionSeedService()
        self.scoring_service = ScoringService()
        self.retrieval_service = RetrievalService()
        self.prompt_service = PromptService()
        self.speech_service = get_speech_service()
        self._embedding_client = None

    def create_session(self, user_id: int, payload: InterviewCreateRequest):
        self._cleanup_expired_sessions(user_id=user_id)
        active_session = self.repo.find_active_session(user_id)
        if active_session:
            raise AppException("你有一场待完成的面试，请先继续作答，或删除后重新开始新的面试。", 409)
        position = self.position_repo.get_by_code(payload.position_code)
        if not position:
            raise AppException("Position not found", 404)
        if payload.answer_mode == AnswerMode.audio and not self.settings.immersive_voice_interview_ready:
            raise AppException("Real voice interview requires configured commercial LLM and speech APIs", 400)
        resume = None
        if payload.resume_id:
            if hasattr(self.resume_repo, "get_for_user"):
                resume = self.resume_repo.get_for_user(user_id, payload.resume_id)
            else:
                resume = self.resume_repo.get(payload.resume_id)
                if resume and getattr(resume, "user_id", user_id) != user_id:
                    resume = None
            if not resume:
                raise AppException("Resume not found", 404)
            if not getattr(resume, "parse", None):
                from app.services.resume_service import ResumeService

                resume = ResumeService(self.db).parse_resume(resume.id, user_id=user_id)
        answer_mode = payload.answer_mode
        title = f"{position.name} / {STYLE_LABELS.get(payload.style, payload.style.value)} 面试"
        session = self.repo.create_session(
            user_id=user_id,
            position_id=position.id,
            resume_id=resume.id if resume else None,
            title=title,
            style=payload.style,
            answer_mode=answer_mode,
            min_questions=self.settings.dynamic_interview_min_questions,
            max_questions=self.settings.dynamic_interview_max_questions,
            early_reject_score_threshold=self.settings.dynamic_interview_early_reject_score,
            early_accept_score_threshold=self.settings.dynamic_interview_early_accept_score,
            status=InterviewStatus.opening,
        )
        self.db.commit()
        self.db.refresh(session)
        logger.info(
            "interview session created | session_id=%s user_id=%s position_code=%s answer_mode=%s style=%s min_questions=%s max_questions=%s resume_id=%s",
            session.id,
            user_id,
            position.code,
            answer_mode.value,
            payload.style.value,
            session.min_questions,
            session.max_questions,
            resume.id if resume else None,
        )
        return session

    def get_active_session(self, user_id: int) -> ActiveInterviewRead | None:
        self._cleanup_expired_sessions(user_id=user_id)
        session = self.repo.find_active_session(user_id)
        if not session:
            return None
        settings = getattr(self, "settings", None) or get_settings()
        min_questions = getattr(session, "min_questions", None)
        if min_questions is None:
            min_questions = getattr(settings, "dynamic_interview_min_questions", get_settings().dynamic_interview_min_questions)
        max_questions = getattr(session, "max_questions", None)
        if max_questions is None:
            max_questions = getattr(settings, "dynamic_interview_max_questions", get_settings().dynamic_interview_max_questions)
        expires_at = session.created_at + timedelta(hours=SESSION_TTL_HOURS)
        return ActiveInterviewRead(
            id=session.id,
            title=session.title,
            position=session.position.name,
            style=session.style,
            answer_mode=session.answer_mode,
            status=session.status,
            min_questions=int(min_questions),
            max_questions=int(max_questions),
            current_turn=session.current_turn,
            ai_controls_rounds=True,
            created_at=session.created_at,
            expires_at=expires_at,
        )

    def discard_session(self, user_id: int, session_id: int) -> InterviewDiscardResult:
        self._cleanup_expired_sessions(user_id=user_id)
        session = self._get_session(session_id)
        if session.user_id != user_id:
            raise AppException("Interview session not found", 404)
        if session.status == InterviewStatus.completed:
            raise AppException("已完成的面试不能按未完成面试结束。", 409)
        deleted = self.repo.delete_unfinished_session(session_id=session.id, user_id=user_id)
        if not deleted:
            raise AppException("未找到可结束的未完成面试。", 404)
        self.db.commit()
        self._clear_pipeline_cache(session.id)
        logger.info(
            "unfinished interview discarded | session_id=%s user_id=%s",
            session.id,
            user_id,
        )
        return InterviewDiscardResult(session_id=session.id)

    def get_first_question(self, session_id: int) -> InterviewQuestionRead:
        self._cleanup_expired_sessions()
        session = self._get_session(session_id)
        ordered_questions = self._ordered_questions(session)
        if ordered_questions:
            first_question = ordered_questions[0]
            logger.info("reuse first question | session_id=%s question_id=%s", session.id, first_question.id)
            return self._serialize_question(session, first_question, ordered_questions)
        summary = self._resume_summary(session)
        question_text, competency_code = self._seed_opening_question(session, summary)
        retrieval = self.retrieval_service.retrieve_with_meta(
            query=self._build_opening_query(session.position.code, competency_code, question_text, summary),
            role_code=session.position.code,
            profile_name="question_generation",
        )
        logger.info(
            "prompt context prepared | prompt_name=%s role_code=%s competency_code=%s retrieval_backend=%s evidence_count=%s",
            "opening_question",
            session.position.code,
            competency_code,
            retrieval.backend,
            len(retrieval.evidence),
        )
        seed_examples = self.seed_service.get_seed_examples(
            session.position.code, competency_code, count=3,
        )
        prompt_result, fallback_used = self._run_required_prompt(
            "opening_question",
            {
                "task_context": {
                    "position": session.position.name,
                    "role_code": session.position.code,
                    "style": self._session_style_code(session),
                    "difficulty": self._difficulty_context(session),
                    "competency_code": competency_code,
                    "stage": "opening_question",
                    "resume_summary": self._build_resume_prompt_context(summary, session.position.code) if summary else None,
                },
                "retrieval_context": self._build_retrieval_context(retrieval.evidence),
                "draft": {
                    "question": question_text,
                    "seed_examples": seed_examples,
                    "instruction": "以上 seed_examples 仅供参考风格和难度，请生成一道新的、不重复的面试题。",
                },
            },
            error_message="AI 首题生成失败，请检查大模型服务配置、鉴权和网络连接后重试。",
            fallback_result={"draft_question": question_text},
        )
        retrieval_backend = retrieval.backend
        evidence_count = len(retrieval.evidence)
        final_question_text = self._sanitize_generated_question(
            prompt_result.get("draft_question", question_text),
            question_text,
        )
        try:
            question = self.repo.create_question(
                session_id=session.id,
                turn_no=1,
                category=QuestionCategory.opening,
                competency_code=competency_code,
                question_text=final_question_text,
            follow_up_reason="根据岗位要求与简历信息生成开场问题",
                follow_up_type=FollowUpType.none,
                evidence_summary=self._format_evidence_summary(
                    retrieval_backend,
                    fallback_used,
                    evidence_count,
                    competency_code,
                ),
            )
            session.current_turn = 1
            session.status = InterviewStatus.resume_clarification if summary else InterviewStatus.technical_question
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            logger.exception(
                "first question persistence failed | session_id=%s competency_code=%s",
                session.id,
                competency_code,
            )
            raise AppException("面试会话已失效或不存在，请重新开始面试。", 409) from exc
        refreshed_session = self._get_session(session.id)
        logger.info(
            "first question generated | session_id=%s question_id=%s competency_code=%s fallback_used=%s retrieval_backend=%s evidence_count=%s has_resume_summary=%s",
            refreshed_session.id,
            question.id,
            competency_code,
            fallback_used,
            retrieval_backend,
            evidence_count,
            summary is not None,
        )
        generated_question = self._get_question_in_session(refreshed_session, question.id)
        return self._serialize_question(refreshed_session, generated_question)

    def upload_audio(self, file) -> dict:
        extension = Path(file.filename or "answer.wav").suffix or ".wav"
        stored_name = f"{uuid4().hex}{extension}"
        target = self.settings.upload_dir / "audio" / stored_name
        with target.open("wb") as output:
            output.write(file.file.read())
        logger.info("audio uploaded | stored_name=%s original_name=%s", stored_name, file.filename or "answer.wav")
        return {
            "file_id": stored_name,
            "url": f"/uploads/audio/{stored_name}",
            "stored_path": str(target),
        }

    def submit_answer(self, session_id: int, payload: SubmitAnswerRequest) -> SubmitAnswerResponse:
        self._cleanup_expired_sessions()
        session = self._get_session(session_id)
        question = self.repo.get_question(payload.question_id)
        if not question or question.session_id != session.id:
            raise AppException("Question not found", 404)
        if self._session_answer_mode(session) == AnswerMode.audio and payload.answer_mode != AnswerMode.audio:
            raise AppException("Real voice interview only supports audio answers", 400)

        existing_answer = self._find_answer_for_question(session, payload.question_id)
        if existing_answer:
            replacement_response = self._replace_pending_audio_answer_if_needed(existing_answer, payload)
            if replacement_response is not None:
                refreshed_session = self._get_session(session.id)
                return SubmitAnswerResponse(
                    answer_id=existing_answer.id,
                    question_id=existing_answer.question_id,
                    evaluation_ready=False,
                    evaluation=None,
                    next_action="awaiting_next_question",
                    progress=self._build_progress(refreshed_session),
                )
            logger.info(
                "duplicate answer submission reused saved answer | session_id=%s question_id=%s answer_id=%s",
                session.id,
                payload.question_id,
                existing_answer.id,
            )
            return self._build_existing_submit_response(session, existing_answer)

        answer_text = payload.text_answer.strip()
        audio_path = None
        if payload.answer_mode == AnswerMode.audio:
            if not payload.audio_file_id:
                raise AppException("Audio answer missing audio_file_id")
            audio_path = self.settings.upload_dir / "audio" / payload.audio_file_id
            if not audio_path.exists():
                raise AppException("Audio file not found", 404)

        logger.info(
            "submit answer accepted | session_id=%s question_id=%s turn_no=%s answer_mode=%s answer_length=%s has_audio=%s",
            session.id,
            question.id,
            question.turn_no,
            payload.answer_mode.value,
            len(answer_text),
            audio_path is not None,
        )

        try:
            answer = self.repo.create_answer(
                session_id=session.id,
                question_id=question.id,
                turn_no=question.turn_no,
                answer_mode=payload.answer_mode,
                answer_text=answer_text,
                audio_path=str(audio_path.relative_to(self.settings.upload_dir.parent)) if audio_path else "",
                asr_text="",
            )
        except IntegrityError:
            self.db.rollback()
            refreshed_session = self._get_session(session.id)
            existing_answer = self._find_answer_for_question(refreshed_session, question.id)
            if existing_answer:
                logger.warning(
                    "duplicate answer submission resolved after integrity conflict | session_id=%s question_id=%s answer_id=%s",
                    refreshed_session.id,
                    question.id,
                    existing_answer.id,
                )
                return self._build_existing_submit_response(refreshed_session, existing_answer)
            raise

        self.db.commit()
        refreshed_session = self._get_session(session.id)
        return SubmitAnswerResponse(
            answer_id=answer.id,
            question_id=answer.question_id,
            evaluation_ready=False,
            evaluation=None,
            next_action="awaiting_next_question",
            progress=self._build_progress(refreshed_session),
        )

    def prefetch_next_question(
        self,
        session_id: int,
        question_id: int,
        payload: QuestionPrefetchRequest,
    ) -> QuestionPrefetchResponse:
        self._cleanup_expired_sessions()
        session = self._get_session(session_id)
        question = self.repo.get_question(question_id)
        if not question or question.session_id != session.id:
            raise AppException("Question not found", 404)

        pipeline_state = self._ensure_question_pipeline_state(session, question)
        partial_answer = payload.partial_answer.strip()
        prefetch_payload = self._build_prefetch_candidates(session, question, partial_answer)
        current_entry = pipeline_state["questions"].get(question.id, {})
        strategy = prefetch_payload.get("strategy", {})
        updated_entry = {
            **current_entry,
            **prefetch_payload,
            "question_id": question.id,
            "partial_answer": partial_answer,
            "version": payload.partial_answer_version or 0,
            "status": "warmup_ready" if len(partial_answer) < PREFETCH_MIN_ANSWER_CHARS else "refined_ready",
            "based_on": "预热题池" if not partial_answer else "回答片段",
            "updated_at": datetime.now(timezone.utc),
        }
        pipeline_state["questions"][question.id] = updated_entry
        best = updated_entry.get("current_best")
        logger.info(
            "next question prefetched | session_id=%s question_id=%s candidate_count=%s based_on=%s version=%s overall_score=%s preferred_type=%s rejected_count=%s replacement=%s",
            session.id,
            question.id,
            len(updated_entry.get("candidates", [])),
            updated_entry["based_on"],
            updated_entry["version"],
            strategy.get("overall_score"),
            getattr(strategy.get("follow_up_type"), "value", None),
            updated_entry.get("rejected_count", 0),
            updated_entry.get("replacement_happened", False),
        )
        return QuestionPrefetchResponse(
            ready=best is not None,
            status=updated_entry["status"],
            based_on=updated_entry["based_on"],
            suggested_question=best["question_text"] if best else None,
            suggested_follow_up_type=best["follow_up_type"] if best else None,
            answer_summary=updated_entry.get("answer_summary", ""),
            buffer_quality=updated_entry.get("buffer_quality"),
            replacement_happened=updated_entry.get("replacement_happened", False),
            rejected_count=int(updated_entry.get("rejected_count", 0) or 0),
            candidates=[PrefetchCandidateRead(**item) for item in updated_entry.get("candidates", [])[:5]],
            updated_at=updated_entry["updated_at"],
        )
    def get_next_question(self, session_id: int, background_tasks=None) -> InterviewNextStepResponse:
        self._cleanup_expired_sessions()
        session = self._get_session(session_id)
        ordered_questions = self._ordered_questions(session)
        if not ordered_questions:
            raise AppException("No question exists in the current session", 400)

        if session.status == InterviewStatus.completed:
            self._schedule_latest_missing_score(session, background_tasks)
            self._schedule_history_report(session)
            return InterviewNextStepResponse(
                next_action="completed",
                next_question=None,
                progress=self._build_progress(session),
                report_ready=self._is_report_ready(session),
                report_id=session.id if self._is_report_ready(session) else None,
            )

        last_question = ordered_questions[-1]
        last_answer = self._find_answer_for_question(session, last_question.id)
        if not last_answer:
            self._schedule_latest_missing_score(session, background_tasks)
            logger.info("next question reused | session_id=%s question_id=%s", session.id, last_question.id)
            return self._build_next_step_response(session, last_question, ordered_questions)

        answer_text, score_payload, evidence, retrieval_backend = self._prepare_next_question_context(
            session,
            last_question,
            last_answer,
        )
        self._schedule_answer_scoring(background_tasks, session.id, last_answer.id)

        if last_question.category == QuestionCategory.wrap_up:
            session.status = InterviewStatus.completed
            if session.completed_at is None:
                session.completed_at = datetime.now(timezone.utc)
            session.end_reason = session.end_reason or "completed_max_questions"
            session.end_decided_by = session.end_decided_by or "ai"
            self.db.commit()
            refreshed_session = self._get_session(session.id)
            self._clear_pipeline_cache(refreshed_session.id)
            logger.info(
                "wrap-up answer marked session completed | session_id=%s answer_id=%s",
                refreshed_session.id,
                last_answer.id,
            )
            self._schedule_history_report(refreshed_session)
            return InterviewNextStepResponse(
                next_action="completed",
                next_question=None,
                progress=self._build_progress(refreshed_session),
                report_ready=self._is_report_ready(refreshed_session),
                report_id=refreshed_session.id if self._is_report_ready(refreshed_session) else None,
            )

        next_action, next_question_id = self._plan_next_question(
            session,
            last_question,
            answer_text,
            score_payload,
            evidence,
            retrieval_backend=retrieval_backend,
        )
        self.db.commit()
        refreshed_session = self._get_session(session.id)
        if next_action == "completed" or next_question_id is None:
            self._clear_pipeline_cache(refreshed_session.id)
            self._schedule_history_report(refreshed_session)
            logger.info(
                "interview completed after final scored answer | session_id=%s answer_id=%s",
                refreshed_session.id,
                last_answer.id,
            )
            return InterviewNextStepResponse(
                next_action="completed",
                next_question=None,
                progress=self._build_progress(refreshed_session),
                report_ready=self._is_report_ready(refreshed_session),
                report_id=refreshed_session.id if self._is_report_ready(refreshed_session) else None,
            )
        next_question = self._get_question_in_session(refreshed_session, next_question_id)
        logger.info(
            "next question generated | session_id=%s answer_id=%s next_action=%s next_question_id=%s",
            refreshed_session.id,
            last_answer.id,
            next_action,
            next_question.id,
        )
        return self._build_next_step_response(refreshed_session, next_question)

    def get_answer_evaluation(self, session_id: int, answer_id: int) -> AnswerEvaluationStatusRead:
        self._cleanup_expired_sessions()
        session = self._get_session(session_id)
        answer = self.repo.get_answer(answer_id)
        if not answer or answer.session_id != session.id:
            raise AppException("Answer not found", 404)
        evaluation = self._serialize_answer_evaluation(answer)
        return AnswerEvaluationStatusRead(
            ready=evaluation is not None,
            evaluation=evaluation,
        )

    def get_detail(self, session_id: int) -> InterviewDetail:
        self._cleanup_expired_sessions()
        session = self._get_session(session_id)
        ordered_questions = self._ordered_questions(session)
        return InterviewDetail(
            session=InterviewSessionRead.model_validate(session),
            position=session.position.name,
            competencies=[CompetencyDimensionRead.model_validate(item) for item in session.position.competencies],
            resume_summary=self._resume_summary(session),
            questions=[self._serialize_question(session, item, ordered_questions) for item in ordered_questions],
        )

    def complete_session(self, session_id: int) -> InterviewReportRead:
        self._cleanup_expired_sessions()
        session = self._get_session(session_id)
        if not hasattr(self, "db"):
            return self._finalize_session(session)
        if session.status != InterviewStatus.completed:
            session.status = InterviewStatus.completed
            if getattr(session, "completed_at", None) is None:
                session.completed_at = datetime.now(timezone.utc)
            session.end_reason = session.end_reason or "user_abort"
            session.end_decided_by = session.end_decided_by or "user"
            self.db.commit()
            self._clear_pipeline_cache(session.id)
        refreshed_session = self._get_session(session.id)
        self._schedule_history_report(refreshed_session)
        if self._is_report_ready(refreshed_session):
            return InterviewReportRead(
                answer_mode=self._session_answer_mode(refreshed_session),
                **refreshed_session.report.report_payload,
            )
        return InterviewReportRead(
            style=refreshed_session.style,
            answer_mode=self._session_answer_mode(refreshed_session),
            **self._history_report_payload(refreshed_session),
        )

    def get_report(self, session_id: int) -> InterviewReportRead:
        self._cleanup_expired_sessions()
        session = self._get_session(session_id)
        if self._refresh_history_audio_analysis(session):
            session = self._get_session(session_id)
        if not self._is_report_ready(session):
            self._ensure_history_report_pending(session)
            logger.info("report pending | session_id=%s", session.id)
            return InterviewReportRead(
                style=session.style,
                answer_mode=self._session_answer_mode(session),
                **self._history_report_payload(session),
            )
        logger.info("report fetched | session_id=%s", session.id)
        return InterviewReportRead(
            answer_mode=self._session_answer_mode(session),
            **session.report.report_payload,
        )

    def _is_archivable_session(self, session) -> bool:
        _ = session
        return True

    def list_history(self, user_id: int):
        self._cleanup_expired_sessions(user_id=user_id)
        sessions = [item for item in self.repo.list_completed_sessions(user_id) if self._is_archivable_session(item)]
        return [
            HistoryItem(
                session_id=item.id,
                title=item.title,
                position=item.position.name,
                style=item.style,
                answer_mode=self._session_answer_mode(item),
                status=item.status,
                total_score=item.report.total_score if item.report else None,
                report_ready=self._is_report_ready(item),
                created_at=item.created_at,
                completed_at=self._completed_at(item),
            )
            for item in sessions
        ]

    def get_history_detail(self, user_id: int, session_id: int) -> HistoryInterviewDetailRead:
        self._cleanup_expired_sessions(user_id=user_id)
        session = self._get_session(session_id)
        if session.user_id != user_id or session.status != InterviewStatus.completed or not self._is_archivable_session(session):
            raise AppException("Interview session not found", 404)
        if self._refresh_history_audio_analysis(session):
            session = self._get_session(session_id)

        report_payload = self._history_report_payload(session)
        ordered_questions = self._ordered_questions(session)
        question_meta = self._build_question_meta(ordered_questions)
        answers_by_question = {item.question_id: item for item in self._ordered_answers(session)}

        records = []
        for question in ordered_questions:
            answer = answers_by_question.get(question.id)
            score = answer.score if answer and answer.score else None
            meta = question_meta.get(question.id, {"round_no": question.turn_no, "counts_toward_total": True})
            records.append(
                HistoryQuestionRecord(
                    question_id=question.id,
                    answer_id=answer.id if answer else None,
                    turn_no=question.turn_no,
                    round_no=int(meta["round_no"]),
                    counts_toward_total=bool(meta["counts_toward_total"]),
                    category=question.category,
                    competency_code=question.competency_code,
                    question_text=question.question_text,
                    follow_up_reason=question.follow_up_reason,
                    follow_up_type=question.follow_up_type,
                    answer_mode=answer.answer_mode if answer else None,
                    audio_path=self._history_audio_url(answer),
                    audio_duration_seconds=self._history_audio_duration_seconds(answer) if answer and answer.answer_mode == AnswerMode.audio else None,
                    answer_text=(answer.answer_text or answer.asr_text) if answer else "",
                    asr_text=answer.asr_text if answer else "",
                    answered_at=answer.created_at if answer else None,
                    evaluation_ready=score is not None,
                    overall_score=score.overall_score if score else None,
                    text_scores=score.text_scores if score else {},
                    audio_scores=score.audio_scores if score and answer and answer.answer_mode == AnswerMode.audio else {},
                    audio_features=self._serialize_audio_features(answer.audio_features if answer and answer.answer_mode == AnswerMode.audio else None),
                    explanation=score.explanation if score else "",
                    suggestions=score.suggestions if score else [],
                )
            )

        return HistoryInterviewDetailRead(
            title=session.title,
            position=session.position.name,
            style=session.style,
            answer_mode=self._session_answer_mode(session),
            status=session.status,
            created_at=session.created_at,
            completed_at=self._completed_at(session),
            report_ready=self._is_report_ready(session),
            questions=records,
            **report_payload,
        )

    def process_pending_history_reports(self, limit: int = 3) -> int:
        processed = 0
        for session in self.repo.list_sessions_needing_report(limit=limit):
            if self._is_report_ready(session):
                continue
            self._schedule_history_report(session)

        now = datetime.now(timezone.utc)
        heartbeat_timeout_before = now - ANALYSIS_JOB_HEARTBEAT_TIMEOUT
        jobs = self.repo.list_due_analysis_jobs(
            now=now,
            heartbeat_timeout_before=heartbeat_timeout_before,
            limit=limit,
        )
        for job in jobs:
            if job.id in REPORT_REBUILDING_SESSIONS:
                continue
            REPORT_REBUILDING_SESSIONS.add(job.id)
            run_history_report_task(job.id)
            processed += 1
        return processed

    def delete_history(self, user_id: int, session_id: int) -> InterviewDiscardResult:
        self._cleanup_expired_sessions(user_id=user_id)
        session = self._get_session(session_id)
        if session.user_id != user_id or session.status != InterviewStatus.completed or not self._is_archivable_session(session):
            raise AppException("Interview session not found", 404)
        deleted = self.repo.delete_completed_session(session_id=session_id, user_id=user_id)
        if not deleted:
            raise AppException("Interview session not found", 404)
        self.db.commit()
        self._clear_pipeline_cache(session_id)
        logger.info("completed interview archive deleted | session_id=%s user_id=%s", session_id, user_id)
        return InterviewDiscardResult(session_id=session_id)

    def _get_session(self, session_id: int):
        session = self.repo.get_session(session_id)
        if not session:
            raise AppException("Interview session not found", 404)
        return session

    def _cleanup_expired_sessions(self, user_id: int | None = None) -> int:
        expires_before = datetime.now(timezone.utc) - timedelta(hours=SESSION_TTL_HOURS)
        deleted = self.repo.cleanup_expired_unfinished_sessions(expires_before=expires_before, user_id=user_id)
        if deleted:
            self.db.commit()
            logger.info(
                "expired unfinished interviews cleaned | user_id=%s deleted_count=%s ttl_hours=%s",
                user_id,
                deleted,
                SESSION_TTL_HOURS,
            )
        return deleted

    def _resume_summary(self, session) -> ResumeSummary | None:
        resume = getattr(session, "resume", None)
        if resume and getattr(resume, "parse", None):
            return ResumeSummary.model_validate(resume.parse.summary)
        return None

    def _resume_job_match(self, summary: ResumeSummary | None, role_code: str) -> ResumeJobMatch | None:
        if not summary:
            return None
        for item in summary.job_matches:
            if item.position_code == role_code:
                return item
        return summary.best_job_match

    def _build_resume_prompt_context(self, summary: ResumeSummary | None, role_code: str) -> dict | None:
        if not summary:
            return None
        job_match = self._resume_job_match(summary, role_code)
        return {
            "background": summary.background,
            "tech_stack": summary.tech_stack[:8],
            "highlights": summary.highlights[:4],
            "risk_points": summary.risk_points[:4],
            "years_of_experience": summary.years_of_experience,
            "overall_score": summary.overall_score,
            "resume_suggestions": summary.resume_suggestions[:3],
            "interview_focuses": summary.interview_focuses[:4],
            "current_job_match": job_match.model_dump() if job_match else None,
        }

    def _ordered_questions(self, session) -> list:
        return sorted(getattr(session, "questions", []) or [], key=lambda item: (item.turn_no, item.id))

    def _ordered_answers(self, session) -> list:
        return sorted(getattr(session, "answers", []) or [], key=lambda item: (item.turn_no, item.id))

    def _find_answer_for_question(self, session, question_id: int):
        for item in self._ordered_answers(session):
            if item.question_id == question_id:
                return item
        return None

    def _find_next_question(self, session, question_id: int):
        ordered_questions = self._ordered_questions(session)
        for index, item in enumerate(ordered_questions):
            if item.id == question_id:
                return ordered_questions[index + 1] if index + 1 < len(ordered_questions) else None
        return None

    def _answered_main_questions(self, session) -> list:
        question_map = {item.id: item for item in self._ordered_questions(session)}
        answered: list = []
        for item in self._ordered_answers(session):
            question = question_map.get(item.question_id)
            if question and question.category in MAIN_QUESTION_CATEGORIES:
                answered.append(item)
        return answered

    def _main_question_count(self, session) -> int:
        answered_count = len(self._answered_main_questions(session))
        return max(answered_count, int(getattr(session, "current_turn", 0) or 0))

    def _covered_main_competencies(self, session) -> set[str]:
        question_map = {item.id: item for item in self._ordered_questions(session)}
        competencies: set[str] = set()
        for answer in self._answered_main_questions(session):
            question = question_map.get(answer.question_id)
            if question and question.competency_code:
                competencies.add(question.competency_code)
        return competencies

    def _rolling_main_score(self, session, latest_question=None, latest_score: float | None = None) -> float | None:
        scores: list[float] = []
        latest_question_id = getattr(latest_question, "id", None)
        for answer in self._answered_main_questions(session):
            if latest_question_id is not None and answer.question_id == latest_question_id and latest_score is not None:
                scores.append(float(latest_score))
                continue
            if answer.score and answer.score.overall_score is not None:
                scores.append(float(answer.score.overall_score))
        if not scores:
            return None
        return round(sum(scores) / len(scores), 2)

    def _build_existing_submit_response(self, session, answer) -> SubmitAnswerResponse:
        evaluation = self._serialize_answer_evaluation(answer)
        return SubmitAnswerResponse(
            answer_id=answer.id,
            question_id=answer.question_id,
            evaluation_ready=evaluation is not None,
            evaluation=evaluation,
            next_action="completed" if session.status == InterviewStatus.completed else "awaiting_next_question",
            progress=self._build_progress(session),
            report_ready=session.status == InterviewStatus.completed,
            report_id=session.id if session.status == InterviewStatus.completed else None,
        )

    def _build_next_step_response(
        self,
        session,
        question,
        ordered_questions: list | None = None,
    ) -> InterviewNextStepResponse:
        serialized_question = self._serialize_question(session, question, ordered_questions)
        if question.category == QuestionCategory.wrap_up:
            next_action = "summary"
        elif question.category == QuestionCategory.opening:
            next_action = "opening"
        else:
            next_action = question.follow_up_type.value
        return InterviewNextStepResponse(
            next_action=next_action,
            next_question=serialized_question,
            progress=self._build_progress(session),
            next_question_preview=serialized_question.question_text,
            next_question_id=serialized_question.id,
        )

    def _serialize_answer_evaluation(self, answer) -> AnswerEvaluation | None:
        score = answer.score
        if not score:
            return None
        evidence = [RetrievalEvidence.model_validate(item) for item in (score.evidence or [])]
        audio_features = self._serialize_audio_features(answer.audio_features) or {"status": "unavailable"}
        debug = score.debug_payload or {}
        return AnswerEvaluation(
            answer_id=answer.id,
            question_id=answer.question_id,
            competency_code=score.competency_code,
            overall_score=score.overall_score,
            text_scores=score.text_scores,
            audio_scores=score.audio_scores,
            explanation=score.explanation,
            suggestions=score.suggestions,
            evidence=evidence,
            audio_features=AudioFeatureSummary(**audio_features),
            answer_text=getattr(answer, "answer_text", "") or "",
            asr_text=getattr(answer, "asr_text", "") or "",
            ai_generated=not debug.get("fallback_used", False),
            degraded=debug.get("fallback_used", False),
        )

    def _schedule_answer_scoring(self, background_tasks, session_id: int, answer_id: int) -> None:
        if background_tasks is None:
            return
        background_tasks.add_task(run_answer_scoring_task, session_id, answer_id)

    def _schedule_latest_missing_score(self, session, background_tasks) -> None:
        if background_tasks is None:
            return
        for answer in reversed(self._ordered_answers(session)):
            if not answer.score:
                self._schedule_answer_scoring(background_tasks, session.id, answer.id)
                return

    def _get_embedding_client(self):
        if self._embedding_client is None:
            self._embedding_client = get_embedding_client()
        return self._embedding_client

    def _get_pipeline_state(self, session) -> dict:
        state = QUESTION_PIPELINE_CACHE.setdefault(
            session.id,
            {
                "main_questions": {},
                "questions": {},
                "embeddings": {},
                "asked_questions": [],
                "covered_competencies": [],
                "updated_at": datetime.now(timezone.utc),
            },
        )
        self._sync_pipeline_context(session, state)
        if not state["main_questions"]:
            competencies = sorted(getattr(session.position, "competencies", []) or [], key=lambda item: item.weight, reverse=True)
            for competency in competencies:
                state["main_questions"][competency.code] = self._build_main_question_bucket(session, competency.code)
        return state

    def _sync_pipeline_context(self, session, state: dict) -> None:
        ordered_questions = self._ordered_questions(session)
        state["asked_questions"] = [item.question_text for item in ordered_questions if item.question_text]
        state["covered_competencies"] = list(
            dict.fromkeys(
                item.competency_code
                for item in ordered_questions
                if item.category in MAIN_QUESTION_CATEGORIES and item.competency_code
            )
        )
        state["updated_at"] = datetime.now(timezone.utc)

    def _clear_pipeline_cache(self, session_id: int) -> None:
        QUESTION_PIPELINE_CACHE.pop(session_id, None)

    def _clear_question_prefetch(self, session_id: int, question_id: int | None) -> None:
        if question_id is None:
            return
        session_state = QUESTION_PIPELINE_CACHE.get(session_id)
        if not session_state:
            return
        session_state.get("questions", {}).pop(question_id, None)

    def _answer_clause_count(self, answer_text: str) -> int:
        normalized = answer_text.replace("\n", "，")
        for marker in ["。", "！", "？", ";", "；", ","]:
            normalized = normalized.replace(marker, "，")
        return len([item.strip() for item in normalized.split("，") if item.strip()])

    def _is_substantive_answer(self, answer_text: str) -> bool:
        normalized = answer_text.strip()
        if not normalized or self._contains_confusion_signal(normalized) or self._is_low_signal_answer(normalized):
            return False
        clause_count = self._answer_clause_count(normalized)
        markers = ["负责", "方案", "取舍", "结果", "指标", "优化", "排查", "实现", "上线", "监控", "性能", "复盘"]
        marker_hits = sum(1 for marker in markers if marker in normalized)
        has_number = any(char.isdigit() for char in normalized)
        return len(normalized) >= 36 and (clause_count >= 2 or marker_hits >= 2 or has_number)

    def _build_main_question_bucket(self, session, competency_code: str) -> list[str]:
        bucket: list[str] = []
        used_questions = list(self._asked_main_questions(session, competency_code=competency_code))
        for index in range(WARMUP_MAIN_QUESTION_COUNT):
            try:
                question_text = self.seed_service.get_question_for_competency(
                    session.position.code,
                    competency_code,
                    used_questions=used_questions,
                    selector_seed=f"{session.id}:{competency_code}:warm:{index}",
                    style=self._session_style_code(session),
                )
            except TypeError:
                question_text = self.seed_service.get_question_for_competency(
                    session.position.code,
                    competency_code,
                    used_questions,
                )
            if question_text and question_text not in bucket:
                bucket.append(question_text)
                used_questions.append(question_text)
        return bucket

    def _normalize_similarity_text(self, text: str) -> str:
        return "".join(
            char.lower()
            for char in text.strip()
            if char.isalnum() or "\u4e00" <= char <= "\u9fff"
        )

    def _char_ngrams(self, text: str, size: int = 2) -> set[str]:
        normalized = self._normalize_similarity_text(text)
        if len(normalized) <= size:
            return {normalized} if normalized else set()
        return {normalized[index:index + size] for index in range(len(normalized) - size + 1)}

    def _lexical_similarity(self, left: str, right: str) -> float:
        left_ngrams = self._char_ngrams(left)
        right_ngrams = self._char_ngrams(right)
        if not left_ngrams or not right_ngrams:
            return 0.0
        union = left_ngrams | right_ngrams
        if not union:
            return 0.0
        return len(left_ngrams & right_ngrams) / len(union)

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = sum(a * a for a in left) ** 0.5
        right_norm = sum(b * b for b in right) ** 0.5
        if left_norm <= 0 or right_norm <= 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _embed_texts_cached(self, state: dict, texts: list[str]) -> dict[str, list[float]]:
        cache = state.setdefault("embeddings", {})
        normalized_pairs = [(text, self._normalize_similarity_text(text)) for text in texts if text and self._normalize_similarity_text(text)]
        missing = [normalized for _, normalized in normalized_pairs if normalized not in cache]
        if missing and not state.get("embedding_disabled"):
            try:
                embeddings = self._get_embedding_client().embed(missing)
                for normalized, embedding in zip(missing, embeddings):
                    cache[normalized] = embedding
            except Exception:
                logger.warning("prefetch embedding unavailable, fallback to lexical similarity", exc_info=True)
                state["embedding_disabled"] = True
        result: dict[str, list[float]] = {}
        for original, normalized in normalized_pairs:
            if normalized in cache:
                result[original] = cache[normalized]
        return result

    def _max_similarity_to_history(self, state: dict, text: str, history_questions: list[str]) -> float:
        if not history_questions:
            return 0.0
        embeddings = self._embed_texts_cached(state, [text, *history_questions])
        if text in embeddings:
            candidate_embedding = embeddings[text]
            similarities = [
                self._cosine_similarity(candidate_embedding, embeddings[history])
                for history in history_questions
                if history in embeddings
            ]
            if similarities:
                return max(similarities)
        return max(self._lexical_similarity(text, history) for history in history_questions)

    def _prefetch_strategy(self, session, question, partial_answer: str) -> dict:
        score_payload = self.scoring_service.score_answer_fast(
            role_code=session.position.code,
            competency_code=question.competency_code,
            question_text=question.question_text,
            answer_text=partial_answer,
            evidence=[],
            difficulty=self._session_style_code(session),
        )
        overall_score = score_payload["overall_score"]
        follow_up_type = FollowUpType.deepen
        reason = "当前题分数落在追问窗口内，允许继续追问。"
        next_competency = question.competency_code
        if overall_score < 55:
            follow_up_type = FollowUpType.switch_dimension
            reason = "当前题实时分数偏低，继续追问收益不高，直接切换能力点。"
            next_competency = self._pick_next_competency(session, current_code=question.competency_code)
        elif overall_score > 75:
            follow_up_type = FollowUpType.switch_dimension
            reason = "当前题实时分数较高，优先切换能力点，保持面试节奏。"
            next_competency = self._pick_next_competency(session, current_code=question.competency_code)
        elif self._contains_confusion_signal(partial_answer):
            follow_up_type = FollowUpType.redirect
            reason = "候选人当前表达了困惑，需要缩小范围重新提问。"
        elif self._is_low_signal_answer(partial_answer):
            follow_up_type = FollowUpType.redirect
            reason = "当前回答信息量不足，先缩小问题范围，引导候选人把核心做法说清楚。"
        elif self._is_substantive_answer(partial_answer):
            follow_up_type = FollowUpType.deepen
            reason = "当前回答已有基础内容，可以围绕做法和结果继续深挖。"
        return {
            "overall_score": overall_score,
            "follow_up_type": follow_up_type,
            "reason": reason,
            "next_competency": next_competency,
            "score_payload": score_payload,
        }

    def _build_answer_summary_fallback(self, question, partial_answer: str) -> str:
        normalized = partial_answer.strip()
        if not normalized:
            return f"当前正在围绕“{question.question_text}”作答，系统暂时只有预热题池候选。"
        if self._contains_confusion_signal(normalized):
            return "候选人明确表示对题意不太理解，当前更适合先缩小问题范围。"
        fragments = [item.strip() for item in normalized.replace("\n", "，").split("，") if item.strip()]
        snippet = "；".join(fragments[:2]) if fragments else normalized[:80]
        if self._is_substantive_answer(normalized):
            return f"候选人已经提到：{snippet}。下一步应优先追问最关键的一个点。"
        return f"候选人当前只零散提到：{snippet}。还需要更聚焦地确认核心做法和有效结果。"

    def _build_seed_prefetch_candidates(self, session, question, partial_answer: str) -> list[dict]:
        state = self._get_pipeline_state(session)
        normalized = partial_answer.strip()
        confused = self._contains_confusion_signal(normalized) if normalized else False
        low_signal = self._is_low_signal_answer(normalized) if normalized else False
        substantive = self._is_substantive_answer(normalized) if normalized else False
        next_competency = self._pick_next_competency(session, current_code=question.competency_code)
        candidates: list[dict] = []
        confidence_map = {"redirect": 0.68, "deepen": 0.64, "credibility": 0.48}
        credibility_allowed = self._should_use_credibility_follow_up(
            {
                "credibility_risk": substantive and not confused and not low_signal,
                "confused": confused,
                "low_signal": low_signal,
            },
            normalized,
            low_credibility=True,
            substantive_answer=substantive,
            previous_follow_up_types=self._round_follow_up_types(session, question),
            session=session,
        )

        if hasattr(self.seed_service, "build_follow_up_candidates"):
            try:
                follow_up_candidates = self.seed_service.build_follow_up_candidates(
                    session.position.code,
                    question.competency_code,
                    question.question_text,
                    normalized,
                    style=self._session_style_code(session),
                )
            except TypeError:
                follow_up_candidates = self.seed_service.build_follow_up_candidates(
                    session.position.code,
                    question.competency_code,
                    question.question_text,
                    normalized,
                )
        else:
            follow_up_candidates = [
                {
                    "question_text": self._seed_follow_up_text(
                        session,
                        follow_up_type,
                        question.competency_code,
                        normalized,
                    ),
                    "follow_up_type": follow_up_type,
                    "competency_code": question.competency_code,
                    "angle": "题库模板",
                    "source": "seed",
                }
                for follow_up_type in ("deepen", "redirect", "credibility")
            ]

        for item in follow_up_candidates:
            if item["follow_up_type"] == "credibility" and not credibility_allowed:
                continue
            confidence = confidence_map.get(item["follow_up_type"], 0.58)
            if confused and item["follow_up_type"] == "redirect":
                confidence += 0.18
            elif substantive and item["follow_up_type"] == "deepen":
                confidence += 0.12
            candidates.append(
                {
                    "question_text": item["question_text"],
                    "follow_up_type": item["follow_up_type"],
                    "competency_code": item["competency_code"],
                    "category": QuestionCategory.follow_up.value,
                    "angle": item.get("angle", "题库预热"),
                    "confidence": round(min(confidence, 0.96), 2),
                    "source": item.get("source", "seed"),
                    "referenced_facts": [],
                }
            )

        warm_main_questions = state["main_questions"].get(next_competency, [])
        if session.current_turn < session.max_questions:
            for index, question_text in enumerate(warm_main_questions[:2]):
                base_confidence = 0.7 if not normalized else 0.78
                if substantive:
                    base_confidence = 0.9
                elif confused:
                    base_confidence = 0.52
                candidates.append(
                    {
                        "question_text": question_text,
                        "follow_up_type": FollowUpType.switch_dimension.value,
                        "competency_code": next_competency,
                        "category": QuestionCategory.technical.value,
                        "angle": f"下一能力点备选 {index + 1}",
                        "confidence": round(base_confidence - index * 0.04, 2),
                        "source": "warmup_main",
                        "referenced_facts": [],
                    }
                )

        if normalized and confused:
            candidates.append(
                {
                    "question_text": self._build_clarified_follow_up_draft(question.question_text),
                    "follow_up_type": FollowUpType.redirect.value,
                    "competency_code": question.competency_code,
                    "category": QuestionCategory.follow_up.value,
                    "angle": "澄清题意",
                    "confidence": 0.94,
                    "source": "prefetch_runtime",
                    "referenced_facts": [],
                }
            )
        return candidates

    def _normalize_prefetch_candidate(self, question, item: dict, next_competency: str) -> dict | None:
        question_text = str(item.get("question_text") or "").strip()
        follow_up_type = str(item.get("follow_up_type") or "").strip() or FollowUpType.deepen.value
        if not question_text or follow_up_type not in {item.value for item in FollowUpType}:
            return None
        competency_code = str(item.get("competency_code") or "").strip()
        if not competency_code:
            competency_code = next_competency if follow_up_type == FollowUpType.switch_dimension.value else question.competency_code
        category = QuestionCategory.technical.value if follow_up_type == FollowUpType.switch_dimension.value else QuestionCategory.follow_up.value
        referenced_facts = [str(value).strip() for value in item.get("referenced_facts", []) if str(value).strip()]
        return {
            "question_text": question_text,
            "follow_up_type": follow_up_type,
            "competency_code": competency_code,
            "category": category,
            "angle": str(item.get("angle") or "实时生成").strip() or "实时生成",
            "confidence": round(float(item.get("confidence") or 0.58), 2),
            "source": str(item.get("source") or "llm_prefetch").strip() or "llm_prefetch",
            "referenced_facts": referenced_facts,
        }

    def _run_prefetch_prompt(self, session, question, partial_answer: str, strategy: dict, entry: dict, warmup_candidates: list[dict]) -> tuple[dict, bool]:
        fallback_result = {
            "answer_summary": self._build_answer_summary_fallback(question, partial_answer),
            "candidates": warmup_candidates[:3],
        }
        if len(partial_answer.strip()) < PREFETCH_MIN_ANSWER_CHARS:
            return fallback_result, True
        prompt_result, fallback_used = self.prompt_service.run_json_prompt(
            "prefetch_follow_up",
            {
                "task_context": {
                    "position": session.position.name,
                    "role_code": session.position.code,
                    "style": self._session_style_code(session),
                    "difficulty": self._difficulty_context(session),
                    "competency_code": question.competency_code,
                    "recommended_follow_up_type": strategy["follow_up_type"].value,
                    "stage": "prefetch_follow_up",
                },
                "conversation_context": {
                    "current_question": question.question_text,
                    "partial_answer": partial_answer,
                    "asked_questions": self._get_pipeline_state(session)["asked_questions"],
                    "covered_competencies": self._get_pipeline_state(session)["covered_competencies"],
                    "avoid_repetition": self._get_pipeline_state(session)["asked_questions"],
                    "current_best_question": (entry.get("current_best") or {}).get("question_text"),
                    "reason": strategy["reason"],
                },
                "retrieval_context": [],
                "draft": {
                    "warmup_candidates": [
                        {
                            "question_text": item["question_text"],
                            "follow_up_type": item["follow_up_type"],
                            "competency_code": item["competency_code"],
                            "angle": item.get("angle", "题库预热"),
                            "source": item.get("source", "seed"),
                        }
                        for item in warmup_candidates[:4]
                    ],
                },
            },
            fallback_result=fallback_result,
        )
        return prompt_result, fallback_used

    def _run_required_prompt(
        self,
        name: str,
        variables: dict,
        *,
        error_message: str,
        fallback_result: dict | None = None,
    ) -> tuple[dict, bool]:
        try:
            return self.prompt_service.run_json_prompt(name, variables, fallback_result=fallback_result)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("required prompt failed | name=%s", name)
            raise AppException(error_message, 502) from exc

    def _candidate_quality_score(self, candidate: dict, answer_summary: str, strategy: dict, current_best: dict | None, state: dict) -> float:
        score = 0.0
        referenced_facts = [fact for fact in candidate.get("referenced_facts", []) if fact]
        if referenced_facts:
            score += 0.40
        if candidate.get("follow_up_type") == strategy["follow_up_type"].value:
            score += 0.15
        if 12 <= len(candidate.get("question_text", "")) <= 70:
            score += 0.10
        if strategy["follow_up_type"] == FollowUpType.credibility and any(word in answer_summary for word in ["负责", "结果", "指标", "验证"]):
            score += 0.25
        elif strategy["follow_up_type"] == FollowUpType.deepen and any(word in answer_summary for word in ["做法", "方案", "取舍", "结果"]):
            score += 0.25
        elif strategy["follow_up_type"] == FollowUpType.redirect and any(word in answer_summary for word in ["不理解", "缩小范围", "题意"]):
            score += 0.25
        elif strategy["follow_up_type"] == FollowUpType.switch_dimension:
            score += 0.25
        lowered_question = candidate.get("question_text", "")
        if any(marker in lowered_question for marker in GENERIC_FOLLOW_UP_MARKERS):
            score -= 0.30
        if current_best:
            similarity = self._max_similarity_to_history(state, candidate["question_text"], [current_best.get("question_text", "")])
            if similarity > SEMANTIC_SOFT_THRESHOLD:
                score -= 0.20
        score += float(candidate.get("confidence") or 0.0) * 0.30
        return round(score, 2)

    def _filter_and_rank_prefetch_candidates(self, state: dict, entry: dict, candidates: list[dict], answer_summary: str, strategy: dict) -> tuple[list[dict], int]:
        history_questions = state.get("asked_questions", [])
        current_best = entry.get("current_best")
        accepted: list[dict] = []
        rejected_count = 0
        seen: set[str] = set()
        for candidate in candidates:
            key = f"{candidate['follow_up_type']}::{candidate['question_text']}"
            if key in seen:
                rejected_count += 1
                continue
            seen.add(key)
            similarity = self._max_similarity_to_history(state, candidate["question_text"], history_questions)
            if similarity > SEMANTIC_DUPLICATE_THRESHOLD:
                rejected_count += 1
                continue
            candidate["quality_score"] = self._candidate_quality_score(candidate, answer_summary, strategy, current_best, state)
            if similarity > SEMANTIC_SOFT_THRESHOLD:
                candidate["quality_score"] = round(candidate["quality_score"] - 0.12, 2)
            accepted.append(candidate)
        accepted.sort(key=lambda item: (item.get("quality_score") or 0.0, item.get("confidence") or 0.0), reverse=True)
        return accepted, rejected_count

    def _build_prefetch_candidates(self, session, question, partial_answer: str) -> dict:
        state = self._get_pipeline_state(session)
        entry = state.get("questions", {}).get(question.id, {})
        strategy = self._prefetch_strategy(session, question, partial_answer or question.question_text[:0]) if partial_answer else {
            "overall_score": None,
            "follow_up_type": FollowUpType.switch_dimension,
            "reason": "当前仅做预热。",
            "next_competency": self._pick_next_competency(session, current_code=question.competency_code),
        }
        warmup_candidates = self._build_seed_prefetch_candidates(session, question, partial_answer)
        answer_summary = self._build_answer_summary_fallback(question, partial_answer)
        generated_candidates: list[dict] = []
        if partial_answer and strategy["follow_up_type"] != FollowUpType.switch_dimension:
            prompt_result, _ = self._run_prefetch_prompt(session, question, partial_answer, strategy, entry, warmup_candidates)
            answer_summary = str(prompt_result.get("answer_summary") or answer_summary).strip() or answer_summary
            for item in prompt_result.get("candidates", []):
                normalized = self._normalize_prefetch_candidate(question, item, strategy["next_competency"])
                if normalized:
                    generated_candidates.append(normalized)
        elif partial_answer and strategy["follow_up_type"] == FollowUpType.switch_dimension:
            answer_summary = f"当前回答实时综合分为 {strategy['overall_score']} 分，系统将直接切换到下一个能力点。"

        combined_candidates = warmup_candidates if strategy["follow_up_type"] == FollowUpType.switch_dimension else [*generated_candidates, *warmup_candidates]
        if strategy["follow_up_type"] == FollowUpType.switch_dimension:
            combined_candidates = [item for item in combined_candidates if item["follow_up_type"] == FollowUpType.switch_dimension.value]
        ranked_candidates, rejected_count = self._filter_and_rank_prefetch_candidates(state, entry, combined_candidates, answer_summary, strategy)
        current_best = ranked_candidates[0] if ranked_candidates else entry.get("current_best")
        previous_quality = float((entry.get("current_best") or {}).get("quality_score") or 0.0)
        best_quality = float((current_best or {}).get("quality_score") or 0.0)
        replacement_happened = bool(current_best and (entry.get("current_best") is None or best_quality >= previous_quality + BUFFER_REPLACE_MARGIN))
        if not replacement_happened and entry.get("current_best"):
            current_best = entry.get("current_best")
            best_quality = previous_quality
        return {
            "answer_summary": answer_summary,
            "strategy": strategy,
            "candidates": ranked_candidates[:5],
            "current_best": current_best,
            "buffer_quality": round(best_quality, 2) if current_best else None,
            "replacement_happened": replacement_happened,
            "rejected_count": rejected_count,
        }

    def _ensure_question_pipeline_state(self, session, question) -> dict:
        state = self._get_pipeline_state(session)
        if question.id not in state["questions"]:
            prefetch_payload = self._build_prefetch_candidates(session, question, "")
            state["questions"][question.id] = {
                "question_id": question.id,
                "partial_answer": "",
                "version": 0,
                "status": "warmup_ready",
                "based_on": "预热题池",
                "updated_at": datetime.now(timezone.utc),
                **prefetch_payload,
            }
        return state

    def _pick_prefetched_candidate(self, session, question, follow_up_type: FollowUpType, competency_code: str) -> dict | None:
        session_state = QUESTION_PIPELINE_CACHE.get(session.id)
        if not session_state:
            return None
        question_id = getattr(question, "id", None)
        if question_id is None:
            return None
        entry = session_state.get("questions", {}).get(question_id)
        if not entry:
            return None
        current_best = entry.get("current_best")
        if current_best and current_best.get("follow_up_type") == follow_up_type.value and current_best.get("competency_code") == competency_code:
            return current_best
        candidates = entry.get("candidates", [])
        for item in candidates:
            if item.get("follow_up_type") != follow_up_type.value:
                continue
            if item.get("competency_code") != competency_code:
                continue
            if follow_up_type == FollowUpType.switch_dimension and item.get("category") != QuestionCategory.technical.value:
                continue
            if follow_up_type != FollowUpType.switch_dimension and item.get("category") != QuestionCategory.follow_up.value:
                continue
            return item
        return None

    def _create_prefetched_question(self, session, question, follow_up_type: FollowUpType, reason: str, competency_code: str) -> int | None:
        if follow_up_type == FollowUpType.switch_dimension and session.current_turn >= session.max_questions:
            return None
        candidate = self._pick_prefetched_candidate(session, question, follow_up_type, competency_code)
        if not candidate:
            return None
        next_question = self.repo.create_question(
            session_id=session.id,
            turn_no=self._next_turn_no(session),
            category=QuestionCategory.follow_up if follow_up_type != FollowUpType.switch_dimension else QuestionCategory.technical,
            competency_code=competency_code,
            question_text=candidate["question_text"],
            follow_up_reason=f"{reason}（使用预取候选）",
            follow_up_type=follow_up_type,
            evidence_summary=(
                f"backend=prefetch; prompt_fallback=True; evidence_count=0; competency={competency_code}; "
                f"source={candidate['source']}; confidence={candidate['confidence']}; quality={candidate.get('quality_score')}"
            ),
        )
        previous_question_id = getattr(question, "id", None)
        if follow_up_type == FollowUpType.switch_dimension:
            session.current_turn += 1
            session.status = InterviewStatus.technical_question
        else:
            session.status = InterviewStatus.deep_follow_up
        self._clear_question_prefetch(session.id, previous_question_id)
        self._ensure_question_pipeline_state(session, next_question)
        logger.info(
            "prefetched candidate consumed | session_id=%s previous_question_id=%s next_question_id=%s follow_up_type=%s competency_code=%s source=%s confidence=%s quality=%s",
            session.id,
            previous_question_id,
            next_question.id,
            follow_up_type.value,
            competency_code,
            candidate["source"],
            candidate["confidence"],
            candidate.get("quality_score"),
        )
        return next_question.id

    def _prepare_next_question_context(self, session, question, answer) -> tuple[str, dict, list[RetrievalEvidence], str]:
        audio_path = self._resolve_answer_audio_path(answer)
        answer_text = self._ensure_answer_text(answer, audio_path)
        retrieval = self.retrieval_service.retrieve_with_meta(
            query=f"{session.position.code} {question.competency_code} {question.question_text} {answer_text}",
            role_code=session.position.code,
            profile_name="answer_analysis",
        )
        score_payload = self.scoring_service.score_answer_fast(
            role_code=session.position.code,
            competency_code=question.competency_code,
            question_text=question.question_text,
            answer_text=answer_text,
            evidence=retrieval.evidence,
            difficulty=self._session_style_code(session),
        )
        return answer_text, score_payload, retrieval.evidence, retrieval.backend

    def _seed_opening_question(self, session, summary: ResumeSummary | None) -> tuple[str, str]:
        job_match = self._resume_job_match(summary, session.position.code)
        kwargs = {
            "used_questions": self._asked_main_questions(session),
            "selector_seed": f"{session.id}:opening",
            "projects": job_match.matched_projects if job_match else (summary.project_experiences if summary else []),
            "interview_focuses": job_match.interview_focuses if job_match else (summary.interview_focuses if summary else []),
            "style": self._session_style_code(session),
        }
        try:
            return self.seed_service.get_opening_question(
                session.position.code,
                summary.highlights if summary else [],
                summary.risk_points if summary else [],
                **kwargs,
            )
        except TypeError:
            return self.seed_service.get_opening_question(
                session.position.code,
                summary.highlights if summary else [],
                summary.risk_points if summary else [],
                kwargs["used_questions"],
            )

    def _seed_main_question(self, session, competency_code: str, next_turn_no: int) -> str:
        kwargs = {
            "used_questions": self._asked_main_questions(session, competency_code=competency_code),
            "selector_seed": f"{session.id}:{next_turn_no}:{competency_code}",
            "style": self._session_style_code(session),
        }
        try:
            return self.seed_service.get_question_for_competency(
                session.position.code,
                competency_code,
                **kwargs,
            )
        except TypeError:
            return self.seed_service.get_question_for_competency(
                session.position.code,
                competency_code,
                kwargs["used_questions"],
            )

    def _seed_follow_up_text(self, session, follow_up_type: str, competency_code: str, answer_text: str) -> str:
        try:
            return self.seed_service.get_follow_up_question(
                session.position.code,
                follow_up_type,
                competency_code,
                answer_text,
                style=self._session_style_code(session),
            )
        except TypeError:
            return self.seed_service.get_follow_up_question(
                session.position.code,
                follow_up_type,
                competency_code,
                answer_text,
            )

    def _resolve_answer_audio_path(self, answer) -> Path | None:
        if not answer.audio_path:
            return None
        settings = getattr(self, "settings", None) or get_settings()
        target = settings.upload_dir.parent / answer.audio_path
        return target if target.exists() else None

    def _session_answer_mode(self, session) -> AnswerMode:
        answer_mode = getattr(session, "answer_mode", None)
        if answer_mode:
            return answer_mode
        if normalize_difficulty(getattr(getattr(session, "style", None), "value", getattr(session, "style", None))) == "hard":
            legacy_style = getattr(getattr(session, "style", None), "value", getattr(session, "style", None))
            if legacy_style == "pressure":
                return AnswerMode.audio
        if getattr(getattr(session, "style", None), "value", getattr(session, "style", None)) == "pressure":
            return AnswerMode.audio
        return AnswerMode.text

    def _session_style_code(self, session) -> str:
        raw_style = getattr(getattr(session, "style", None), "value", getattr(session, "style", None))
        return normalize_difficulty(raw_style)

    def _difficulty_context(self, session) -> dict:
        profile = get_difficulty_profile(self._session_style_code(session))
        return {
            "code": profile.code,
            "label": profile.label,
            "audience_hint": profile.audience_hint,
            "opening_focus": profile.opening_focus,
            "main_focus": profile.main_focus,
            "follow_up_focus": profile.follow_up_focus,
            "prompt_hint": profile.prompt_hint,
        }

    def _ensure_answer_text(self, answer, audio_path: Path | None = None) -> str:
        answer_text = (answer.answer_text or answer.asr_text or "").strip()
        if answer_text:
            if not answer.answer_text and answer.asr_text:
                answer.answer_text = answer.asr_text
                self.db.flush()
            return answer_text
        if answer.answer_mode != AnswerMode.audio:
            return ""
        if audio_path is None:
            audio_path = self._resolve_answer_audio_path(answer)
        if audio_path is None:
            raise AppException("Audio file not found", 404)
        asr_text = self.speech_service.transcribe(audio_path).strip()
        answer.asr_text = asr_text
        if not answer.answer_text:
            answer.answer_text = asr_text
        self.db.flush()
        return (answer.answer_text or answer.asr_text).strip()

    def _replace_pending_audio_answer_if_needed(self, existing_answer, payload: SubmitAnswerRequest) -> bool | None:
        if payload.answer_mode != AnswerMode.audio:
            return None
        if getattr(existing_answer, "answer_mode", None) != AnswerMode.audio:
            return None
        if getattr(existing_answer, "score", None) is not None:
            return None
        current_text = ((getattr(existing_answer, "answer_text", None) or "") + (getattr(existing_answer, "asr_text", None) or "")).strip()
        if current_text:
            return None
        if not payload.audio_file_id:
            return None

        audio_path = self.settings.upload_dir / "audio" / payload.audio_file_id
        if not audio_path.exists():
            raise AppException("Audio file not found", 404)

        existing_answer.audio_path = str(audio_path.relative_to(self.settings.upload_dir.parent))
        existing_answer.answer_text = payload.text_answer.strip()
        existing_answer.asr_text = ""
        self.db.commit()
        logger.info(
            "pending audio answer replaced with new upload | answer_id=%s audio_path=%s",
            existing_answer.id,
            existing_answer.audio_path,
        )
        return True

    def _persist_answer_evaluation(self, session, answer, force: bool = False) -> AnswerEvaluation | None:
        existing = self._serialize_answer_evaluation(answer)
        if existing is not None and not force:
            return existing

        question = answer.question or self.repo.get_question(answer.question_id)
        if not question:
            raise AppException("Question not found", 404)
        audio_path = self._resolve_answer_audio_path(answer)
        answer_text = self._ensure_answer_text(answer, audio_path)
        retrieval = self.retrieval_service.retrieve_with_meta(
            query=f"{session.position.code} {question.competency_code} {question.question_text} {answer_text}",
            role_code=session.position.code,
            profile_name="answer_scoring",
        )
        score_payload, features, debug_payload = self.scoring_service.score_answer(
            role_code=session.position.code,
            competency_code=question.competency_code,
            question_text=question.question_text,
            answer_text=answer_text,
            evidence=retrieval.evidence,
            audio_path=audio_path,
            retrieval_backend=retrieval.backend,
            resume_summary=self._resume_summary(session),
            difficulty=self._session_style_code(session),
        )
        self.repo.upsert_audio_features(answer_id=answer.id, **features)
        self.repo.upsert_score(
            answer_id=answer.id,
            competency_code=score_payload["competency_code"],
            overall_score=score_payload["overall_score"],
            text_scores=score_payload["text_scores"],
            audio_scores=score_payload["audio_scores"],
            explanation=score_payload["explanation"],
            suggestions=score_payload["suggestions"],
            evidence=[item.model_dump() for item in retrieval.evidence],
            debug_payload=debug_payload,
        )
        self.db.commit()
        refreshed_answer = self.repo.get_answer(answer.id)
        logger.info(
            "answer evaluation persisted asynchronously | session_id=%s answer_id=%s retrieval_backend=%s evidence_count=%s",
            session.id,
            answer.id,
            retrieval.backend,
            len(retrieval.evidence),
        )
        return self._serialize_answer_evaluation(refreshed_answer)

    def _should_recover_audio_evaluation(self, answer) -> bool:
        if not answer or answer.answer_mode != AnswerMode.audio or not answer.score:
            return False
        if self._has_legacy_audio_analysis_signature(answer):
            return self._resolve_answer_audio_path(answer) is not None
        audio_scores = answer.score.audio_scores or {}
        audio_feature_status = getattr(answer.audio_features, "status", None)
        if audio_scores.get("status") == "available" and audio_feature_status == "available":
            return False
        return self._resolve_answer_audio_path(answer) is not None

    def _has_legacy_audio_analysis_signature(self, answer) -> bool:
        audio_features = getattr(answer, "audio_features", None)
        if getattr(audio_features, "status", None) != "available":
            return False
        pause_ratio = getattr(audio_features, "pause_ratio", None)
        voiced_ratio = getattr(audio_features, "voiced_ratio", None)
        speech_rate = getattr(audio_features, "speech_rate", None)
        if not all(isinstance(value, (int, float)) for value in (pause_ratio, voiced_ratio, speech_rate)):
            return False
        return (
            abs(float(pause_ratio) - 25.0) <= 1.5
            and abs(float(voiced_ratio) - 75.0) <= 1.5
            and float(speech_rate) >= 20.0
        )

    def _recover_history_audio_scores(self, session) -> bool:
        recovered = False
        for answer in self._ordered_answers(session):
            if not self._should_recover_audio_evaluation(answer):
                continue
            audio_path = self._resolve_answer_audio_path(answer)
            if audio_path is None:
                continue
            try:
                features = analyze_audio(audio_path)
                if features.get("status") != "available":
                    continue
                audio_scores = map_audio_scores(features)
                competency_code = getattr(
                    answer.score,
                    "competency_code",
                    getattr(getattr(answer, "question", None), "competency_code", ""),
                )
                self.repo.upsert_audio_features(answer_id=answer.id, **features)
                self.repo.upsert_score(
                    answer_id=answer.id,
                    competency_code=competency_code,
                    overall_score=answer.score.overall_score,
                    text_scores=answer.score.text_scores,
                    audio_scores=audio_scores,
                    explanation=answer.score.explanation,
                    suggestions=answer.score.suggestions,
                    evidence=getattr(answer.score, "evidence", []) or [],
                    debug_payload=getattr(answer.score, "debug_payload", {}) or {},
                )
                recovered = True
                self.db.commit()
                logger.info(
                    "history audio evaluation recovered | session_id=%s answer_id=%s",
                    session.id,
                    answer.id,
                )
            except Exception:
                self.db.rollback()
                logger.exception(
                    "history audio evaluation recovery failed | session_id=%s answer_id=%s",
                    session.id,
                    getattr(answer, "id", None),
                )
        return recovered

    def _refresh_history_audio_analysis(self, session) -> bool:
        if session.status != InterviewStatus.completed:
            return False
        if not self._recover_history_audio_scores(session):
            return False
        refreshed_session = self._get_session(session.id)
        self._build_report(refreshed_session)
        logger.info("history audio analysis refreshed | session_id=%s", session.id)
        return True

    def _ensure_session_scores(self, session) -> None:
        missing_answer_ids = [item.id for item in self._ordered_answers(session) if not item.score]
        for answer_id in missing_answer_ids:
            refreshed_session = self._get_session(session.id)
            answer = self.repo.get_answer(answer_id)
            if not answer:
                continue
            self._persist_answer_evaluation(refreshed_session, answer)

    def _build_question_meta(self, ordered_questions: list) -> dict[int, dict[str, int | bool]]:
        meta: dict[int, dict[str, int | bool]] = {}
        round_no = 0
        for item in ordered_questions:
            counts_toward_total = item.category in MAIN_QUESTION_CATEGORIES
            if counts_toward_total:
                round_no += 1
            meta[item.id] = {
                "round_no": round_no or 1,
                "counts_toward_total": counts_toward_total,
            }
        return meta

    def _serialize_question(self, session, question, ordered_questions: list | None = None) -> InterviewQuestionRead:
        ordered_questions = ordered_questions or self._ordered_questions(session)
        meta = self._build_question_meta(ordered_questions)[question.id]
        return InterviewQuestionRead(
            id=question.id,
            turn_no=question.turn_no,
            round_no=int(meta["round_no"]),
            counts_toward_total=bool(meta["counts_toward_total"]),
            category=question.category,
            competency_code=question.competency_code,
            question_text=question.question_text,
            follow_up_reason=question.follow_up_reason,
            follow_up_type=question.follow_up_type,
            evidence_summary=question.evidence_summary,
        )

    def _build_progress(self, session) -> InterviewProgress:
        settings = getattr(self, "settings", None) or get_settings()
        min_questions = getattr(session, "min_questions", None)
        if min_questions is None:
            min_questions = getattr(settings, "dynamic_interview_min_questions", get_settings().dynamic_interview_min_questions)
        max_questions = getattr(session, "max_questions", None)
        if max_questions is None:
            max_questions = getattr(settings, "dynamic_interview_max_questions", get_settings().dynamic_interview_max_questions)
        return InterviewProgress(
            current_round=session.current_turn,
            min_rounds=int(min_questions),
            max_rounds=int(max_questions),
            total_questions_asked=len(self._ordered_questions(session)),
            can_finish_early=session.current_turn >= int(min_questions),
        )

    def _completed_at(self, session) -> datetime | None:
        if session.completed_at:
            return session.completed_at
        if session.report:
            return session.report.created_at
        return None

    def _report_payload(self, session) -> dict:
        payload = getattr(getattr(session, "report", None), "report_payload", None)
        return payload if isinstance(payload, dict) else {}

    def _latest_analysis_job(self, session):
        analysis_jobs = getattr(session, "analysis_jobs", None)
        if analysis_jobs:
            return analysis_jobs[-1]
        return self.repo.get_latest_analysis_job(session.id)

    def _analysis_fingerprint(self, session) -> str:
        payload = {
            "analysis_job_version": ANALYSIS_JOB_VERSION,
            "session_id": session.id,
            "style": getattr(session.style, "value", session.style),
            "answer_mode": getattr(session.answer_mode, "value", session.answer_mode),
            "questions": [
                {
                    "id": item.id,
                    "turn_no": item.turn_no,
                    "category": getattr(item.category, "value", item.category),
                    "competency_code": item.competency_code,
                    "question_text": item.question_text,
                }
                for item in self._ordered_questions(session)
            ],
            "answers": [
                {
                    "id": item.id,
                    "question_id": item.question_id,
                    "turn_no": item.turn_no,
                    "answer_mode": getattr(item.answer_mode, "value", item.answer_mode),
                    "answer_text": item.answer_text or "",
                    "asr_text": item.asr_text or "",
                    "audio_path": item.audio_path or "",
                }
                for item in self._ordered_answers(session)
            ],
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _analysis_retry_at(self, retry_count: int, now: datetime) -> datetime | None:
        if retry_count >= len(ANALYSIS_JOB_RETRY_DELAYS):
            return None
        return now + ANALYSIS_JOB_RETRY_DELAYS[retry_count]

    def _pending_summary_for_job(self, job) -> str:
        status = getattr(job, "status", None)
        if status == AnalysisJobStatus.failed:
            return "AI 分析暂时遇到问题，系统会自动重试。"
        if status == AnalysisJobStatus.dead:
            return "AI 分析多次失败，已停止自动重试。"
        return "AI 正在分析这场面试，报告生成后会自动显示。"

    def _pending_level_for_job(self, job) -> str:
        status = getattr(job, "status", None)
        if status == AnalysisJobStatus.failed:
            return "重试中"
        if status == AnalysisJobStatus.dead:
            return "分析失败"
        return REPORT_PENDING_LEVEL

    def _pending_status_for_job(self, job) -> str:
        status = getattr(job, "status", None)
        if isinstance(status, AnalysisJobStatus):
            return status.value
        if isinstance(status, str) and status:
            return status
        return REPORT_PENDING_STATUS

    def _pending_started_at(self, session, started_at: datetime | None = None) -> datetime:
        if started_at is not None:
            return started_at
        payload = self._report_payload(session)
        raw_started_at = payload.get("analysis_started_at")
        if isinstance(raw_started_at, str):
            try:
                return datetime.fromisoformat(raw_started_at)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def _build_analysis_job_payload(self, session, fingerprint: str, version: int) -> dict:
        return {
            "session_id": session.id,
            "fingerprint": fingerprint,
            "version": version,
            "analysis_job_version": ANALYSIS_JOB_VERSION,
        }

    def _ensure_analysis_job(self, session):
        if session.status != InterviewStatus.completed:
            return None
        fingerprint = self._analysis_fingerprint(session)
        latest_job = self._latest_analysis_job(session)
        if latest_job and latest_job.fingerprint == fingerprint:
            if latest_job.status == AnalysisJobStatus.success and not self._is_report_ready(session):
                pass
            else:
                return latest_job
        next_version = (latest_job.version + 1) if latest_job else 1
        try:
            job = self.repo.create_analysis_job(
                session_id=session.id,
                status=AnalysisJobStatus.pending,
                version=next_version,
                retry_count=0,
                max_retries=len(ANALYSIS_JOB_RETRY_DELAYS) + 1,
                current_stage="queued",
                next_retry_at=datetime.now(timezone.utc),
                locked_by="",
                error_reason="",
                fingerprint=fingerprint,
                idempotency_key=f"{session.id}:{next_version}:{fingerprint}",
                stage_payload=self._build_analysis_job_payload(session, fingerprint, next_version),
            )
            self.db.commit()
            refreshed_session = self._get_session(session.id)
            return self._latest_analysis_job(refreshed_session) or job
        except IntegrityError:
            self.db.rollback()
            refreshed_session = self._get_session(session.id)
            return self._latest_analysis_job(refreshed_session)

    def _is_report_ready(self, session) -> bool:
        if not getattr(session, "report", None):
            return False
        payload = self._report_payload(session)
        analysis_status = payload.get("analysis_status")
        if analysis_status == REPORT_PENDING_STATUS:
            return False
        return True

    def _build_pending_report_payload(self, session, started_at: datetime | None = None) -> dict:
        started = started_at or datetime.now(timezone.utc)
        job = self._latest_analysis_job(session)
        return {
            "session_id": session.id,
            "total_score": 0.0,
            "report_level": REPORT_PENDING_LEVEL,
            "competency_scores": {},
            "radar": [],
            "suggestions": [],
            "qa_records": [],
            "next_training_plan": [],
            "summary": "AI 正在分析你的面试，评分和综合报告生成后会自动显示。",
            "voice_scores": {},
            "analysis_status": REPORT_PENDING_STATUS,
            "analysis_started_at": started.isoformat(),
            "analysis_job_id": job.id if job else None,
            "analysis_stage": job.current_stage if job else "queued",
        }

    def _mark_report_pending(self, session, *, started_at: datetime | None = None):
        pending_payload = self._build_pending_report_payload(session, started_at=started_at)
        report = self.repo.upsert_report(
            session_id=session.id,
            total_score=0.0,
            competency_scores={},
            report_level=REPORT_PENDING_LEVEL,
            report_payload=pending_payload,
        )
        self.db.commit()
        return report

    def _ensure_history_report_pending(self, session) -> None:
        if session.status != InterviewStatus.completed:
            return
        if self._is_report_ready(session):
            return
        payload = self._report_payload(session)
        if payload.get("analysis_status") == REPORT_PENDING_STATUS:
            return
        self._mark_report_pending(session)

    def _serialize_audio_features(self, audio_features):
        if not audio_features:
            return None
        return {
            "status": audio_features.status,
            "volume_stability": audio_features.volume_stability,
            "pause_ratio": audio_features.pause_ratio,
            "speech_rate": audio_features.speech_rate,
            "pitch_variation": audio_features.pitch_variation,
            "voiced_ratio": audio_features.voiced_ratio,
        }

    def _schedule_history_report(self, session) -> None:
        if session.status != InterviewStatus.completed:
            return
        if self._is_report_ready(session):
            return
        self._ensure_history_report_pending(session)
        self._ensure_analysis_job(session)

    def _history_audio_url(self, answer) -> str:
        if not answer or not getattr(answer, "audio_path", ""):
            return ""
        audio_path = str(answer.audio_path).replace("\\", "/")
        if audio_path.startswith("var/uploads/"):
            return f"/{audio_path.removeprefix('var/')}"
        if audio_path.startswith("uploads/"):
            return f"/{audio_path}"
        if audio_path.startswith("audio/"):
            return f"/uploads/{audio_path}"
        return f"/uploads/{audio_path.lstrip('/')}"

    def _history_audio_duration_seconds(self, answer) -> float | None:
        if not answer or getattr(answer, "answer_mode", None) != AnswerMode.audio:
            return None
        audio_path = self._resolve_answer_audio_path(answer)
        if audio_path is None:
            return None
        try:
            return measure_audio_duration_seconds(audio_path)
        except Exception:
            logger.warning(
                "history audio duration measure failed | answer_id=%s path=%s",
                getattr(answer, "id", None),
                audio_path,
                exc_info=True,
            )
            return None

    def _history_report_payload(self, session) -> dict:
        if self._is_report_ready(session):
            return {
                "session_id": session.id,
                "total_score": session.report.total_score,
                "report_level": session.report.report_level,
                "competency_scores": session.report.competency_scores,
                "radar": session.report.report_payload.get("radar", []),
                "suggestions": [
                    ReportSuggestion.model_validate(item)
                    for item in session.report.report_payload.get("suggestions", [])
                ],
                "qa_records": session.report.report_payload.get("qa_records", []),
                "next_training_plan": session.report.report_payload.get("next_training_plan", []),
                "summary": session.report.report_payload.get("summary", ""),
                "voice_scores": session.report.report_payload.get("voice_scores", {}),
            }
        pending_payload = self._report_payload(session)
        if pending_payload.get("analysis_status") == REPORT_PENDING_STATUS:
            return {
                "session_id": session.id,
                "total_score": 0.0,
                "report_level": pending_payload.get("report_level", REPORT_PENDING_LEVEL),
                "competency_scores": {},
                "radar": [],
                "suggestions": [],
                "qa_records": [],
                "next_training_plan": [],
                "summary": pending_payload.get("summary", "AI 正在分析你的面试，评分和综合报告生成后会自动显示。"),
                "voice_scores": {},
            }
        return self._build_pending_report_payload(session)

    def _build_pending_report_payload(self, session, started_at: datetime | None = None) -> dict:
        job = self._latest_analysis_job(session)
        started = self._pending_started_at(session, started_at=started_at)
        return {
            "session_id": session.id,
            "total_score": 0.0,
            "report_level": self._pending_level_for_job(job),
            "competency_scores": {},
            "radar": [],
            "suggestions": [],
            "qa_records": [],
            "next_training_plan": [],
            "summary": self._pending_summary_for_job(job),
            "voice_scores": {},
            "analysis_status": self._pending_status_for_job(job),
            "analysis_started_at": started.isoformat(),
            "analysis_job_id": job.id if job else None,
            "analysis_stage": job.current_stage if job else "queued",
        }

    def _history_report_payload(self, session) -> dict:
        if self._is_report_ready(session):
            return {
                "session_id": session.id,
                "total_score": session.report.total_score,
                "report_level": session.report.report_level,
                "competency_scores": session.report.competency_scores,
                "radar": session.report.report_payload.get("radar", []),
                "suggestions": [
                    ReportSuggestion.model_validate(item)
                    for item in session.report.report_payload.get("suggestions", [])
                ],
                "qa_records": session.report.report_payload.get("qa_records", []),
                "next_training_plan": session.report.report_payload.get("next_training_plan", []),
                "summary": session.report.report_payload.get("summary", ""),
                "voice_scores": session.report.report_payload.get("voice_scores", {}),
            }
        return self._build_pending_report_payload(session)

    def _get_question_in_session(self, session, question_id: int):
        for item in self._ordered_questions(session):
            if item.id == question_id:
                return item
        raise AppException("Question not found", 404)

    def _next_turn_no(self, session) -> int:
        ordered_questions = self._ordered_questions(session)
        if not ordered_questions:
            return 1
        return ordered_questions[-1].turn_no + 1

    def _asked_main_questions(self, session, competency_code: str | None = None) -> list[str]:
        asked_questions = []
        for item in self._ordered_questions(session):
            if item.category not in MAIN_QUESTION_CATEGORIES:
                continue
            if competency_code and item.competency_code != competency_code:
                continue
            asked_questions.append(item.question_text)
        return asked_questions

    def _follow_up_count_for_round(self, session, question) -> int:
        ordered_questions = self._ordered_questions(session)
        question_meta = self._build_question_meta(ordered_questions)
        question_id = getattr(question, "id", None)
        round_no = int(question_meta.get(question_id, {"round_no": session.current_turn}).get("round_no", session.current_turn))
        return sum(
            1
            for item in ordered_questions
            if question_meta.get(item.id, {}).get("round_no") == round_no and item.category == QuestionCategory.follow_up
        )

    def _round_follow_up_types(self, session, question) -> list[FollowUpType]:
        ordered_questions = self._ordered_questions(session)
        question_meta = self._build_question_meta(ordered_questions)
        question_id = getattr(question, "id", None)
        round_no = int(question_meta.get(question_id, {"round_no": session.current_turn}).get("round_no", session.current_turn))
        return [
            item.follow_up_type
            for item in ordered_questions
            if question_meta.get(item.id, {}).get("round_no") == round_no and item.category == QuestionCategory.follow_up
        ]

    def _session_follow_up_type_count(self, session, follow_up_type: FollowUpType) -> int:
        return sum(
            1
            for item in self._ordered_questions(session)
            if item.category == QuestionCategory.follow_up and item.follow_up_type == follow_up_type
        )

    def _should_use_credibility_follow_up(
        self,
        analysis: dict,
        answer_text: str,
        low_credibility: bool,
        substantive_answer: bool,
        previous_follow_up_types: list[FollowUpType],
        session,
    ) -> bool:
        if not analysis["credibility_risk"] or not low_credibility:
            return False
        if analysis["confused"] or analysis["low_signal"] or not substantive_answer:
            return False
        if FollowUpType.credibility in previous_follow_up_types:
            return False
        if self._session_follow_up_type_count(session, FollowUpType.credibility) >= MAX_CREDIBILITY_FOLLOW_UPS_PER_SESSION:
            return False
        normalized = answer_text.strip()
        if not normalized:
            return False
        verification_markers = [
            "我负责",
            "我做",
            "指标",
            "数据",
            "性能",
            "延迟",
            "吞吐",
            "成功率",
            "压测",
            "监控",
            "上线",
            "故障",
            "排查",
            "优化",
            "取舍",
            "结果",
        ]
        return any(marker in normalized for marker in verification_markers) or any(char.isdigit() for char in normalized)

    def _contains_confusion_signal(self, answer_text: str) -> bool:
        lowered = answer_text.lower()
        return any(marker in lowered for marker in CONFUSION_MARKERS)

    def _is_low_signal_answer(self, answer_text: str) -> bool:
        lowered = answer_text.lower().strip()
        condensed = lowered.replace(" ", "")
        if not condensed:
            return True
        if any(marker in lowered for marker in LOW_SIGNAL_MARKERS):
            return True
        if len(condensed) <= 8:
            return True
        tokens = [item for item in condensed if item.isalnum() or "\u4e00" <= item <= "\u9fff"]
        if len(set(tokens)) <= 2 and len(condensed) <= 16:
            return True
        return False

    def _build_clarified_follow_up_draft(self, question_text: str) -> str:
        return (
            "如果刚才的问题不够清楚，我们先缩小范围。"
            f"请只用一个你最熟悉的例子，直接回答这道题想问的核心：{question_text}"
        )

    def _analyze_answer(
        self,
        session,
        question,
        answer_text: str,
        evidence: list,
        retrieval_backend: str = "unknown",
    ) -> dict:
        if self.settings.fast_question_flow:
            prompt_result = self._build_answer_analysis_fallback(answer_text)
            fallback_used = True
        else:
            logger.info(
                "prompt context prepared | prompt_name=%s role_code=%s competency_code=%s retrieval_backend=%s evidence_count=%s",
                "answer_analysis",
                session.position.code,
                question.competency_code,
                retrieval_backend,
                len(evidence[:4]),
            )
            prompt_result, fallback_used = self.prompt_service.run_json_prompt(
                "answer_analysis",
                {
                    "task_context": {
                        "position": session.position.name,
                        "role_code": session.position.code,
                        "style": self._session_style_code(session),
                        "difficulty": self._difficulty_context(session),
                        "competency_code": question.competency_code,
                        "stage": "answer_analysis",
                    },
                    "conversation_context": {
                        "question_text": question.question_text,
                        "answer_text": answer_text,
                    },
                    "retrieval_context": self._build_retrieval_context(evidence[:4]),
                },
                fallback_result=self._build_answer_analysis_fallback(answer_text),
            )
        facts = [str(item).strip() for item in prompt_result.get("facts", []) if str(item).strip()]
        missing_points = [str(item).strip() for item in prompt_result.get("missing_points", []) if str(item).strip()]
        confused = self._contains_confusion_signal(answer_text)
        low_signal = self._is_low_signal_answer(answer_text)
        substantive_answer = self._is_substantive_answer(answer_text)
        off_topic = bool(prompt_result.get("off_topic", False)) or (low_signal and not confused)
        credibility_risk = bool(prompt_result.get("credibility_risk", False)) or (low_signal and not substantive_answer)

        if confused:
            facts = []
            if "候选人已经明确表示未理解题意" not in missing_points:
                missing_points.insert(0, "候选人已经明确表示未理解题意")
        elif low_signal:
            facts = facts[:1]
            if "回答信息量过低，缺少可继续深挖的有效细节" not in missing_points:
                missing_points.insert(0, "回答信息量过低，缺少可继续深挖的有效细节")
        elif substantive_answer and len(missing_points) == 1 and "缺少更具体" in missing_points[0]:
            missing_points = []

        is_complete = (
            substantive_answer
            and not confused
            and not off_topic
            and not low_signal
            and len(missing_points) <= 1
            and not (credibility_risk and len(facts) < 2)
        )
        return {
            "facts": facts,
            "missing_points": missing_points,
            "off_topic": off_topic,
            "credibility_risk": credibility_risk,
            "is_complete": is_complete,
            "fallback_used": fallback_used,
            "confused": confused,
            "low_signal": low_signal,
        }
    def _decide_next_question_strategy(
        self,
        session,
        question,
        answer_text: str,
        score_payload: dict,
        evidence: list,
        retrieval_backend: str = "unknown",
    ) -> dict:
        analysis = self._analyze_answer(
            session,
            question,
            answer_text,
            evidence,
            retrieval_backend=retrieval_backend,
        )
        text_scores = score_payload["text_scores"]
        raw_overall_score = score_payload.get("overall_score")
        overall_score = float(raw_overall_score) if raw_overall_score is not None else None
        low_accuracy = text_scores["accuracy"] < 48
        low_completeness = text_scores["completeness"] < 48
        low_credibility = text_scores["credibility"] < 55
        unsure_answer = self._contains_confusion_signal(answer_text)
        substantive_answer = self._is_substantive_answer(answer_text)
        round_follow_up_count = self._follow_up_count_for_round(session, question)
        previous_follow_up_types = self._round_follow_up_types(session, question)
        should_probe_credibility = self._should_use_credibility_follow_up(
            analysis,
            answer_text,
            low_credibility=low_credibility,
            substantive_answer=substantive_answer,
            previous_follow_up_types=previous_follow_up_types,
            session=session,
        )

        follow_up_type = FollowUpType.switch_dimension
        reason = "当前能力点已经覆盖得比较充分，切换到下一个能力点。"

        if analysis["confused"]:
            follow_up_type = FollowUpType.redirect
            reason = "候选人明显有些困惑，先缩小范围补一个澄清追问。"
        elif overall_score is not None and overall_score < 55:
            follow_up_type = FollowUpType.switch_dimension
            reason = "当前这题得分较低，继续叠加追问收益有限，切换到下一个能力点。"
        elif overall_score is not None and overall_score > 75:
            follow_up_type = FollowUpType.switch_dimension
            reason = "当前回答已经比较稳，可以进入下一个能力点。"
        elif analysis["low_signal"] and round_follow_up_count >= 1:
            follow_up_type = FollowUpType.switch_dimension
            reason = "已经追问过一次，但回答仍然信息量不足，切换到下一个能力点。"
        elif analysis["off_topic"] or unsure_answer:
            follow_up_type = FollowUpType.redirect
            reason = "回答偏离了题目核心，需要先拉回主线。"
        elif analysis["low_signal"]:
            follow_up_type = FollowUpType.redirect
            reason = "当前回答信息量太低，先用更聚焦的问法把核心做法问出来。"
        elif should_probe_credibility:
            follow_up_type = FollowUpType.credibility
            reason = "回答已经有基本做法，但仍缺少可验证的个人贡献或结果证据，补一次核验追问。"
        elif analysis["credibility_risk"] and low_credibility and FollowUpType.credibility in previous_follow_up_types:
            follow_up_type = FollowUpType.switch_dimension
            reason = "这一轮已经做过真实性核验，继续追问容易重复，切换到下一个能力点。"
        elif analysis["is_complete"] or (
            substantive_answer
            and round_follow_up_count == 0
            and not analysis["off_topic"]
            and not analysis["confused"]
            and not analysis["low_signal"]
            and not low_accuracy
            and not low_completeness
        ):
            follow_up_type = FollowUpType.switch_dimension
            reason = "当前回答已经比较完整，可以继续往下推进。"
        elif analysis["missing_points"] or low_accuracy or low_completeness:
            follow_up_type = FollowUpType.deepen
            reason = "当前回答还有几个关键点没有展开，值得继续追问。"

        if follow_up_type != FollowUpType.switch_dimension and follow_up_type in previous_follow_up_types:
            follow_up_type = FollowUpType.switch_dimension
            reason = "这一轮已经出现过同类追问，切换到下一个能力点避免重复。"

        if follow_up_type != FollowUpType.switch_dimension and round_follow_up_count >= 2:
            follow_up_type = FollowUpType.switch_dimension
            reason = "这一轮追问已经足够，切换到下一个能力点。"

        next_competency = question.competency_code
        if follow_up_type == FollowUpType.switch_dimension:
            next_competency = self._pick_next_competency(session, current_code=question.competency_code)

        return {
            "analysis": analysis,
            "follow_up_type": follow_up_type,
            "reason": reason,
            "next_competency": next_competency,
            "previous_follow_up_types": previous_follow_up_types,
            "overall_score": overall_score,
        }

    def _estimate_incremental_value(self, analysis: dict, follow_up_type: FollowUpType, overall_score: float | None) -> float:
        if follow_up_type != FollowUpType.switch_dimension:
            return 0.65
        if analysis["confused"] or analysis["off_topic"] or analysis["low_signal"]:
            return 0.12
        if overall_score is not None and overall_score < 55:
            return 0.18
        if analysis["is_complete"] and overall_score is not None and overall_score >= 75:
            return 0.14
        return 0.4

    def _candidate_fit_judgement(self, analysis: dict, rolling_score: float | None, latest_score: float | None) -> str:
        settings = getattr(self, "settings", None) or get_settings()
        reject_threshold = float(settings.dynamic_interview_early_reject_score)
        accept_threshold = float(settings.dynamic_interview_early_accept_score)
        if (
            rolling_score is not None
            and rolling_score < reject_threshold
            and (analysis["confused"] or analysis["off_topic"] or analysis["low_signal"] or (latest_score is not None and latest_score < reject_threshold + 5))
        ):
            return "clearly_not_fit"
        if (
            rolling_score is not None
            and rolling_score >= accept_threshold
            and analysis["is_complete"]
            and not analysis["credibility_risk"]
            and not analysis["off_topic"]
        ):
            return "fit"
        return "borderline"

    def _heuristic_termination_decision(
        self,
        session,
        question,
        analysis: dict,
        follow_up_type: FollowUpType,
        overall_score: float | None,
    ) -> InterviewTerminationDecision:
        settings = getattr(self, "settings", None) or get_settings()
        min_questions = int(getattr(session, "min_questions", settings.dynamic_interview_min_questions))
        max_questions = int(getattr(session, "max_questions", settings.dynamic_interview_max_questions))
        early_reject_score = float(getattr(session, "early_reject_score_threshold", settings.dynamic_interview_early_reject_score))
        early_accept_score = float(getattr(session, "early_accept_score_threshold", settings.dynamic_interview_early_accept_score))
        main_question_count = self._main_question_count(session)
        rolling_score = self._rolling_main_score(session, latest_question=question, latest_score=overall_score)
        total_competencies = max(len(getattr(session.position, "competencies", []) or []), 1)
        covered_competencies = self._covered_main_competencies(session)
        coverage_ratio = min(len(covered_competencies) / total_competencies, 1.0)
        expected_incremental_value = self._estimate_incremental_value(analysis, follow_up_type, overall_score)
        candidate_fit = self._candidate_fit_judgement(analysis, rolling_score, overall_score)
        evidence_sufficient = analysis["is_complete"] and len(covered_competencies) >= min(3, total_competencies)

        policy = InterviewTerminationPolicy(
            min_questions=min_questions,
            max_questions=max_questions,
            early_reject_score=early_reject_score,
            early_accept_score=early_accept_score,
            min_questions_for_accept=settings.dynamic_interview_min_questions_for_accept,
            low_value_gain_threshold=settings.dynamic_interview_low_value_gain_threshold,
        )
        return policy.evaluate(
            answered_main_questions=main_question_count,
            rolling_score=rolling_score,
            latest_score=overall_score,
            competency_coverage_ratio=coverage_ratio,
            evidence_sufficient=evidence_sufficient,
            expected_incremental_value=expected_incremental_value,
            candidate_fit=candidate_fit,
            suggested_next_action="switch_dimension" if follow_up_type == FollowUpType.switch_dimension else "follow_up",
        )

    def _evaluate_interview_termination(
        self,
        session,
        question,
        analysis: dict,
        follow_up_type: FollowUpType,
        overall_score: float | None,
    ) -> InterviewTerminationDecision:
        settings = getattr(self, "settings", None) or get_settings()
        min_questions = int(getattr(session, "min_questions", settings.dynamic_interview_min_questions))
        max_questions = int(getattr(session, "max_questions", settings.dynamic_interview_max_questions))
        early_reject_score = float(getattr(session, "early_reject_score_threshold", settings.dynamic_interview_early_reject_score))
        early_accept_score = float(getattr(session, "early_accept_score_threshold", settings.dynamic_interview_early_accept_score))
        fallback = self._heuristic_termination_decision(
            session,
            question,
            analysis,
            follow_up_type,
            overall_score,
        )
        total_competencies = max(len(getattr(session.position, "competencies", []) or []), 1)
        covered_competencies = sorted(self._covered_main_competencies(session))
        coverage_ratio = min(len(covered_competencies) / total_competencies, 1.0)
        expected_incremental_value = self._estimate_incremental_value(analysis, follow_up_type, overall_score)
        context = {
            "session_policy": {
                "min_questions": min_questions,
                "max_questions": max_questions,
                "early_reject_score": early_reject_score,
                "early_accept_score": early_accept_score,
            },
            "interview_state": {
                "answered_main_questions": self._main_question_count(session),
                "covered_competencies": covered_competencies,
                "competency_coverage_ratio": round(coverage_ratio, 2),
                "rolling_score": fallback.rolling_score,
                "latest_score": overall_score,
                "information_sufficient": fallback.information_sufficient,
                "expected_incremental_value": round(expected_incremental_value, 2),
            },
            "candidate_assessment": {
                "fit_judgement": fallback.candidate_fit,
                "reasons": [
                    "回答偏题" if analysis["off_topic"] else "",
                    "回答信息量低" if analysis["low_signal"] else "",
                    "候选人明显困惑" if analysis["confused"] else "",
                    "证据不足" if analysis["credibility_risk"] else "",
                ],
            },
            "question_strategy": {
                "suggested_next_action": "switch_dimension" if follow_up_type == FollowUpType.switch_dimension else "follow_up",
                "follow_up_type": follow_up_type.value,
            },
        }
        context["candidate_assessment"]["reasons"] = [
            item for item in context["candidate_assessment"]["reasons"] if item
        ] or [fallback.reason]

        if self._main_question_count(session) < min_questions:
            return fallback
        if self._main_question_count(session) >= max_questions:
            return fallback

        try:
            prompt_result, _ = self.prompt_service.run_json_prompt(
                "interview_continue_decision",
                context,
                fallback_result={
                    "decision": fallback.decision,
                    "end_reason": fallback.end_reason,
                    "confidence": fallback.confidence,
                    "reason": fallback.reason,
                    "suggested_next_action": fallback.suggested_next_action,
                },
            )
        except Exception:
            logger.warning("termination prompt fallback forced | session_id=%s", getattr(session, "id", None))
            prompt_result = {
                "decision": fallback.decision,
                "end_reason": fallback.end_reason,
                "confidence": fallback.confidence,
                "reason": fallback.reason,
                "suggested_next_action": fallback.suggested_next_action,
            }
        decision = str(prompt_result.get("decision") or fallback.decision).strip()
        end_reason = str(prompt_result.get("end_reason") or fallback.end_reason).strip()
        suggested_next_action = str(prompt_result.get("suggested_next_action") or fallback.suggested_next_action).strip()
        reason = str(prompt_result.get("reason") or fallback.reason).strip() or fallback.reason
        confidence = float(prompt_result.get("confidence") or fallback.confidence)

        if decision not in {"continue", "end"}:
            return fallback
        if decision == "end" and end_reason not in {"early_reject", "early_accept", "completed_max_questions"}:
            return fallback
        return InterviewTerminationDecision(
            decision=decision,
            end_reason=end_reason if decision == "end" else "none",
            confidence=confidence,
            reason=reason,
            suggested_next_action=suggested_next_action if suggested_next_action in {"follow_up", "switch_dimension", "close_interview"} else fallback.suggested_next_action,
            low_value_gain=fallback.low_value_gain,
            information_sufficient=fallback.information_sufficient,
            candidate_fit=fallback.candidate_fit,
            rolling_score=fallback.rolling_score,
            latest_score=fallback.latest_score,
        )

    def _plan_next_question(
        self,
        session,
        question,
        answer_text: str,
        score_payload: dict,
        evidence: list,
        retrieval_backend: str = "unknown",
    ) -> tuple[str, int | None]:
        next_turn_no = self._next_turn_no(session)
        decision = self._decide_next_question_strategy(
            session,
            question,
            answer_text,
            score_payload,
            evidence,
            retrieval_backend=retrieval_backend,
        )
        analysis = decision["analysis"]
        follow_up_type = decision["follow_up_type"]
        reason = decision["reason"]
        next_competency = decision["next_competency"]
        previous_follow_up_types = decision["previous_follow_up_types"]
        previous_question_id = getattr(question, "id", None)
        termination_decision = self._evaluate_interview_termination(
            session,
            question,
            analysis,
            follow_up_type,
            decision["overall_score"],
        )

        if termination_decision.should_end:
            session.status = InterviewStatus.completed
            session.end_reason = termination_decision.end_reason
            session.end_decided_by = "ai"
            if getattr(session, "completed_at", None) is None:
                session.completed_at = datetime.now(timezone.utc)
            self._clear_question_prefetch(session.id, previous_question_id)
            logger.info(
                "interview completed by termination policy | session_id=%s turn_no=%s end_reason=%s rolling_score=%s latest_score=%s",
                session.id,
                session.current_turn,
                termination_decision.end_reason,
                termination_decision.rolling_score,
                termination_decision.latest_score,
            )
            return "completed", None

        prefetched_question_id = self._create_prefetched_question(
            session,
            question,
            follow_up_type,
            reason,
            next_competency,
        )
        if prefetched_question_id is not None:
            return follow_up_type.value, prefetched_question_id

        if follow_up_type == FollowUpType.switch_dimension:
            if session.current_turn >= session.max_questions:
                session.status = InterviewStatus.completed
                if getattr(session, "completed_at", None) is None:
                    session.completed_at = datetime.now(timezone.utc)
                self._clear_question_prefetch(session.id, previous_question_id)
                logger.info(
                    "interview completed without fixed wrap-up | session_id=%s turn_no=%s competency_code=%s overall_score=%s",
                    session.id,
                    next_turn_no,
                    question.competency_code,
                    decision["overall_score"],
                )
                return "completed", None
                final_question = self.repo.create_question(
                    session_id=session.id,
                    turn_no=next_turn_no,
                    category=QuestionCategory.wrap_up,
                    competency_code=question.competency_code,
                    question_text="最后请你用一句话总结：你最希望面试官记住你的哪一点？",
                    follow_up_reason="主问题轮次已完成，进入总结题。",
                    follow_up_type=FollowUpType.switch_dimension,
                    evidence_summary="main_question_limit_reached",
                )
                session.status = InterviewStatus.summary
                self._clear_question_prefetch(session.id, previous_question_id)
                logger.info(
                    "next question planned | session_id=%s turn_no=%s follow_up_type=%s competency_code=%s overall_score=%s",
                    session.id,
                    next_turn_no,
                    FollowUpType.switch_dimension.value,
                    question.competency_code,
                    decision["overall_score"],
                )
                return "summary", final_question.id

            next_question_text = self._seed_main_question(session, next_competency, next_turn_no)
            prompt_retrieval = self.retrieval_service.retrieve_with_meta(
                query=f"{session.position.code} {next_competency} {next_question_text}",
                role_code=session.position.code,
                profile_name="question_generation",
            )
        else:
            if analysis["confused"]:
                next_question_text = self._build_clarified_follow_up_draft(question.question_text)
            else:
                next_question_text = self._seed_follow_up_text(
                    session,
                    follow_up_type.value,
                    question.competency_code,
                    answer_text,
                )
            next_competency = question.competency_code
            prompt_retrieval = SimpleNamespace(
                evidence=evidence,
                backend=retrieval_backend,
            )

        logger.info(
            "prompt context prepared | prompt_name=%s role_code=%s competency_code=%s retrieval_backend=%s evidence_count=%s",
            "follow_up",
            session.position.code,
            next_competency,
            prompt_retrieval.backend,
            len(prompt_retrieval.evidence),
        )
        prompt_result, fallback_used = self._run_required_prompt(
            "follow_up",
            {
                "task_context": {
                    "position": session.position.name,
                    "role_code": session.position.code,
                    "style": self._session_style_code(session),
                    "difficulty": self._difficulty_context(session),
                    "follow_up_type": follow_up_type.value,
                    "competency_code": next_competency,
                    "stage": "follow_up",
                },
                "conversation_context": {
                    "previous_question": question.question_text,
                    "answer_text": answer_text,
                    "reason": reason,
                    "facts": analysis["facts"],
                    "missing_points": analysis["missing_points"],
                    "off_topic": analysis["off_topic"],
                    "credibility_risk": analysis["credibility_risk"],
                    "candidate_confused": analysis["confused"],
                    "low_signal_answer": analysis["low_signal"],
                    "previous_follow_up_types": [item.value for item in previous_follow_up_types],
                    "asked_questions": self._get_pipeline_state(session)["asked_questions"],
                    "covered_competencies": self._get_pipeline_state(session)["covered_competencies"],
                    "avoid_repetition": self._get_pipeline_state(session)["asked_questions"],
                },
                "resume_context": self._build_resume_prompt_context(self._resume_summary(session), session.position.code),
                "retrieval_context": self._build_retrieval_context(prompt_retrieval.evidence),
                "draft": {
                    "question": next_question_text,
                    "seed_examples": self.seed_service.get_seed_examples(
                        session.position.code, next_competency, count=3,
                    ),
                    "instruction": "以上 seed_examples 仅供参考风格，请生成一道新的、不重复的追问题。",
                },
            },
            error_message="AI 追问生成失败，请检查大模型服务配置、鉴权和网络连接后重试。",
            fallback_result={"draft_question": next_question_text},
        )
        final_question_text = self._sanitize_generated_question(
            prompt_result.get("draft_question", next_question_text),
            next_question_text,
        )
        next_question = self.repo.create_question(
            session_id=session.id,
            turn_no=next_turn_no,
            category=QuestionCategory.follow_up if follow_up_type != FollowUpType.switch_dimension else QuestionCategory.technical,
            competency_code=next_competency,
            question_text=final_question_text,
            follow_up_reason=reason,
            follow_up_type=follow_up_type,
            evidence_summary=self._format_evidence_summary(
                prompt_retrieval.backend,
                fallback_used,
                len(prompt_retrieval.evidence),
                next_competency,
            ),
        )
        if follow_up_type == FollowUpType.switch_dimension:
            session.current_turn += 1
            session.status = InterviewStatus.technical_question
        else:
            session.status = InterviewStatus.deep_follow_up
        self._clear_question_prefetch(session.id, previous_question_id)
        self._ensure_question_pipeline_state(session, next_question)
        logger.info(
            "next question planned | session_id=%s turn_no=%s follow_up_type=%s competency_code=%s fallback_used=%s retrieval_backend=%s evidence_count=%s overall_score=%s answer_complete=%s missing_points=%s confused=%s low_signal=%s",
            session.id,
            next_turn_no,
            follow_up_type.value,
            next_competency,
            fallback_used,
            prompt_retrieval.backend,
            len(prompt_retrieval.evidence),
            decision["overall_score"],
            analysis["is_complete"],
            len(analysis["missing_points"]),
            analysis["confused"],
            analysis["low_signal"],
        )
        return follow_up_type.value, next_question.id

    def _build_retrieval_context(self, evidence: list) -> list[dict]:
        return [
            {
                "title": item.title,
                "snippet": item.snippet,
                "competency_code": item.competency_code,
                "score": item.score,
                "source_type": item.doc_type,
            }
            for item in evidence[:4]
        ]

    def _sanitize_generated_question(self, question_text: str, fallback_question: str) -> str:
        text = self._normalize_generated_question_text(question_text)
        fallback = self._normalize_generated_question_text(fallback_question)
        if not text:
            return fallback

        compacted = self._compact_enumerated_question(text, fallback)
        if compacted:
            text = compacted

        text = re.sub(r"\d+[)）]\s*", "", text)
        text = re.sub(r"[（(](?:例如|比如|如)[^）)]*[）)]", "", text)
        text = re.sub(r"[；;]\s*", "，", text)
        text = re.sub(r"\s+", " ", text).strip(" ，。；;")

        if len(text) > 72:
            text = self._compress_long_question(text, fallback)

        text = text.rstrip("，；;")
        if text and text[-1] not in ".。？！?":
            text = f"{text}。"
        return text or fallback

    def _normalize_generated_question_text(self, text: str) -> str:
        normalized = " ".join((text or "").split())
        normalized = normalized.replace("：", "，").replace(":", "，")
        normalized = re.sub(r"[“”\"]", "", normalized)
        return normalized.strip()

    def _compact_enumerated_question(self, text: str, fallback: str) -> str:
        if not re.search(r"\d+[)）]", text):
            return ""

        intro = self._question_intro(text, fallback)
        focuses: list[str] = []
        if any(token in text for token in ("架构决策", "技术判断", "取舍")):
            focuses.append("关键决策")
        if any(token in text for token in ("约束", "限制", "协作", "耦合", "压测")):
            focuses.append("核心约束")
        if any(token in text for token in ("量化", "指标", "验证", "效果")):
            focuses.append("结果验证")
        if any(token in text for token in ("复盘", "迭代")) and "结果验证" not in focuses:
            focuses.append("复盘")

        if not focuses:
            return ""
        focus_text = "、".join(dict.fromkeys(focuses[:3]))
        return f"{intro}，重点讲讲你的{focus_text}"

    def _compress_long_question(self, text: str, fallback: str) -> str:
        intro = self._question_intro(text, fallback)
        focuses: list[str] = []
        keyword_map = [
            ("关键决策", ("架构", "决策", "trade-off", "取舍")),
            ("核心约束", ("约束", "限制", "协作", "耦合", "复杂场景")),
            ("结果验证", ("量化", "指标", "验证", "效果", "收益")),
            ("复盘", ("复盘", "迭代", "失败")),
        ]
        for label, keywords in keyword_map:
            if any(keyword in text for keyword in keywords):
                focuses.append(label)

        if not focuses:
            if fallback and len(fallback) <= 72:
                return fallback
            return text[:68].rstrip("，；; ") + "。"

        focus_text = "、".join(dict.fromkeys(focuses[:3]))
        return f"{intro}，重点讲讲你的{focus_text}"

    def _question_intro(self, text: str, fallback: str) -> str:
        candidate = re.split(r"[，。？！?]", text, maxsplit=1)[0].strip()
        for marker in ("重点说明", "重点讲", "请聚焦", "并说明"):
            if marker in candidate:
                candidate = candidate.split(marker, 1)[0].strip("，:： ")
        if len(candidate) < 8 and fallback:
            candidate = re.split(r"[，。？！?]", fallback, maxsplit=1)[0].strip()
        if not candidate:
            candidate = "请介绍一个你深度参与的项目"
        return candidate.rstrip("，；; ")

    def _format_evidence_summary(
        self,
        retrieval_backend: str,
        prompt_fallback_used: bool,
        evidence_count: int,
        competency_code: str,
    ) -> str:
        return (
            f"backend={retrieval_backend}; prompt_fallback={prompt_fallback_used}; "
            f"evidence_count={evidence_count}; competency={competency_code}"
        )

    def _build_opening_query(
        self,
        role_code: str,
        competency_code: str,
        draft_question: str,
        summary: ResumeSummary | None,
    ) -> str:
        resume_bits: list[str] = []
        if summary:
            job_match = self._resume_job_match(summary, role_code)
            resume_bits.extend(summary.highlights[:2])
            resume_bits.extend(summary.risk_points[:2])
            resume_bits.extend(summary.tech_stack[:3])
            if job_match:
                resume_bits.extend(job_match.matched_skills[:2])
                resume_bits.extend(job_match.missing_skills[:2])
                resume_bits.extend(job_match.interview_focuses[:2])
        return " ".join(
            item
            for item in [role_code, competency_code, draft_question, *resume_bits]
            if item
        )

    def _build_answer_analysis_fallback(self, answer_text: str) -> dict:
        normalized = answer_text.strip()
        fragments = [
            item.strip("。；;，, ")
            for item in normalized.replace("\n", "，").split("，")
            if item.strip("。；;，, ")
        ]
        facts = fragments[:3]
        if not facts and normalized:
            facts = [normalized[:80]]
        confused = self._contains_confusion_signal(normalized)
        low_signal = self._is_low_signal_answer(normalized)
        substantive_answer = self._is_substantive_answer(normalized)
        credibility_markers = ["负责", "指标", "结果", "数据", "压测", "监控", "优化", "上线", "方案", "取舍"]
        credibility_risk = confused or low_signal or (
            bool(normalized)
            and not substantive_answer
            and not any(marker in normalized for marker in credibility_markers)
            and not any(char.isdigit() for char in normalized)
        )
        missing_points: list[str] = []
        if confused:
            missing_points.append("候选人已经明确表示未理解题意")
        elif low_signal:
            missing_points.append("回答信息量过低，缺少可继续深挖的有效细节")
        elif normalized and not substantive_answer:
            missing_points.append("回答还没有形成完整链路，请补充你的做法、取舍或结果。")
        return {
            "facts": [] if (confused or low_signal) else facts,
            "missing_points": missing_points,
            "off_topic": low_signal and not confused,
            "credibility_risk": credibility_risk,
        }
    def _pick_next_competency(self, session, current_code: str) -> str:
        competencies = sorted(getattr(session.position, "competencies", []) or [], key=lambda item: item.weight, reverse=True)
        used_codes = [
            item.competency_code
            for item in self._ordered_questions(session)
            if item.category in MAIN_QUESTION_CATEGORIES
        ]
        for competency in competencies:
            if competency.code not in used_codes:
                return competency.code
        if not competencies:
            return current_code
        current_index = next((index for index, item in enumerate(competencies) if item.code == current_code), -1)
        return competencies[(current_index + 1) % len(competencies)].code

    def _finalize_session(self, session) -> InterviewReportRead:
        report = self._build_report(session)
        session.status = InterviewStatus.completed
        session.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self._clear_pipeline_cache(session.id)
        logger.info(
            "interview session completed | session_id=%s user_id=%s total_score=%s report_level=%s",
            session.id,
            session.user_id,
            report.total_score,
            report.report_level,
        )
        return report

    def _collect_voice_scores(self, session) -> dict[str, float]:
        voice_scores: dict[str, list[float]] = {
            "speech_confidence": [],
            "speech_clarity": [],
            "speech_fluency": [],
            "speech_emotion": [],
        }
        for answer in self._ordered_answers(session):
            if not answer.score or answer.answer_mode != AnswerMode.audio:
                continue
            audio_scores = answer.score.audio_scores or {}
            mapping = {
                "speech_confidence": audio_scores.get("confidence"),
                "speech_clarity": audio_scores.get("clarity"),
                "speech_fluency": audio_scores.get("fluency"),
                "speech_emotion": audio_scores.get("emotion"),
            }
            for key, value in mapping.items():
                if isinstance(value, (int, float)):
                    voice_scores[key].append(float(value))
        return {key: round(mean(values), 2) for key, values in voice_scores.items() if values}
    def _build_report(self, session) -> InterviewReportRead:
        competency_scores: dict[str, list[float]] = {}
        suggestions: list[ReportSuggestion] = []
        qa_records = []
        weaknesses = []
        ordered_questions = self._ordered_questions(session)
        question_meta = self._build_question_meta(ordered_questions)
        for answer in self._ordered_answers(session):
            if not answer.score:
                continue
            competency_scores.setdefault(answer.score.competency_code, []).append(answer.score.overall_score)
            round_meta = question_meta.get(answer.question_id, {"round_no": answer.turn_no, "counts_toward_total": True})
            qa_records.append(
                {
                    "turn_no": round_meta["round_no"],
                    "is_follow_up": not round_meta["counts_toward_total"],
                    "question": answer.question.question_text,
                    "answer": answer.answer_text or answer.asr_text,
                    "score": answer.score.overall_score,
                    "follow_up_reason": answer.question.follow_up_reason,
                }
            )
            if answer.score.overall_score < 70:
                weaknesses.append({"tag": answer.score.competency_code, "score": answer.score.overall_score})
                suggestions.append(
                    ReportSuggestion(
                        issue=f"{get_competency_label(answer.score.competency_code)} 需要重点提升",
                        reason=answer.score.explanation,
                        improvement="回到这个能力点的核心概念，回答时补充更清晰的技术细节、取舍过程和可验证结果。",
                        practice_direction=f"至少围绕 {get_competency_label(answer.score.competency_code)} 练习 3 道针对性模拟题。",
                    )
                )
        flattened = {key: round(mean(value), 2) for key, value in competency_scores.items()}
        voice_scores = self._collect_voice_scores(session)
        total_score = round(mean(flattened.values()), 2) if flattened else 0.0
        if total_score >= 85:
            level = "表现优秀"
        elif total_score >= 75:
            level = "表现良好"
        elif total_score >= 60:
            level = "达到预期"
        else:
            level = "需要加强"

        next_training_plan = [item.improvement for item in suggestions[:3]] or [
            "优先补齐最薄弱的能力点，再加强回答结构、项目证据和场景化表达深度。",
        ]
        summary = f"本场面试共完成 {len(self._ordered_answers(session))} 次作答，总分 {total_score} 分，当前水平为“{level}”。"
        report_payload = InterviewReportRead(
            session_id=session.id,
            total_score=total_score,
            report_level=level,
            competency_scores=flattened,
            radar=[{"name": get_competency_label(key), "value": value} for key, value in flattened.items()],
            suggestions=suggestions[:5],
            qa_records=qa_records,
            next_training_plan=next_training_plan,
            summary=summary,
            voice_scores=voice_scores,
            style=session.style,
            answer_mode=self._session_answer_mode(session),
        )
        self.repo.upsert_report(
            session_id=session.id,
            total_score=total_score,
            competency_scores=flattened,
            report_level=level,
            report_payload={
                **report_payload.model_dump(),
                "analysis_status": REPORT_READY_STATUS,
                "weaknesses": weaknesses,
            },
        )
        if self._is_archivable_session(session):
            self.system_repo.add_growth_snapshot(
                user_id=session.user_id,
                payload={
                    "session_id": session.id,
                    "total_score": total_score,
                    "weaknesses": weaknesses,
                    "plan": next_training_plan,
                },
            )
        logger.info(
            "report built | session_id=%s user_id=%s total_score=%s weakness_count=%s",
            session.id,
            session.user_id,
            total_score,
            len(weaknesses),
        )
        return report_payload






def run_answer_scoring_task(session_id: int, answer_id: int) -> None:
    db = SessionLocal()
    try:
        service = InterviewService(db)
        session = service._get_session(session_id)
        answer = service.repo.get_answer(answer_id)
        if not answer or answer.session_id != session.id:
            logger.warning(
                "async answer evaluation skipped because answer is missing | session_id=%s answer_id=%s",
                session_id,
                answer_id,
            )
            return
        service._persist_answer_evaluation(session, answer)
    except Exception:
        db.rollback()
        logger.exception(
            "async answer evaluation failed | session_id=%s answer_id=%s",
            session_id,
            answer_id,
        )
    finally:
        db.close()


def run_history_report_task(job_id: int) -> None:
    db = SessionLocal()
    try:
        service = InterviewService(db)
        repo = service.repo
        now = datetime.now(timezone.utc)
        claim = repo.claim_analysis_job(
            job_id=job_id,
            worker_id=ANALYSIS_WORKER_ID,
            now=now,
            heartbeat_timeout_before=now - ANALYSIS_JOB_HEARTBEAT_TIMEOUT,
        )
        if not claim:
            logger.info("analysis job skipped because it is already claimed or no longer due | job_id=%s", job_id)
            return

        session = claim.session
        if not session:
            logger.info(
                "analysis job skipped because session is missing | job_id=%s session_id=%s",
                job_id,
                getattr(claim, "session_id", None),
            )
            repo.mark_analysis_job_failed(
                claim,
                now=datetime.now(timezone.utc),
                error_reason="Interview session missing.",
                next_retry_at=None,
            )
            db.commit()
            return

        if session.status != InterviewStatus.completed:
            logger.info(
                "analysis job skipped because session is not completed | job_id=%s session_id=%s status=%s",
                job_id,
                session.id,
                getattr(session.status, "value", session.status),
            )
            repo.mark_analysis_job_failed(
                claim,
                now=datetime.now(timezone.utc),
                error_reason="Interview session is not completed.",
                next_retry_at=None,
            )
            db.commit()
            return

        if service._is_report_ready(session):
            repo.mark_analysis_job_success(
                claim,
                now=datetime.now(timezone.utc),
                payload={**(claim.stage_payload or {}), "finalized_at": datetime.now(timezone.utc).isoformat()},
            )
            db.commit()
            logger.info(
                "analysis job skipped because report already exists | job_id=%s session_id=%s",
                job_id,
                session.id,
            )
            return

        repo.heartbeat_analysis_job(
            claim,
            now=datetime.now(timezone.utc),
            stage="qa_scoring",
            payload={**(claim.stage_payload or {}), "session_id": session.id, "stage": "qa_scoring"},
        )
        db.commit()
        logger.info("analysis job started | job_id=%s session_id=%s", job_id, session.id)

        service._ensure_session_scores(session)
        refreshed_job = repo.get_analysis_job(job_id)
        if not refreshed_job or not refreshed_job.session:
            return
        repo.heartbeat_analysis_job(
            refreshed_job,
            now=datetime.now(timezone.utc),
            stage="report_generation",
            payload={**(refreshed_job.stage_payload or {}), "session_id": refreshed_job.session.id, "stage": "report_generation"},
        )
        db.commit()

        refreshed_session = service._get_session(refreshed_job.session.id)
        if not service._is_report_ready(refreshed_session):
            service._build_report(refreshed_session)
            db.commit()

        completed_job = repo.get_analysis_job(job_id)
        if completed_job:
            repo.mark_analysis_job_success(
                completed_job,
                now=datetime.now(timezone.utc),
                payload={**(completed_job.stage_payload or {}), "session_id": refreshed_session.id, "stage": "report_generated"},
            )
            db.commit()
        logger.info("analysis job completed | job_id=%s session_id=%s", job_id, refreshed_session.id)
    except Exception as exc:
        db.rollback()
        try:
            service = InterviewService(db)
            job = service.repo.get_analysis_job(job_id)
            if job:
                now = datetime.now(timezone.utc)
                next_retry_at = service._analysis_retry_at(job.retry_count, now)
                service.repo.mark_analysis_job_failed(
                    job,
                    now=now,
                    error_reason=str(exc),
                    next_retry_at=next_retry_at,
                )
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("analysis job failure state update failed | job_id=%s", job_id)
        logger.exception("analysis job failed | job_id=%s", job_id)
    finally:
        REPORT_REBUILDING_SESSIONS.discard(job_id)
        db.close()






































