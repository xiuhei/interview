from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.enums import ResumeStatus
from app.services.resume_service import ResumeService


class DummyDB:
    def commit(self) -> None:
        return None

    def refresh(self, _resume) -> None:
        return None


class DummyRepo:
    def __init__(self, resume) -> None:
        self.resume = resume
        self.created_parse = None

    def get(self, resume_id: int):
        return self.resume if self.resume.id == resume_id else None

    def create_parse(self, **kwargs):
        self.created_parse = kwargs
        self.resume.parse = SimpleNamespace(summary=kwargs["summary"], raw_result=kwargs["raw_result"])
        return self.resume.parse

    def list_for_user(self, user_id: int):
        return [self.resume] if getattr(self.resume, "user_id", user_id) == user_id else []


class DummyPromptService:
    def __init__(self, prompt_result: dict, fallback_used: bool = False) -> None:
        self.prompt_result = prompt_result
        self.fallback_used = fallback_used
        self.calls: list[dict] = []

    def run_json_prompt(self, name: str, variables: dict, fallback_result: dict | None = None):
        self.calls.append(
            {
                "name": name,
                "variables": variables,
                "fallback_result": fallback_result,
            }
        )
        return self.prompt_result, self.fallback_used


def cpp_backend_position_repo():
    return SimpleNamespace(
        list_positions=lambda: [
            SimpleNamespace(
                code="cpp_backend",
                name="C++ backend",
                competencies=[
                    SimpleNamespace(code="system_design", weight=0.6),
                    SimpleNamespace(code="performance", weight=0.4),
                ],
            )
        ]
    )


def test_resume_parse_persists_prompt_summary(tmp_path):
    uploads_dir = tmp_path / "data" / "uploads" / "resumes"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    resume_file = uploads_dir / "resume.txt"
    resume_file.write_text(
        "3 years of C++ backend work, owned a trading system and improved throughput.",
        encoding="utf-8",
    )

    resume = SimpleNamespace(
        id=1,
        stored_path="uploads/resumes/resume.txt",
        parse=None,
        raw_text="",
        status=ResumeStatus.uploaded,
    )
    service = object.__new__(ResumeService)
    service.db = DummyDB()
    service.repo = DummyRepo(resume)
    service.settings = SimpleNamespace(upload_dir=tmp_path / "data" / "uploads")
    service.prompt_service = DummyPromptService(
        {
            "background": "3 years of C++ backend work with trading-system ownership.",
            "project_experiences": ["Trading system performance tuning"],
            "tech_stack": ["C++", "Redis", "MySQL"],
            "highlights": ["Improved throughput"],
            "risk_points": ["More quant results can still be added"],
            "years_of_experience": 3,
        }
    )

    parsed_resume = service.parse_resume(1)

    assert parsed_resume.status == ResumeStatus.parsed
    assert parsed_resume.parse.summary["background"] == "3 years of C++ backend work with trading-system ownership."
    assert parsed_resume.parse.summary["tech_stack"] == ["C++", "Redis", "MySQL"]
    prompt_call = service.prompt_service.calls[0]
    assert prompt_call["name"] == "resume_parse"
    assert prompt_call["variables"]["draft"]["background"]


def test_resume_parse_falls_back_to_draft_when_prompt_result_is_empty():
    resume = SimpleNamespace(
        id=2,
        stored_path="uploads/resumes/resume.txt",
        parse=None,
        raw_text="",
        status=ResumeStatus.uploaded,
    )
    service = object.__new__(ResumeService)
    service.db = DummyDB()
    service.repo = DummyRepo(resume)
    service.settings = SimpleNamespace(upload_dir=ROOT / "data" / "uploads")
    service.prompt_service = DummyPromptService(
        {
            "background": "",
            "project_experiences": [],
            "tech_stack": [],
            "highlights": [],
            "risk_points": [],
            "years_of_experience": None,
        },
        fallback_used=True,
    )
    service._build_summary = lambda text: SimpleNamespace(
        model_dump=lambda: {
            "background": "Draft background",
            "project_experiences": ["Draft project"],
            "tech_stack": ["Redis"],
            "highlights": ["Draft highlight"],
            "risk_points": ["Draft risk"],
            "years_of_experience": 2,
        }
    )

    import app.services.resume_service as resume_module

    original_clean_text = resume_module.clean_text
    original_read_resume_text = resume_module.read_resume_text
    resume_module.clean_text = lambda text: text
    resume_module.read_resume_text = lambda path: "Draft resume text"
    try:
        parsed_resume = service.parse_resume(2)
    finally:
        resume_module.clean_text = original_clean_text
        resume_module.read_resume_text = original_read_resume_text

    assert parsed_resume.parse.summary["background"] == "Draft background"
    assert parsed_resume.parse.raw_result["fallback_used"] is True


