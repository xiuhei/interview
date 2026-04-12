from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.enums import FollowUpType, InterviewStatus, InterviewStyle, QuestionCategory
from app.core.exceptions import AppException
from app.rag.service import RetrievalTrace
from app.schemas.interview import InterviewReportRead, RetrievalEvidence
from app.schemas.resume import ResumeSummary
from app.services.interview_service import InterviewService
from app.services.question_seed_service import QuestionSeedService


class DummyDB:
    def commit(self) -> None:
        return None

    def refresh(self, _session) -> None:
        return None


class DummyRepo:
    def __init__(self, session=None) -> None:
        self.created_questions: list[dict] = []
        self.session = session

    def cleanup_expired_unfinished_sessions(self, expires_before, user_id=None):
        _ = expires_before, user_id
        return 0

    def create_question(self, **kwargs):
        question = SimpleNamespace(id=len(self.created_questions) + 1, **kwargs)
        self.created_questions.append(kwargs)
        if self.session is not None:
            self.session.questions.append(question)
        return question


class DummySeedService:
    def get_opening_question(self, role_code: str, highlights: list[str], risk_points: list[str], used_questions: list[str]):
        _ = highlights, risk_points, used_questions
        return f"opening::{role_code}", "project_depth"

    def get_question_for_competency(self, role_code: str, competency_code: str, used_questions: list[str]):
        _ = used_questions
        return f"main::{role_code}::{competency_code}"

    def get_follow_up_question(self, role_code: str, follow_up_type: str, competency_code: str, answer_text: str):
        _ = answer_text
        return f"follow::{role_code}::{follow_up_type}::{competency_code}"

    def get_seed_examples(self, role_code: str, competency_code: str, count: int = 3):
        return [f"seed_example::{role_code}::{competency_code}::{i}" for i in range(count)]


class CapturePromptService:
    def __init__(self, custom_questions: dict[str, str] | None = None) -> None:
        self.calls: list[dict] = []
        self.custom_questions = custom_questions or {}

    def run_json_prompt(self, name: str, variables: dict, fallback_result: dict | None = None):
        self.calls.append(
            {
                "name": name,
                "variables": variables,
                "fallback_result": fallback_result,
            }
        )
        if name == "answer_analysis":
            return {
                "facts": ["explain bottleneck first", "then discuss cache and rate limit"],
                "missing_points": [],
                "off_topic": False,
                "credibility_risk": False,
            }, False
        if name in self.custom_questions:
            return {"draft_question": self.custom_questions[name]}, False
        return {"draft_question": variables["draft"]["question"]}, False


class DummyRetrievalService:
    def __init__(self, evidence: list[RetrievalEvidence]) -> None:
        self.calls: list[dict] = []
        self.evidence = evidence

    def retrieve_with_meta(self, query: str, role_code: str) -> RetrievalTrace:
        self.calls.append({"query": query, "role_code": role_code})
        return RetrievalTrace(evidence=self.evidence, backend="milvus")


def build_evidence() -> list[RetrievalEvidence]:
    return [
        RetrievalEvidence(
            doc_id="doc-1",
            role_code="cpp_backend",
            doc_type="knowledge",
            competency_code="system_design",
            title="system design",
            snippet="cache, rate limiting, database, and monitoring matter for high concurrency.",
            score=0.91,
        )
    ]


def build_service(evidence: list[RetrievalEvidence] | None = None) -> tuple[InterviewService, DummyRepo, CapturePromptService, DummyRetrievalService]:
    service = object.__new__(InterviewService)
    repo = DummyRepo()
    prompt_service = CapturePromptService()
    retrieval_service = DummyRetrievalService(evidence or build_evidence())
    service.repo = repo
    service.seed_service = DummySeedService()
    service.prompt_service = prompt_service
    service.retrieval_service = retrieval_service
    service._next_turn_no = lambda session: 2
    service._asked_main_questions = lambda session, competency_code=None: []
    service._pick_next_competency = lambda session, current_code: "architecture"
    service._follow_up_count_for_round = lambda session, question: 0
    return service, repo, prompt_service, retrieval_service


