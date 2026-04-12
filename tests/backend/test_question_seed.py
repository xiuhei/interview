from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.question_seed_service import QuestionSeedService


def test_question_seed_loading():
    service = QuestionSeedService()
    question, competency = service.get_opening_question("cpp_backend", [], [])
    assert question
    assert competency == "project_depth"


def test_opening_question_uses_rotating_default_when_project_depth_pool_is_empty(tmp_path):
    seed_dir = tmp_path / "question_seeds"
    seed_dir.mkdir()
    (seed_dir / "cpp_backend.json").write_text(
        """
{
  "opening": [
    {"question": "请解释 网关架构 的核心概念，并说明它主要解决什么问题。", "competency_code": "project_depth"},
    {"question": "请从机制角度解释 网关架构 为什么能工作，并说明它的关键约束。", "competency_code": "project_depth"},
    {"question": "如果在项目里遇到和 网关架构 相关的问题，你会如何判断是否采用它，并如何验证效果？", "competency_code": "project_depth"}
  ],
  "competencies": {},
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

    variants = {
        service.get_opening_question("cpp_backend", [], [], used_questions=[], selector_seed=f"{index}:opening")[0]
        for index in range(1, 16)
    }
    first = next(iter(variants))
    competency = service.get_opening_question("cpp_backend", [], [], used_questions=[], selector_seed="1:opening")[1]

    assert competency == "project_depth"
    assert first
    assert all(("C++ 后端项目" in item or "后端优化或故障排查" in item) for item in variants)
    assert len(variants) >= 2