def test_resume_parse_builds_job_match_and_resume_scores(tmp_path):
    uploads_dir = tmp_path / "data" / "uploads" / "resumes"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    resume_file = uploads_dir / "resume.txt"
    resume_file.write_text(
        "3年 C++ 后端开发，负责交易系统和高并发服务，使用 C++、Redis、MySQL、Linux 做性能优化，吞吐提升 40%。",
        encoding="utf-8",
    )

    resume = SimpleNamespace(
        id=3,
        user_id=7,
        stored_path="uploads/resumes/resume.txt",
        parse=None,
        raw_text="",
        status=ResumeStatus.uploaded,
    )
    service = object.__new__(ResumeService)
    service.db = DummyDB()
    service.repo = DummyRepo(resume)
    service.settings = SimpleNamespace(upload_dir=tmp_path / "data" / "uploads")
    service.position_repo = SimpleNamespace(
        list_positions=lambda: [
            SimpleNamespace(
                code="cpp_backend",
                name="C++后端开发",
                competencies=[
                    SimpleNamespace(code="system_design", weight=0.6),
                    SimpleNamespace(code="performance", weight=0.4),
                ],
            )
        ]
    )
    service.prompt_service = DummyPromptService(
        {
            "background": "3年 C++ 后端开发，负责交易系统和高并发服务。",
            "project_experiences": ["交易系统性能优化"],
            "tech_stack": ["C++", "Redis", "MySQL", "Linux"],
            "highlights": ["高并发服务优化"],
            "risk_points": ["可继续补充更多量化收益"],
            "years_of_experience": 3,
        }
    )

    parsed_resume = service.parse_resume(3)

    assert parsed_resume.parse.summary["overall_score"] > 0
    assert parsed_resume.parse.summary["best_job_match"]["position_code"] == "cpp_backend"
    assert parsed_resume.parse.summary["job_matches"][0]["matched_skills"]
    assert parsed_resume.parse.summary["score_breakdown"]["role_relevance"] >= 30
    assert parsed_resume.parse.summary["resume_suggestions"]


def test_resume_parse_penalizes_sparse_unstructured_resume(tmp_path):
    uploads_dir = tmp_path / "data" / "uploads" / "resumes"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    resume_file = uploads_dir / "resume.txt"
    resume_file.write_text(
        "张三简历。做过一点项目，学习能力强，希望找开发工作。",
        encoding="utf-8",
    )

    resume = SimpleNamespace(
        id=4,
        user_id=7,
        stored_path="uploads/resumes/resume.txt",
        parse=None,
        raw_text="",
        status=ResumeStatus.uploaded,
    )
    service = object.__new__(ResumeService)
    service.db = DummyDB()
    service.repo = DummyRepo(resume)
    service.settings = SimpleNamespace(upload_dir=tmp_path / "data" / "uploads")
    service.position_repo = cpp_backend_position_repo()
    service.prompt_service = DummyPromptService(
        {
            "background": "求职开发岗位。",
            "project_experiences": ["做过一点项目"],
            "tech_stack": ["C++"],
            "highlights": ["学习能力强"],
            "risk_points": ["项目描述较少"],
            "years_of_experience": None,
        }
    )

    parsed_resume = service.parse_resume(4)
    summary = parsed_resume.parse.summary

    assert summary["overall_score"] < 45
    assert summary["score_breakdown"]["project_depth"] < 35
    assert summary["score_breakdown"]["impact"] <= 20
    assert summary["score_breakdown"]["role_relevance"] < 35


def test_resume_parse_penalizes_irrelevant_resume_even_if_well_structured(tmp_path):
    uploads_dir = tmp_path / "data" / "uploads" / "resumes"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    resume_file = uploads_dir / "resume.txt"
    resume_file.write_text(
        (
            "Alice Zhang\n"
            "3 years of campus operations experience.\n"
            "Led university event planning, coordinated 20 volunteers, and increased attendance by 35%.\n"
            "Built activity calendars, managed budgets, and improved on-site process efficiency.\n"
            "Skills: Excel, PowerPoint, communication, event planning.\n"
        ),
        encoding="utf-8",
    )

    resume = SimpleNamespace(
        id=5,
        user_id=7,
        stored_path="uploads/resumes/resume.txt",
        parse=None,
        raw_text="",
        status=ResumeStatus.uploaded,
    )
    service = object.__new__(ResumeService)
    service.db = DummyDB()
    service.repo = DummyRepo(resume)
    service.settings = SimpleNamespace(upload_dir=tmp_path / "data" / "uploads")
    service.position_repo = cpp_backend_position_repo()
    service.prompt_service = DummyPromptService(
        {
            "background": "3 years of campus operations experience with event execution ownership.",
            "project_experiences": ["Led university event planning and improved attendance by 35%"],
            "tech_stack": ["Excel", "PowerPoint"],
            "highlights": ["Improved attendance by 35%"],
            "risk_points": ["Lacks direct backend engineering experience"],
            "years_of_experience": 3,
        }
    )

    parsed_resume = service.parse_resume(5)
    summary = parsed_resume.parse.summary

    assert summary["score_breakdown"]["clarity"] >= 45
    assert summary["score_breakdown"]["impact"] >= 20
    assert summary["score_breakdown"]["role_relevance"] < 30
    assert summary["best_job_match"]["score"] < 30
    assert summary["overall_score"] < 55


def test_list_resumes_returns_summary_for_personal_repository():
    summary = {
        "candidate_name": "张三",
        "background": "背景",
        "project_experiences": ["项目A"],
        "tech_stack": ["C++"],
        "highlights": ["性能优化"],
        "risk_points": ["缺少量化结果"],
        "years_of_experience": 3,
        "overall_score": 80,
        "score_breakdown": {
            "clarity": 80,
            "project_depth": 82,
            "impact": 75,
            "role_relevance": 85,
            "credibility": 78,
        },
        "job_matches": [],
        "best_job_match": None,
        "resume_suggestions": ["补充量化结果"],
        "interview_focuses": ["优先追问项目结果"],
    }
    resume = SimpleNamespace(
        id=9,
        user_id=7,
        filename="resume.pdf",
        stored_path="uploads/resumes/resume.pdf",
        mime_type="application/pdf",
        status=ResumeStatus.parsed,
        created_at=datetime(2026, 3, 27, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 27, tzinfo=timezone.utc),
        parse=SimpleNamespace(summary=summary),
    )
    service = object.__new__(ResumeService)
    service.repo = DummyRepo(resume)

    items = service.list_resumes(7)

    assert len(items) == 1
    assert items[0].summary is not None
    assert items[0].summary.overall_score == 80