def test_opening_question_uses_retrieval_context_and_prompt_output():
    resume_summary = ResumeSummary(
        background="3 years of backend work and some high-concurrency projects.",
        project_experiences=["trading system", "monitoring platform"],
        tech_stack=["C++", "Redis", "MySQL"],
        highlights=["high concurrency", "performance tuning"],
        risk_points=["missing quantified results"],
        years_of_experience=3,
    )
    session = SimpleNamespace(
        id=1,
        current_turn=0,
        max_questions=6,
        status=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        resume=SimpleNamespace(parse=SimpleNamespace(summary=resume_summary.model_dump())),
        questions=[],
        answers=[],
    )
    repo = DummyRepo(session)
    prompt_service = CapturePromptService({"opening_question": "Tell me how you approached capacity planning in your last project."})
    retrieval_service = DummyRetrievalService(build_evidence())
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = repo
    service.seed_service = DummySeedService()
    service.prompt_service = prompt_service
    service.retrieval_service = retrieval_service
    service._get_session = lambda session_id: session
    service._asked_main_questions = lambda current_session: []
    service._ensure_question_pipeline_state = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("warmup should not run on first question"))
    service._serialize_question = lambda current_session, question, ordered_questions=None: SimpleNamespace(
        id=question.id,
        question_text=question.question_text,
    )

    question = service.get_first_question(1)

    assert question.question_text == "Tell me how you approached capacity planning in your last project."
    assert retrieval_service.calls[0]["role_code"] == "cpp_backend"
    prompt_call = prompt_service.calls[0]
    assert prompt_call["name"] == "opening_question"
    assert prompt_call["fallback_result"] is None
    assert prompt_call["variables"]["retrieval_context"][0]["source_type"] == "knowledge"
    assert prompt_call["variables"]["draft"]["question"] == "opening::cpp_backend"
    assert repo.created_questions[0]["evidence_summary"].startswith("backend=milvus")


def test_opening_question_fails_fast_when_ai_prompt_fails():
    resume_summary = ResumeSummary(
        background="3 years of backend work.",
        project_experiences=["trading system"],
        tech_stack=["C++", "Redis"],
        highlights=["performance tuning"],
        risk_points=[],
        years_of_experience=3,
    )
    session = SimpleNamespace(
        id=1,
        current_turn=0,
        max_questions=6,
        status=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        resume=SimpleNamespace(parse=SimpleNamespace(summary=resume_summary.model_dump())),
        questions=[],
        answers=[],
    )

    class FailingPromptService:
        def run_json_prompt(self, name: str, variables: dict, fallback_result: dict | None = None):
            _ = name, variables, fallback_result
            raise RuntimeError("llm boom")

    repo = DummyRepo(session)
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = repo
    service.seed_service = DummySeedService()
    service.prompt_service = FailingPromptService()
    service.retrieval_service = DummyRetrievalService(build_evidence())
    service._get_session = lambda session_id: session
    service._asked_main_questions = lambda current_session: []

    try:
        service.get_first_question(1)
    except AppException as exc:
        assert exc.status_code == 502
        assert "AI 首题生成失败" in exc.message
    else:
        raise AssertionError("expected AppException when opening question prompt fails")

    assert repo.created_questions == []


def test_opening_question_sanitizes_outline_style_prompt_output():
    session = SimpleNamespace(
        id=1,
        current_turn=0,
        max_questions=6,
        status=None,
        style=InterviewStyle.hard,
        position=SimpleNamespace(code="web_frontend", name="Web Frontend"),
        resume=None,
        questions=[],
        answers=[],
    )
    repo = DummyRepo(session)
    prompt_service = CapturePromptService(
        {
            "opening_question": (
                "请介绍一个你深度参与的前端项目，重点说明：1）你在其中承担的关键架构决策"
                "（例如微前端落地、状态管理演进或性能瓶颈突破）；2）当时面临的核心约束"
                "（如多团队协作、历史代码耦合、首屏性能压测不达标等）；3）你如何量化评估方案效果。"
            )
        }
    )
    retrieval_service = DummyRetrievalService(build_evidence())
    service = object.__new__(InterviewService)
    service.db = DummyDB()
    service.repo = repo
    service.seed_service = DummySeedService()
    service.prompt_service = prompt_service
    service.retrieval_service = retrieval_service
    service._get_session = lambda session_id: session
    service._asked_main_questions = lambda current_session: []
    service._ensure_question_pipeline_state = lambda *_args, **_kwargs: None
    service._serialize_question = lambda current_session, question, ordered_questions=None: SimpleNamespace(
        id=question.id,
        question_text=question.question_text,
    )

    question = service.get_first_question(1)

    assert "1）" not in question.question_text
    assert "例如" not in question.question_text
    assert "微前端落地" not in question.question_text
    assert question.question_text == "请介绍一个你深度参与的前端项目，重点讲讲你的关键决策、核心约束、结果验证。"

def test_complete_answer_switches_dimension_without_extra_follow_up():
    evidence = build_evidence()
    service, repo, prompt_service, retrieval_service = build_service(evidence)
    service._analyze_answer = lambda session, question, answer_text, items, retrieval_backend="unknown": {
        "facts": ["analyze the bottleneck first", "then use cache and rate limiting"],
        "missing_points": [],
        "off_topic": False,
        "credibility_risk": False,
        "is_complete": True,
        "fallback_used": False,
        "confused": False,
        "low_signal": False,
    }
    session = SimpleNamespace(
        id=1,
        current_turn=1,
        max_questions=6,
        status=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
    )
    question = SimpleNamespace(competency_code="system_design", question_text="Design a high-concurrency API.")
    score_payload = {"text_scores": {"accuracy": 78, "completeness": 82, "credibility": 75}}

    action, question_id = service._plan_next_question(
        session,
        question,
        "complete answer",
        score_payload,
        evidence,
        retrieval_backend="milvus",
    )

    assert action == FollowUpType.switch_dimension.value
    assert question_id == 1
    assert session.current_turn == 2
    assert session.status == InterviewStatus.technical_question
    assert repo.created_questions[0]["category"] == QuestionCategory.technical
    assert repo.created_questions[0]["competency_code"] == "architecture"
    assert retrieval_service.calls[0]["query"].startswith("cpp_backend architecture")
    prompt_call = prompt_service.calls[0]
    assert prompt_call["variables"]["task_context"]["follow_up_type"] == "switch_dimension"
    assert prompt_call["variables"]["retrieval_context"][0]["source_type"] == "knowledge"

def test_incomplete_answer_stays_on_same_competency_for_follow_up():
    evidence = build_evidence()
    service, repo, prompt_service, retrieval_service = build_service(evidence)
    service._analyze_answer = lambda session, question, answer_text, items, retrieval_backend="unknown": {
        "facts": ["mentioned cache"],
        "missing_points": ["missing trade-offs and rollout details"],
        "off_topic": False,
        "credibility_risk": False,
        "is_complete": False,
        "fallback_used": False,
        "confused": False,
        "low_signal": False,
    }
    session = SimpleNamespace(
        id=1,
        current_turn=1,
        max_questions=6,
        status=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
    )
    question = SimpleNamespace(competency_code="system_design", question_text="Design a high-concurrency API.")
    score_payload = {"text_scores": {"accuracy": 78, "completeness": 76, "credibility": 75}}

    action, question_id = service._plan_next_question(
        session,
        question,
        "still incomplete",
        score_payload,
        evidence,
        retrieval_backend="milvus",
    )

    assert action == FollowUpType.deepen.value
    assert question_id == 1
    assert session.current_turn == 1
    assert session.status == InterviewStatus.deep_follow_up
    assert repo.created_questions[0]["category"] == QuestionCategory.follow_up
    assert repo.created_questions[0]["competency_code"] == "system_design"
    assert retrieval_service.calls == []
    prompt_call = prompt_service.calls[0]
    assert prompt_call["variables"]["conversation_context"]["missing_points"] == ["missing trade-offs and rollout details"]
    assert prompt_call["variables"]["retrieval_context"][0]["source_type"] == "knowledge"


def test_last_main_question_finishes_without_fixed_wrap_up():
    evidence = build_evidence()
    service, repo, prompt_service, retrieval_service = build_service(evidence)
    service._analyze_answer = lambda session, question, answer_text, items, retrieval_backend="unknown": {
        "facts": ["covered the bottleneck and trade-offs"],
        "missing_points": [],
        "off_topic": False,
        "credibility_risk": False,
        "is_complete": True,
        "fallback_used": False,
        "confused": False,
        "low_signal": False,
    }
    session = SimpleNamespace(
        id=1,
        current_turn=6,
        max_questions=6,
        status=None,
        completed_at=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
    )
    question = SimpleNamespace(id=21, competency_code="system_design", question_text="Design a high-concurrency API.")
    score_payload = {"text_scores": {"accuracy": 82, "completeness": 84, "credibility": 80}}

    action, question_id = service._plan_next_question(
        session,
        question,
        "complete answer",
        score_payload,
        evidence,
        retrieval_backend="milvus",
    )

    assert action == "completed"
    assert question_id is None
    assert session.status == InterviewStatus.completed
    assert session.completed_at is not None
    assert repo.created_questions == []
    assert retrieval_service.calls == []
    assert prompt_service.calls == []


def test_complete_session_allows_early_finish_without_answers():
    service = object.__new__(InterviewService)
    session = SimpleNamespace(id=9, answers=[], status=InterviewStatus.technical_question, report=None)
    expected_report = InterviewReportRead(
        session_id=9,
        total_score=0,
        report_level="Needs Improvement",
        competency_scores={},
        radar=[],
        suggestions=[],
        qa_records=[],
        next_training_plan=["start"],
        summary="empty",
    )
    service._get_session = lambda session_id: session
    service._finalize_session = lambda current_session: expected_report
    service._cleanup_expired_sessions = lambda user_id=None: 0

    report = service.complete_session(9)

    assert report == expected_report


def test_confused_answer_gets_only_one_clarifying_redirect_then_switches_dimension():
    evidence = build_evidence()
    service, repo, prompt_service, retrieval_service = build_service(evidence)
    service._analyze_answer = lambda session, question, answer_text, items, retrieval_backend="unknown": {
        "facts": [],
        "missing_points": ["候选人已经明确表示未理解题意"],
        "off_topic": False,
        "credibility_risk": True,
        "is_complete": False,
        "fallback_used": False,
        "confused": True,
        "low_signal": True,
    }
    session = SimpleNamespace(
        id=1,
        current_turn=1,
        max_questions=6,
        status=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        questions=[],
    )
    question = SimpleNamespace(id=11, competency_code="system_design", question_text="Design a high-concurrency API.")
    score_payload = {"text_scores": {"accuracy": 20, "completeness": 18, "credibility": 18}}

    action, _ = service._plan_next_question(
        session,
        question,
        "我不理解这题什么意思",
        score_payload,
        evidence,
        retrieval_backend="milvus",
    )

    assert action == FollowUpType.redirect.value
    prompt_call = prompt_service.calls[0]
    assert prompt_call["variables"]["conversation_context"]["candidate_confused"] is True
    assert "缩小范围" in prompt_call["variables"]["draft"]["question"]
    assert repo.created_questions[0]["follow_up_type"] == FollowUpType.redirect

    session.questions = [
        SimpleNamespace(
            id=11,
            turn_no=1,
            category=QuestionCategory.technical,
            competency_code="system_design",
            question_text="Design a high-concurrency API.",
            follow_up_type=FollowUpType.none,
        ),
        SimpleNamespace(
            id=12,
            turn_no=2,
            category=QuestionCategory.follow_up,
            competency_code="system_design",
            question_text="Clarify once.",
            follow_up_type=FollowUpType.redirect,
        ),
    ]
    service._next_turn_no = lambda current_session: 3

    action, _ = service._plan_next_question(
        session,
        question,
        "还是不太明白",
        score_payload,
        evidence,
        retrieval_backend="milvus",
    )

    assert action == FollowUpType.switch_dimension.value


def test_repeated_follow_up_type_switches_dimension_instead_of_repeating():
    evidence = build_evidence()
    service, repo, prompt_service, retrieval_service = build_service(evidence)
    service._analyze_answer = lambda session, question, answer_text, items, retrieval_backend="unknown": {
        "facts": ["mentioned one cache detail"],
        "missing_points": ["missing quantified impact"],
        "off_topic": False,
        "credibility_risk": True,
        "is_complete": False,
        "fallback_used": False,
        "confused": False,
        "low_signal": False,
    }
    session = SimpleNamespace(
        id=1,
        current_turn=1,
        max_questions=6,
        status=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        questions=[
            SimpleNamespace(
                id=21,
                turn_no=1,
                category=QuestionCategory.technical,
                competency_code="system_design",
                question_text="Design a high-concurrency API.",
                follow_up_type=FollowUpType.none,
            ),
            SimpleNamespace(
                id=22,
                turn_no=2,
                category=QuestionCategory.follow_up,
                competency_code="system_design",
                question_text="What metric proves the impact?",
                follow_up_type=FollowUpType.credibility,
            ),
        ],
    )
    question = session.questions[0]
    score_payload = {"text_scores": {"accuracy": 72, "completeness": 68, "credibility": 40}}

    action, _ = service._plan_next_question(
        session,
        question,
        "still vague answer",
        score_payload,
        evidence,
        retrieval_backend="milvus",
    )

    assert action == FollowUpType.switch_dimension.value
    assert repo.created_questions[-1]["category"] == QuestionCategory.technical


def test_low_signal_answer_uses_redirect_instead_of_credibility():
    evidence = build_evidence()
    service, repo, prompt_service, retrieval_service = build_service(evidence)
    service._analyze_answer = lambda session, question, answer_text, items, retrieval_backend="unknown": {
        "facts": [],
        "missing_points": ["回答信息量过低，缺少可继续深挖的有效细节"],
        "off_topic": False,
        "credibility_risk": True,
        "is_complete": False,
        "fallback_used": False,
        "confused": False,
        "low_signal": True,
    }
    session = SimpleNamespace(
        id=1,
        current_turn=1,
        max_questions=6,
        status=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        questions=[],
    )
    question = SimpleNamespace(id=31, competency_code="system_design", question_text="Design a high-concurrency API.")
    score_payload = {"text_scores": {"accuracy": 52, "completeness": 42, "credibility": 30}}

    action, _ = service._plan_next_question(
        session,
        question,
        "差不多就是做了优化",
        score_payload,
        evidence,
        retrieval_backend="milvus",
    )

    assert action == FollowUpType.redirect.value
    assert repo.created_questions[0]["follow_up_type"] == FollowUpType.redirect
    assert retrieval_service.calls == []
    assert prompt_service.calls[0]["variables"]["task_context"]["follow_up_type"] == "redirect"


def test_credibility_follow_up_is_limited_to_one_per_session():
    evidence = build_evidence()
    service, repo, prompt_service, retrieval_service = build_service(evidence)
    service._analyze_answer = lambda session, question, answer_text, items, retrieval_backend="unknown": {
        "facts": ["提到了缓存方案和压测结果"],
        "missing_points": ["缺少个人贡献和量化结果的核验"],
        "off_topic": False,
        "credibility_risk": True,
        "is_complete": False,
        "fallback_used": False,
        "confused": False,
        "low_signal": False,
    }
    session = SimpleNamespace(
        id=1,
        current_turn=2,
        max_questions=6,
        status=None,
        style=InterviewStyle.medium,
        position=SimpleNamespace(code="cpp_backend", name="CPP Backend"),
        questions=[
            SimpleNamespace(
                id=41,
                turn_no=1,
                category=QuestionCategory.technical,
                competency_code="system_design",
                question_text="Design a high-concurrency API.",
                follow_up_type=FollowUpType.none,
            ),
            SimpleNamespace(
                id=42,
                turn_no=2,
                category=QuestionCategory.follow_up,
                competency_code="system_design",
                question_text="What metrics prove the impact?",
                follow_up_type=FollowUpType.credibility,
            ),
            SimpleNamespace(
                id=43,
                turn_no=3,
                category=QuestionCategory.technical,
                competency_code="architecture",
                question_text="How would you evolve the service architecture?",
                follow_up_type=FollowUpType.none,
            ),
        ],
    )
    question = session.questions[-1]
    score_payload = {"text_scores": {"accuracy": 70, "completeness": 66, "credibility": 42}}

    action, _ = service._plan_next_question(
        session,
        question,
        "我做了缓存改造，压测的时候吞吐提升了30%，但这里先不展开。",
        score_payload,
        evidence,
        retrieval_backend="milvus",
    )

    assert action == FollowUpType.deepen.value
    assert repo.created_questions[0]["follow_up_type"] == FollowUpType.deepen
    assert prompt_service.calls[0]["variables"]["task_context"]["follow_up_type"] == "deepen"


def test_question_seed_service_filters_distorted_authenticity_questions(tmp_path):
    seed_dir = tmp_path / "question_seeds"
    seed_dir.mkdir()
    (seed_dir / "cpp_backend.json").write_text(
        """
{
  "opening": [
    {"question": "请解释 项目真实性 的核心概念，并说明它主要解决什么问题。", "competency_code": "project_depth"},
    {"question": "请解释 网关架构 的核心概念，并说明它主要解决什么问题。", "competency_code": "project_depth"}
  ],
  "competencies": {
    "project_depth": [
      {"question": "请从机制角度解释 项目真实性 为什么能工作，并说明它的关键约束。"},
      {"question": "请从机制角度解释 网关架构 为什么能工作，并说明它的关键约束。"}
    ]
  },
  "follow_up": {}
}
""".strip(),
        encoding="utf-8",
    )

    service = object.__new__(QuestionSeedService)
    service.seed_dir = seed_dir
    service.question_bank_path = tmp_path / "question.jsonl"
    service._seed_cache = {}
    service._question_cache = {}

    opening_question, _ = service.get_opening_question("cpp_backend", [], [], [])
    main_question = service.get_question_for_competency("cpp_backend", "project_depth", [])

    assert "项目真实性" not in opening_question
    assert "项目真实性" not in main_question


def test_project_depth_questions_skip_conceptual_question_bank_entries(tmp_path):
    seed_dir = tmp_path / "question_seeds"
    seed_dir.mkdir()
    (seed_dir / "cpp_backend.json").write_text(
        """
{
  "opening": [
    {"question": "请解释 网关架构 的核心概念，并说明它主要解决什么问题。", "competency_code": "project_depth"}
  ],
  "competencies": {
    "project_depth": [
      {"question": "网关架构 和 虚函数与多态 应该怎么比较？"}
    ]
  },
  "follow_up": {}
}
""".strip(),
        encoding="utf-8",
    )
    question_bank = tmp_path / "question.jsonl"
    question_bank.write_text(
        """
{"role_code":"cpp_backend","doc_type":"question","source_type":"project_depth","title":"网关架构 和 虚函数与多态 应该怎么比较？","content":"", "parsed_meta":{"题目":"网关架构 和 虚函数与多态 应该怎么比较？"}}
""".strip(),
        encoding="utf-8",
    )

    service = object.__new__(QuestionSeedService)
    service.seed_dir = seed_dir
    service.question_bank_path = question_bank
    service._seed_cache = {}
    service._question_cache = {}

    opening_question, _ = service.get_opening_question("cpp_backend", [], [], [])
    main_question = service.get_question_for_competency("cpp_backend", "project_depth", [])

    assert "网关架构 和 虚函数与多态" not in opening_question
    assert "网关架构 和 虚函数与多态" not in main_question
    assert "代表性项目" in main_question
    assert "代表性项目" in opening_question or "做过的" in opening_question


def test_non_project_questions_keep_question_body_clean(tmp_path):
    seed_dir = tmp_path / "question_seeds"
    seed_dir.mkdir()
    (seed_dir / "cpp_backend.json").write_text(
        """
{
  "opening": [],
  "competencies": {
    "cpp_language": [
      {"question": "请解释 Lambda 捕获 的核心概念，并说明它主要解决什么问题。"}
    ],
    "system_design": [
      {"question": "请对比 缓存击穿与热点治理 和 分布式锁 的适用场景、优缺点以及你在项目里会如何选择。"}
    ]
  },
  "follow_up": {}
}
""".strip(),
        encoding="utf-8",
    )

    service = object.__new__(QuestionSeedService)
    service.seed_dir = seed_dir
    service.question_bank_path = tmp_path / "question.jsonl"
    service._seed_cache = {}
    service._question_cache = {}

    concept_question = service.get_question_for_competency("cpp_backend", "cpp_language", [])
    comparison_question = service.get_question_for_competency("cpp_backend", "system_design", [])

    assert "做法、取舍和结果" not in concept_question
    assert concept_question == "请解释 Lambda 捕获 的核心概念，并说明它主要解决什么问题。"
    assert "做法、取舍和结果" not in comparison_question
    assert comparison_question == "请对比 缓存击穿与热点治理 和 分布式锁 的适用场景、优缺点以及你在项目里会如何选择。"


def test_project_or_scenario_questions_are_clean_in_medium_mode(tmp_path):
    seed_dir = tmp_path / "question_seeds"
    seed_dir.mkdir()
    (seed_dir / "cpp_backend.json").write_text(
        """
{
  "opening": [],
  "competencies": {
    "system_design": [
      {"question": "请结合一个真实项目，说明你在处理 分布式锁 相关问题时的职责、方案、指标和复盘。"}
    ]
  },
  "follow_up": {}
}
""".strip(),
        encoding="utf-8",
    )

    service = object.__new__(QuestionSeedService)
    service.seed_dir = seed_dir
    service.question_bank_path = tmp_path / "question.jsonl"
    service._seed_cache = {}
    service._question_cache = {}

    main_question = service.get_question_for_competency("cpp_backend", "system_design", [])

    assert main_question == "请结合一个真实项目，说明你在处理 分布式锁 相关问题时的职责、方案、指标和复盘。"


def test_project_or_scenario_questions_are_clean_in_hard_mode(tmp_path):
    seed_dir = tmp_path / "question_seeds"
    seed_dir.mkdir()
    (seed_dir / "cpp_backend.json").write_text(
        """
{
  "opening": [],
  "competencies": {
    "system_design": [
      {"question": "请结合一个真实项目，说明你在处理 分布式锁 相关问题时的职责、方案、指标和复盘。"}
    ]
  },
  "follow_up": {}
}
""".strip(),
        encoding="utf-8",
    )

    service = object.__new__(QuestionSeedService)
    service.seed_dir = seed_dir
    service.question_bank_path = tmp_path / "question.jsonl"
    service._seed_cache = {}
    service._question_cache = {}

    main_question = service.get_question_for_competency("cpp_backend", "system_design", [], style="hard")

    assert main_question == "请结合一个真实项目，说明你在处理 分布式锁 相关问题时的职责、方案、指标和复盘。"



